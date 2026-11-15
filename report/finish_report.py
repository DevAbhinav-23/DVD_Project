from pathlib import Path
import csv, re, shutil, zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'report' / 'completed'
OUT.mkdir(exist_ok=True)
source = Path(r'C:\Users\srika\.codex\attachments\dfb46a91-aacd-4a55-8460-c9f6dc43caaf\Pasted text.txt').read_text(encoding='utf-8-sig')
section = (ROOT/'report/part4_section.tex').read_text(encoding='utf-8')
section = section.replace('% Numerical results remain blank pending consistent upstream regeneration.', '% Results from the junction-area-consistent artifacts at commit 29d644c.')
section = section.replace('The intended consistent device setup uses', 'The device setup uses')
start = section.index(r'\noindent\textit{Final validation outcomes')
end = section.index(r'\subsection{Results}', start)
section = section[:start] + r'''The saved circuit reference was generated with ngspice-47 and Python
3.12.13. All 102,400 corner--vector combinations are present, and all
recorded NAND outputs agree with their Boolean values. The largest output
deviation from its ideal rail is 0.5366\% of $V_{DD}$; the largest primary
input deviation is $4.96\times10^{-12}$\,V, below the 1\,nV tolerance.
There are 51,200 valid-parity and 51,200 error cases.

The final saved results were also checked for complete coverage, agreement
with the circuit SPICE reference, and correct recomputation of the error
metrics. All 17 recorded input/code hashes match the supplied artifacts.
The repository additionally includes a successful 1,200-case operating-point/DC
cross-check from the earlier circuit revision; it is supporting validation
of the sweep method, not a new cross-check of the final junction-area revision.

''' + section[end:]
start = section.index(r'\begin{table}[H]', section.index(r'\subsection{Results}'))
end = section.index(r'\subsection{Worked calculation}',start)
with (ROOT/'results/part4/circuit_table.csv').open() as f: metrics=list(csv.DictReader(f))
names=['ML plain sum','ML corrected','ML corrected + primary inputs','SPICE lookup plain','SPICE lookup corrected']
table = r'''\begin{table}[H]
\centering\small
\begin{tabular}{lrrrrr}
\toprule
Estimate & Bias (\%) & Median (\%) & p95 (\%) & Mean (\%) & Max (\%)\\
\midrule
'''
for name,row in zip(names,metrics):
    table += name+' & '+' & '.join(f'{float(row[k]):.2f}' for k in ['bias_pct','median_err_pct','p95_err_pct','mean_err_pct','max_err_pct'])+r' \\'+'\n'
table += r'''\bottomrule
\end{tabular}
\caption{Circuit relative errors over all 102,400 cases. The last two rows
use isolated-gate SPICE currents as diagnostics. Only the primary-input
variant includes primary-input supply currents in its reference.}
\label{tab:circuitresults}
\end{table}

\begin{table}[H]
\centering
\begin{tabular}{lrr}
\toprule
ML estimate & Median SPICE ($\mu$A) & Median ML ($\mu$A)\\
\midrule
'''
for name,row in zip(names[:3],metrics[:3]):
    table+=name+f" & {float(row['spice_median_A'])*1e6:.4f} & {float(row['prediction_median_A'])*1e6:.4f}"+r' \\'+'\n'
table+=r'''\bottomrule
\end{tabular}
\caption{Median reference and predicted leakage. These are medians of
currents, rather than currents from one representative simulation.}
\end{table}

The corrected supply estimate reaches \textbf{1.14\% median error},
\textbf{3.63\% p95 error}, and \textbf{1.40\% mean error}, equivalent to
\textbf{98.60\% mean accuracy}. Its median signed bias is $-0.62\%$,
indicating slight underestimation. The approximately 99\% mean-accuracy
objective is not reached. The plain sum has 24.76\% mean error, showing
why internally supplied input currents matter. Including primary high-input
currents in both sides gives 1.38\% mean error under that alternative definition.

\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{circuit_parity.png}
\caption{Plain and corrected ML leakage against complete-circuit SPICE
over all 102,400 cases. The diagonal indicates exact agreement.}
\label{fig:circuitparity}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=0.85\linewidth]{error_vs_temperature.png}
\caption{Corrected relative error against temperature. Multiple vectors
share each of the 200 PVT corners.}
\label{fig:circuittemperature}
\end{figure}

'''
section=section[:start]+table+section[end:]
section=section.replace('For vector \\texttt{000000000} at corner 0, Boolean evaluation gives eight', 'For vector \\texttt{000000000} at corner 0 ($V_{DD}=0.842208$\\,V,\n$T=87.773\\,^\\circ$C), Boolean evaluation gives eight')
values={'Plain gate sum ($\\mu$A)': '1.02026428', 'Internal high-input correction ($\\mu$A)': '0.20789869', 'Corrected estimate ($\\mu$A)': '1.22816297', 'Complete-circuit SPICE reference ($\\mu$A)': '1.24359123', 'Relative error (\\%)':'1.2406'}
for name,value in values.items():section=section.replace(name+' & \\\\',name+' & '+value+' \\\\')
section=section.replace('Worked example; numerical values await the final run.', 'Worked example for vector \\texttt{000000000} at corner 0. The expected parity-error output is 0.')
start=section.index(r'\noindent\textit{Results-dependent discussion')
end=section.index('The lookup assumes',start)
section=section[:start]+r'''The corrected circuit mean error (1.40\%) is lower than the isolated NAND2
mean error (1.79\%; p95 4.56\%). Combining gate contributions can average
some model errors, but the complete circuit also introduces analog loading.
Using exact isolated-gate SPICE currents still gives 0.71\% mean error
after correction, compared with 24.61\% for the uncorrected sum. Thus,
improving transistor fits alone does not remove the error of composing
isolated gates.

The worst individual case is vector \texttt{111111110} at corner 72:
$V_{DD}=0.94936$\,V and $T=124.91\,^\circ$C. SPICE gives
2.92193\,$\mu$A and the corrected model gives 2.72699\,$\mu$A,
an error of 6.67\%. Corner 72 also has the largest mean error over its
512 vectors (5.60\%). Across corners, the worst vector by mean error is
\texttt{111111111}, at 1.49\%.

\begin{table}[H]
\centering
\begin{tabular}{lrr}
\toprule
Temperature range ($^\circ$C) & Mean error (\%) & p95 error (\%)\\
\midrule
$-38.48$ to $6.49$ & 1.24 & 2.71\\
$6.78$ to $44.46$ & 0.97 & 2.36\\
$44.97$ to $84.93$ & 1.28 & 3.56\\
$87.09$ to $124.91$ & 2.13 & 5.14\\
\bottomrule
\end{tabular}
\caption{Corrected error in temperature quartiles, each containing 50
corners and 25,600 cases. Other PVT parameters vary within each group.}
\end{table}

The hottest quartile has the highest mean error, but this is an association
in the sampled corners rather than an isolated causal temperature effect.
With the full-circuit current as the common denominator, mean signed error
splits into $+0.017$ percentage points from ML versus isolated-gate SPICE
and $-0.699$ points from isolated-gate composition versus the full circuit,
giving $-0.682$ points overall. These are signed means, not the median bias.

''' + section[end:]
section=section[:section.index(r'\subsection{Reproducibility}')]+r'''\subsection{Reproducibility and submitted artifacts}
The reported predictions use the regenerated junction-area datasets and
retrained models merged in commit \texttt{29d644c}. The saved full-circuit
SPICE reference already uses the same junction-area convention. The
comparison was refreshed with the new models; retraining is not needed
when reproducing Part 4 from these supplied upstream artifacts.

The command \texttt{python run\_all.py --part4-only} runs the circuit tests,
simulation workflow and comparison. The separate script
\texttt{part4\_circuit/cross\_check.py} runs the operating-point/DC check.
The repository provides the following Part 4 deliverables:
\begin{itemize}
\item Circuit construction, exhaustive logic checks, simulation and
comparison code in \texttt{part4\_circuit/}, with \texttt{run\_all.py}
as the pipeline entry point.
\item Runnable transistor netlists \texttt{parity9\_example.cir} and
\texttt{parity9\_dc.cir} in \texttt{results/part4/}.
\item Compressed full-circuit SPICE records and circuit predictions;
the 800-entry NAND2 lookup; summary tables and both result plots.
\item Per-corner, per-vector and PVT-quartile error tables, worst cases,
and all 32 gate contributions for the worked example.
\item Simulation metadata, package versions and artifact hashes for
tracing the results to their inputs and code.
\end{itemize}
These artifacts retain the baseline and corrected estimates, so the
accuracy improvement and the remaining approximation error can both be
examined directly.
'''
assert not re.search('pending|placeholder|await|intentionally blank',section,re.I)
(OUT/'part4_section.tex').write_text(section,encoding='utf-8')
fixed=source.replace(r'\usepackage{float}',r'\usepackage{float}'+'\n'+r'\usepackage{amsmath}'+'\n'+r'\usepackage{booktabs}')
heading=r'{\Large\textbf{Part 2: Transistor-Level ML Models}}'
fixed=fixed.replace(heading,r'\begin{center}'+'\n'+heading)
combined=fixed.replace(r'\end{document}',section+'\n'+r'\end{document}')
restored=combined.replace(section+'\n','').replace(r'\begin{center}'+'\n'+heading,heading).replace(r'\usepackage{float}'+'\n'+r'\usepackage{amsmath}'+'\n'+r'\usepackage{booktabs}',r'\usepackage{float}')
assert restored==source,'Other members content changed'
(OUT/'project_report.tex').write_text(combined,encoding='utf-8')
for name in set(re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',combined)):
    matches=[p for p in (ROOT/'results').rglob(name) if 'smoke' not in p.parts and 'pilot' not in p.parts]; assert len(matches)==1,(name,matches)
    shutil.copy2(matches[0],OUT/name)
clean=re.sub(r'(?<!\\)%[^\n]*','',combined)
stack=[]
for action,env in re.findall(r'\\(begin|end)\{([^}]+)\}',clean):
    if action=='begin':stack.append(env)
    else:assert stack and stack.pop()==env,(action,env)
assert not stack
labels=re.findall(r'\\label\{([^}]+)\}',clean)
assert len(labels)==len(set(labels))
assert set(re.findall(r'\\ref\{([^}]+)\}',clean))<=set(labels)
print('PASS: other sections preserved except minimal syntax repairs; environments and references checked; latest figures copied.')

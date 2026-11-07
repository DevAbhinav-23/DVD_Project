# Part 4 deliverables and integration audit

Source: `docs/DVD_ML_PROJECT.pdf`, workflow Part C, Sections 5-6.
Circuit interpretation selected by the Part 4 owner: eight data bits plus one even-parity bit.

| Requirement | Evidence | Status |
|---|---|---|
| Assigned technology and supply | Shared 22nm MGK model, nominal 0.9 V, L=22 nm | Met |
| Complete transistor test-circuit netlist | `results/part4/parity9_example.cir` and `parity9_dc.cir`; 32 NAND2s, 128 FETs | Met |
| Required simulator tolerances | All netlists include the exact `config.SPICE_OPTIONS` line | Met |
| Every input combination | All 512 nine-bit vectors, including valid and invalid even parity | Met |
| Same 200 PVT corners as gate validation | `data/corners.csv`; reference PVT values checked against this file | Met |
| Complete circuit SPICE reference | `results/part4/spice_circuit.csv.gz`: 102,400 unique cases | Met |
| Hierarchical prediction using the four saved transistor models | Ordered NAND graph, Boolean evaluation, and gate lookup; original plain sum retained | Met |
| Matching leakage definitions | Supply-only main reference; internally driven input-current correction; separately matched primary-input variant | Met |
| Required circuit metrics | SPICE/ML medians, signed bias, median error, p95 error in `circuit_table.csv` / `.md`; mean/max also included | Met |
| Log-axis parity plot | `results/part4/plots/circuit_parity.png` | Met |
| Regenerating code in order with fixed seeds | `run_all.py --part4-only`; complete upstream sequence also provided by `run_all.py` | Part 4 path verified; complete upstream retraining still needs the team run |
| Circuit report, comparison with gate accuracy, error analysis and limitations | `results/part4/report_part4.md`, condition/vector/corner summaries and plots | Part 4 material met; combined final report still to assemble |
| Up to 99% mean accuracy objective | Supply-only estimate with internal input-current correction achieves 98.451% (1.549% mean relative error) | Below objective |

The submission uses the four saved transistor models and the Part 3 rail-input NAND2 lookup.
It reports the prescribed plain sum alongside the internal input-current correction.

`validation_summary.txt` and `op_dc_crosscheck.json` record coverage, functional checks,
and the 1,200-case independent operating-point/DC comparison. The extra validation checks
and current correction supplement the specified method; the plain hierarchical baseline remains available.

## Work for the later joint team task

1. Assemble one final typed report covering all ten deliverables in Section 6, using the existing
   Parts 1-3 artifacts and the Part 4 section. Include model comparison, chosen-model test metrics,
   gate and circuit tables, all required plots, and limitations.
2. Run the complete regeneration sequence once in a clean agreed environment. The Part 4 path
   has passed; the hours-long upstream retraining/learning-curve pipeline has not been rerun for
   this addition. Record the environment and review the regenerated numbers.
3. Agree on the primary leakage definition and disclose the input-current variant. State explicitly
   that this team used eight data bits plus a parity input. Explain the additional targeted training
   datasets and keep the four required 10,000-row uniform CSVs available.
4. Check report/table/plot consistency, package the specified datasets, example netlists, saved models,
   code and report, and complete the team's final submission. The brief does not specify a separate
   presentation; prepare one only if the course/TA asks for it elsewhere.

## Change safety

The protected Part 1-3 paths are unchanged relative to the checked-out Git HEAD:
`part1_dataset/`, `part2_models/`, `part3_gates/`, `data/`, `models/`, `results/part1/`,
`results/part2/`, `results/part3/`, `requirements.txt`, and `docs/`.
All 24 pre-existing uppercase configuration settings retain their original values.

Existing files modified for Part 4:

- `config.py`: four new settings on six appended lines; no original setting changed.
- `.gitignore`: only Part 4 checkpoint/pilot exclusions added.
- `README.md`: assignment clarification, Part 4 commands/results, and status documentation.

New work is in `part4_circuit/`, `results/part4/`, and `run_all.py`.
No commit or push has been performed. No remote comparison is implied by this local audit.
If teammates have edited the same shared documentation/config files remotely, merge those changes
before pushing. Individual generated result files have been checked to be below 100 MB.

This Windows checkout now has local `core.autocrlf=true`, matching its existing Windows Git setting.
Ubuntu Git otherwise reported line-ending-only changes throughout the unchanged upstream text files.
Both Windows and Ubuntu Git now agree that the protected paths are unchanged. No working files
were converted; this local Git metadata setting is not part of a commit or push.

Use `python run_all.py --part4-only` for this part. Running `python run_all.py` intentionally
regenerates and overwrites upstream generated datasets/models/results as part of the full pipeline;
it is a command for the later joint reproduction task, not a prerequisite for committing Part 4.

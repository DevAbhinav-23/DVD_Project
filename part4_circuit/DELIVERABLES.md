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
| Regenerating code in order with fixed seeds | `run_all.py --part4-only`; complete upstream sequence also provided by `run_all.py` | Part 4 path verified on the earlier run |
| Circuit report, comparison with gate accuracy, error analysis and limitations | `results/part4/report_part4.md`, condition/vector/corner summaries and plots | Met. The combined report is in `report/completed/project_report.tex`. |
| Up to 99% mean accuracy objective | Supply-only estimate with internal input-current correction achieves 98.597% (1.403% mean relative error) | Below objective |

The submission uses the four saved transistor models and the Part 3 rail-input NAND2 lookup.
It reports the prescribed plain sum alongside the internal input-current correction.

`results/part4/simulation_summary.json` records the final ngspice-47 sweep and its
logic checks. The saved `validation_summary.txt` and `op_dc_crosscheck.json` document
validation of the earlier Part 4 run, including 1,200 operating-point/DC comparisons.

## Final report and reproduction

- The [combined report](../report/completed/project_report.tex) covers Parts 1–4.
  The [Overleaf ZIP](../report/completed_report_overleaf.zip) contains the main document
  and its 12 figures. Compile it in Overleaf to check the PDF layout.
- The saved datasets use 5,000 uniform and 5,000 targeted samples per transistor case.
  The corrected supply-only estimate and the primary-input-current variant are both
  documented in the report.
- Run `python run_all.py --part4-only` to reproduce the circuit stage from the saved
  upstream results. Run `python run_all.py` to regenerate the upstream datasets,
  models, and gate results as well.

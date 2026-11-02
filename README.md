# DVD_Project
This is the repo which contains the main codebase for the Digital VLSID Course 2026 project:
**ML-Driven PVT Variation Aware Leakage Estimation.**

## Our assignment
| Item | Value |
|---|---|
| Model file | 22nm MGK (PTM metal-gate / high-k, BSIM4) |
| Nominal VDD | 0.9 V (sampled range 0.81 – 0.99 V) |
| Channel length L | 22 nm |
| Widths (NMOS and PMOS) | 22 nm – 176 nm (1 × Lmin to 8 × Lmin) |
| Test circuit | 8-bit parity checker |
| Target | Up to 99% mean accuracy (mean relative error of about 1%) |

All of these values live in **one shared config file** ([config.py](config.py)), along with the model file path, random seeds and simulator settings. Every script reads them from there; nobody hard-codes them.

## Repository layout
```
config.py               # shared settings for every part
requirements.txt        # pinned Python packages
models/22nm_MGK.pm      # assigned PTM model file
docs/                   # project specification (DVD_ML_PROJECT.pdf)
part1_dataset/
  netlists/             # example single-transistor netlists (nmos_on/off, pmos_on/off .cir)
  spice_utils.py        # build a sample netlist, run ngspice, read back Id, Ig, Is, Ib
  generate.py           # draw samples and simulate -> data/<case>.csv, data/<case>_targeted.csv
  validate.py           # KCL, sanity, coverage checks and trend plots -> results/part1/
part2_models/
  leakage_model.py      # features, log10|I| + sign target, saved CaseModel (load_case_model)
  train_compare.py      # 4 model families x 4 cases -> comparison table, chosen models, plots
  learning_curve.py     # chosen model vs training-set size (1k, 2k, 5k, 7k)
part3_gates/
  netlists/             # one runnable SPICE netlist per gate (inv, nand2, nor2, and2, or2 .cir)
  corners.py            # the 200 shared PVT corners -> data/corners.csv (also used by Part 4)
  gates.py              # gate topologies, gate netlists, batched ngspice runs, leakage formula
  simulate.py           # 18 cases x 200 corners in SPICE + oracle check -> results/part3/
  compare.py            # ML gate leakage vs SPICE -> results table, parity plot
data/                   # generated datasets (Part 1 CSVs) and the corner table
results/part1/          # Part 1 plots, KCL and coverage summaries, validation summary
results/part2/          # Part 2 tables, plots and the four saved models
results/part3/          # Part 3 SPICE records, predictions, gate table, oracle check, parity plot
```
Each later part gets its own `partN_*/` folder and writes its outputs under `results/partN/`.

## Setup
Requires ngspice (developed with ngspice-42) and Python 3.12.
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running Part 1
```
.venv/bin/python part1_dataset/generate.py    # ~25 s on 12 cores, writes both datasets to data/
.venv/bin/python part1_dataset/validate.py    # writes results/part1/
```
Both scripts use the fixed seeds in `config.py`, so a rerun reproduces byte-identical CSVs.
`generate.py --set uniform|targeted|both`, `--cases nmos_on ...`, `--n` and `--n-targeted` regenerate a subset.

### Datasets
| Files | Rows per case | Terminal voltages |
|---|---|---|
| `data/<case>.csv` (spec deliverable) | 10,000 | Vd, Vs uniform in [0, VDD], as the spec requires |
| `data/<case>_targeted.csv` | 5,000 | Where transistors sit inside static gates (below) |

VDD, temperature and the process parameters are drawn the same way in both; `<case>` is
`nmos_on`, `nmos_off`, `pmos_on` or `pmos_off`.

**Why the targeted set exists.** Inside a gate, an ON transistor carries only leakage, so its
|Vds| is a few mV or less, often with one terminal on its rail; OFF transistors have their terminals
at or near 0 and VDD. Uniform Vd, Vs almost never lands there (e.g. 3 of 10,000 PMOS ON rows have
|Vds| < 4 mV with a terminal on VDD), so models trained only on the uniform set are untested exactly
where Parts 3 and 4 use them. The targeted set fills those regions:
- **ON:** one terminal (drain or source, at random) on the device's own rail (VDD for PMOS, 0 for
  NMOS) half the time, else uniform; the other a log-uniform |Vds| of 0.1 µV–50 mV away, either sign.
- **OFF:** each of Vd, Vs exactly at 0 (30%), exactly at VDD (30%), 1 µV–100 mV off a rail (20%) or
  uniform (20%). If both land on the same rail, Vs is moved just off it (an all-terminals-equal OFF
  device never occurs in a gate).
- **W:** half at `config.GATE_W` (the gate width), half uniform.

The ranges come from circuit behaviour, not from the Part 3 SPICE results (those are evaluation-only).
[results/part1/coverage.csv](results/part1/coverage.csv) and `coverage.png` compare the two sets.

### Dataset notes (for Part 2)
- **Training:** train on both sets combined, and report test accuracy separately on a held-out slice of
  the targeted set: the uniform test set does not measure accuracy at the gate operating points.
- **Columns:** `vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj` (inputs) and `id, ig, is, ib` (targets).
- **Units:** SI (V, m, A, m⁻³ for ndep, m²/Vs for u0); `temp` in °C.
- **Signs:** current flowing *into* the terminal is positive. Signs do change within a case:
  in the ON cases Id and Is flip in about 50% of rows (whenever Vs > Vd), and in the OFF cases
  gate leakage is comparable to channel leakage, so Id is not simply −Is.
- **Range:** |I| spans about 1e-17 to 5e-4 A, so predict log10|I| and the sign separately.
- **Constant columns:** `vg` and `vb` are fixed per case (equal to `vdd` or 0), so they add no information within a case.
- **Numerical floor:** currents below about 1e-14 A are at SPICE's numerical floor. In the targeted OFF sets,
  where a device's terminals are within µV of its gate and body, Ig and Ib can be exactly 0 or ~1e-15 A noise
  (123 PMOS OFF rows); clip |I| at about 1e-14 A rather than fitting that noise.

### Validation results
All checks pass ([results/part1/validation_summary.txt](results/part1/validation_summary.txt)).
- **KCL:** a row passes when |Id+Ig+Is+Ib| ≤ 1e-3 · max|I| + 1e-13 A (relative plus absolute, like SPICE's
  reltol / abstol). 1e-3 is 10× below the 1% accuracy target; 0.1 pA is 0.1% of 0.1 nA, below every gate
  leakage we evaluate. All rows of both sets pass; the largest residual is 0.011 pA.
  The residual is a few-fA floor in the BSIM4 model's current bookkeeping: it appears only where every current is in the pA range, and it is unchanged when the solver tolerances are tightened 1000×.
- **Coverage:** e.g. PMOS ON rows with |Vds| < 4 mV and a terminal on VDD: 3 (uniform) vs 2,025 (targeted);
  NMOS OFF rows with terminals on opposite rails: 5 vs 1,471.
- **Trends (controlled sweeps at nominal, |Vds| = VDD):** OFF current rises with temperature and falls as |vth0| grows; |Ig| falls as toxe grows.

## Running Part 2
```
.venv/bin/python part2_models/train_compare.py    # ~1 h on 4 cores, writes results/part2/
.venv/bin/python part2_models/evaluate_test.py    # per-row SPICE vs ML on both test sets
.venv/bin/python part2_models/learning_curve.py   # ~40 min, needs train_compare.py first
```
`train_compare.py --fast` runs one hyperparameter setting per family as a quick smoke test.

### Method
- **Data:** `data/<case>.csv` (uniform) and `data/<case>_targeted.csv` (gate operating points) are each
  split 70 / 15 / 15 with `SEEDS["split"]` and combined for training and validation. The two test slices are
  reported separately. Row indices are saved in `results/part2/splits/<case>_<set>_<split>_idx.csv`.
- **Target:** each current is predicted as `sign(I) × 10^y` with `y = log10|I|`, clipped at 1e-15 A
  (SPICE's numerical floor; rows below it are left out of the error metrics). Where a terminal's sign is
  mixed in training (Id and Is), a LightGBM classifier predicts it for every family: the sign flips only
  in a narrow band near Vd ≈ Vs, where the MLP classifier was clearly worse (94–95% vs 99–100%).
- **Features:** the 12 inputs plus Vds, |Vds|, log10|Vds|, Vgs, Vgd, Vbs, Vbd, gate and body voltage
  relative to min/max(Vd, Vs), 1/kT, logs of W, toxe, ndep and u0, and the subthreshold exponents
  (Vgs − |vth0|)/kT. log10|Vds| matters for ON devices near Vds = 0, where the channel current is
  proportional to Vds. Columns constant within a case are dropped.
- **Model types:** degree-2/3 polynomial ridge (baseline), Random Forest, LightGBM, and an MLP
  (3 × 64 tanh, full-batch L-BFGS). The MLP and ridge are one model with four outputs; the tree
  models have one model per terminal. XGBoost is also available via `--families xgboost`.
- **Selection:** per case, the family with the lowest validation mean over terminals of
  (median + 95th-percentile relative error) / 2. Gradient boosting uses the validation set for early stopping.

### Results
The MLP wins every case. Validation set (both datasets), mean over the four terminals
(median / 95th-percentile relative error):

| Case | Poly ridge | Random Forest | LightGBM | **MLP** |
|---|---|---|---|---|
| NMOS ON | 10.9% / 58% | 11.5% / 53% | 4.3% / 25% | **2.3% / 22%** |
| NMOS OFF | 15.2% / 76% | 5.9% / 37% | 3.1% / 25% | **1.5% / 7.7%** |
| PMOS ON | 9.0% / 53% | 11.7% / 55% | 4.1% / 23% | **2.3% / 23%** |
| PMOS OFF | 15.8% / 81% | 6.2% / 37% | 3.0% / 22% | **1.6% / 8.3%** |

Test set, chosen MLP, mean over terminals (`results/part2/test_metrics.md`, `test_summary.csv`):

| Case | Uniform test: median / p95 | Targeted test: median / p95 |
|---|---|---|
| NMOS ON | 1.9% / 7.5% | 4.5% / 52% |
| NMOS OFF | 1.4% / 7.1% | 2.0% / 12% |
| PMOS ON | 1.9% / 7.0% | 4.8% / 54% |
| PMOS OFF | 1.5% / 7.0% | 1.9% / 12% |

- **Before the targeted data**, the same models were trained on the uniform set only. They scored
  1.1–1.3% on the uniform test but 120–180% median error on the targeted ON test points, with the
  sign of Id and Is right in only 42–72% of them.
- **The remaining large targeted errors** are Id and Is of ON devices at |Vds| of µV to mV, where the
  channel current passes through zero and partly cancels the gate current (sign right in 98–99%).
  Part 3's leakage formula does not use those currents (it solves them by KCL). The Ig and Ib of the same
  devices, which Part 3 does use, are at 2.1–2.6% median error.
- **Uniform accuracy** dropped from 1.1–1.3% to 1.4–1.9% median, since one network of the same size now covers
  the targeted region too.

**Learning curve** (`results/part2/learning_curve.csv`, `plots/learning_curve.png`; still from the
uniform-only training): 1k training rows give 2.0–3.4% median and 28–64% 95th-percentile error, 2k rows
reach 1.2–1.4% median, and from 5k to 7k both level off. It has not been re-run with the targeted data.

### Using the models (Parts 3 and 4)
```python
sys.path.insert(0, "part2_models")
from leakage_model import load_case_model
m = load_case_model("results/part2/models/nmos_off.joblib")
currents = m.predict(df)   # df with the 12 input columns -> DataFrame id, ig, is, ib in A
```

## Running Part 3
```
.venv/bin/python part3_gates/simulate.py   # ~1 min on 16 cores, 3,600 SPICE runs + oracle check
.venv/bin/python part3_gates/compare.py    # ~5 s, ML prediction, gate table and parity plot
```
`simulate.py` draws `data/corners.csv` (seed `SEEDS["corners"]`) on first use and reuses it after that; Part 4 reads the same file through `part3_gates/corners.py:load_corners`.

### Method
- **Gates:** static CMOS INV, NAND2, NOR2, and AND2 / OR2 as NAND2 / NOR2 + INV in one netlist,
  using the 22nm MGK NMOS and PMOS cards with the corner's vth0, toxe, ndep, u0, xj. The spec gives
  no gate sizing, so every transistor is minimum size, W = L = 22 nm (`GATE_W` in `config.py`).
  All NMOS in a gate share the corner's NMOS parameters, all PMOS its PMOS parameters.
- **SPICE records:** every transistor terminal is wired through its own 0 V source, so each run
  records all terminal currents, the supply and input-source currents, and the output and internal
  node voltages (x, y, and the NAND / NOR output inside AND2 / OR2). One row per run in
  `results/part3/spice_gates.csv`.
- **ML prediction:** each transistor's (Vd, Vg, Vs, Vb) comes from the SPICE node voltages, inputs
  are exactly 0 or VDD, and the ON / OFF model is picked from the gate voltage (above or below VDD/2).
  Vg is passed to the model at the rail it was trained at; feeding the recorded Vg instead is
  reported as a variant.
- **Leakage** (`part3_gates/gates.py:leakage`, the same formula for SPICE and ML): the current
  drawn from VDD, computed **without any ON transistor's drain or source current**. Inside a gate an
  ON transistor sits at |Vds| ≈ 0 and only carries the leakage of the rest of the gate; the transistor
  models are unreliable there (the PMOS ON model gets Is's sign wrong in every run). So:
  - each ON transistor's channel is one unknown t (its drain current); its source current follows from
    its own KCL, is = −(ig + ib) − t. Its gate and body currents are used as predicted;
  - OFF transistors use all four predicted currents;
  - KCL at every internal node (out, x, y, nand_out, nor_out) solves the unknowns, and the VDD current
    is the sum at the VDD node. Only combinations KCL determines may enter (e.g. the sum of two
    parallel ON PMOS); the function raises an error otherwise.

  `leakage_vdd_terminals` keeps the previous formula (sum of every terminal current at VDD) for comparison.
- **Oracle check** (`results/part3/oracle_check.txt`): on the SPICE terminal currents the formula
  reproduces −i(Vsupply) to 7e-7, below the 1e-6 limit (the previous formula: 9e-16). The difference
  is each ON transistor's own KCL residual in SPICE, the same few-fA floor as in the Part 1 KCL check,
  relative to ~10 nA of gate leakage.

### Results
Over all 3,600 gate runs, with the current Part 2 models (retrained on uniform + targeted data):
**median error 1.5%, 95th percentile 4.9%, mean 1.9%, bias −0.7%** (`results/part3/gate_table.md`,
`plots/gate_parity.png`). Every case has the right sign; the per-case median error is 1.1–2.7%.
With the earlier uniform-only models it was 4.4% median, 18% p95.
- **Formula change:** with the previous formula (VDD terminals) the same models gave a 132% median
  error, wrong-signed in the 14 cases with an ON PMOS on VDD (variants table, last column).
- **Retraining on the targeted data** (OFF devices at the rails, ON devices at Vds ≈ 0) cut the
  gate error from 4.4% to 1.5% median and from 18% to 4.9% p95.
- **Least accurate:** NOR2 10 (median 2.7%, p95 6.9%) and NOR2 11 (2.4%, 8.1%), where the leakage is the
  smallest (0.7–9 nA) and flows through series OFF PMOS; NAND2 00 (2.0%) is next.
- **AND2 / OR2 inverter input:** the internal NAND / NOR output is at most 1.8% of VDD off the rail.
  Feeding the recorded Vg instead of the rail value changes the median error by at most 1.1 points (OR2 00).
- **Input-source current (TA question 3):** counting the gate current drawn from inputs held at VDD
  gives a 1.4% median error (variants table of `gate_table.md`).

## Conventions (fix these before writing code)
- **Current sign:** current flowing *into* a terminal is positive. The KCL check is then `Id + Ig + Is + Ib ≈ 0`.
- **Leakage definition:** gate and circuit leakage = static current drawn from the VDD supply. On the ML side it is computed by KCL from the OFF transistors' currents and every transistor's gate and body currents, never from an ON transistor's drain or source current (`part3_gates/gates.py:leakage`). SPICE and ML must use exactly the same definition.
- **Gate current through the inputs:** input sources at VDD also supply gate-tunnelling current. Whether that counts as leakage is an open TA question (see below). Whatever we decide is applied to both SPICE and ML.
- **Error metric:** relative error `|ML − SPICE| / |SPICE|`. Bias = signed median of `(ML − SPICE) / SPICE`.
- **Netlist options:** every netlist (transistor, gate and circuit) includes
  `.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`.
- **Shared corner table:** the 200 PVT corners are generated **once**, saved to a file and reused for every gate and for the parity circuit. Each corner holds VDD, temperature, one NMOS parameter set and one PMOS parameter set.

## Open questions for the TA
1. Does the parity checker have 8 inputs (parity generator, 256 vectors) or 9 inputs (8 data bits + parity bit, 512 vectors)?
2. Should the ML side solve the internal node voltages itself (by KCL on the ML models), or only use the SPICE-recorded voltages? Section 5 asks for "internal node voltages from both".
3. Does gate-tunnelling current drawn through the input sources count as leakage?

---

## Part 1 — Generate transistor datasets
Goal: Create training data using SPICE.
1. Inspect the 22nm MGK model card:
   - confirm that `vth0, toxe, ndep, u0, xj` exist for both NMOS and PMOS, and note their nominal values;
   - check that gate tunnelling is enabled (`igcmod` / `igbmod`). If it is off, Ig is about zero and the "gate current vs toxe" plot will be flat.
2. Create four single-transistor netlists: NMOS ON, NMOS OFF, PMOS ON and PMOS OFF. Every terminal gets its own voltage source.
3. For each case, draw 10,000 samples with fixed seeds. Every parameter is drawn independently:
   - VDD first, uniform over 0.81 – 0.99 V;
   - Vd and Vs, each uniform over 0 – VDD;
   - W, uniform over 22 – 176 nm;
   - temperature, uniform over −40 – 125 °C;
   - `vth0, toxe, ndep, u0, xj`, each uniform over nominal ±10%. NMOS and PMOS use separate draws. PMOS vth0 is negative, so apply the ±10% as a scale factor to keep the sign.
   - Vg and Vb are fixed by the case and use the **sampled** VDD:

     | Case | Vg | Vb |
     |---|---|---|
     | NMOS ON | VDD | 0 |
     | NMOS OFF | 0 | 0 |
     | PMOS ON | 0 | VDD |
     | PMOS OFF | VDD | VDD |
4. Run SPICE (`.op`) for every sample and extract `Id, Ig, Is, Ib`. Run samples in batches or in parallel rather than starting one simulator process per sample.
5. Save four CSV files with the columns `vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj, id, ig, is, ib`.
6. Validate the data:
   - run the KCL check for each case;
   - make the three required trend plots: OFF current vs temperature, OFF current vs vth0, and gate current vs toxe.

   Make each trend plot twice: once from the random dataset, and once from a controlled sweep that changes one parameter while holding the others at nominal. The controlled sweep shows the trend clearly.
7. Hand Member 2 a pilot set of about 1k samples early so model work can begin before the full data is ready.

Output: four CSV datasets of 10,000 samples each, the KCL check, the trend plots and the example netlists.

⬇️
## Part 2 — Train and select ML models
Goal: Predict transistor currents without running SPICE for every new prediction.
1. Separate the inputs (X) from the four terminal currents (Y).
2. Split each dataset 70 / 15 / 15 into train, validation and test sets with a fixed seed (80 / 10 / 10 is also allowed).
3. Preprocess:
   - targets: predict `log10|I|`, because the currents span many orders of magnitude;
   - sign changes: Ig, Ib and Is can change sign, so handle the sign with a classifier or a signed log scaling;
   - extra features: Vgs, Vds, Vbs, 1/T, and possibly predict I/W, since current scales roughly with W.
4. Train four model types on each case:
   - polynomial or ridge regression as a baseline;
   - Random Forest or Extra Trees;
   - gradient boosting (XGBoost or LightGBM);
   - an MLP.
5. Compare the models on the validation set using R² (on the log scale), median relative error and 95th-percentile relative error. This produces the 4 model types × 4 cases comparison table.
6. Select the best model for each case and report its test-set median and 95th-percentile errors. Make a predicted-vs-SPICE plot for each case.
7. Save the four chosen models, one file per case. A file may wrap one sub-model per current.
8. Plot a learning curve: test accuracy against dataset size (1k, 2k, 5k, 10k). The spec rewards the smallest dataset that still gives high accuracy.

Output: four selected transistor-case models, the comparison table and the evaluation results.

⬇️
## Part 3 — Validate at the logic-gate level
Goal: Check whether the transistor models can accurately estimate gate leakage.
1. Write static CMOS SPICE netlists for INV, NAND2, NOR2, AND2 and OR2:
   - AND2 = NAND2 + INV and OR2 = NOR2 + INV, each simulated as **one complete netlist**;
   - internal nodes: x (between the series NMOS of NAND2) and y (between the series PMOS of NOR2);
   - all NMOS in a gate share the corner's NMOS parameters, and all PMOS share its PMOS parameters.
2. Simulate every input combination at the 200 shared corners, with inputs at exactly 0 or VDD. That is 18 gate-input cases × 200 = 3,600 simulations.
3. Record the SPICE leakage, the internal node voltages, the output voltage and **every transistor's terminal currents**.
4. **Oracle check:** run the SPICE transistor currents through the leakage-summing formula and confirm it reproduces the SPICE leakage. This catches formula or sign mistakes before any ML error enters.
5. ML prediction:
   - build each transistor's (Vd, Vg, Vs, Vb) from the recorded node voltages;
   - pick the ON or OFF model from the gate voltage (for example, an NMOS with its gate at VDD uses NMOS ON);
   - predict the currents and combine them into the gate leakage by KCL, without the drain/source currents of ON transistors (see Running Part 3 → Method).

   Optional: also solve the internal nodes with the ML models by KCL (depends on TA question 2).
6. Compare ML against SPICE. For each of the 18 cases, report the SPICE median, ML median, bias, median error and 95th-percentile error. Plot ML against SPICE for every gate simulation on log axes.
7. Expected weak spot: in AND2 and OR2 the inverter's input is the internal NAND or NOR output, which is not exactly 0 or VDD. The models were trained with Vg exactly at 0 or VDD. Discuss this in the error analysis.

Output: gate-level leakage predictions, the results table and the parity plot.

⬇️
## Part 4 — Validate the complete circuit (8-bit parity checker)
Goal: Estimate the parity checker's leakage from the gate models.
1. **Circuit structure:** an XOR tree of 7 XOR2s, with each XOR built from 4 NAND2s. That is 28 NAND2s and 112 transistors, and only the NAND2 gate model is needed. The full SPICE netlist must use **exactly the same** gate breakdown as the ML sum.
2. Simulate the full netlist for every input vector at the same 200 corners: 256 × 200 = 51,200 simulations, or 512 × 200 if the TA confirms 9 inputs. Loop over the vectors inside one netlist per corner (a `.control` loop or `alterparam`) and run the corners in parallel.
3. Record the SPICE leakage for each (vector, corner).
4. Run a logic simulation of the tree to get the logic inputs of all 28 gates for each vector.
5. Gate model = a function of (gate type, inputs, corner) that returns the predicted leakage. Its internal node voltages come from the Part B record for the same corner and input pattern, or from the ML KCL solve. Gate inputs are taken as exactly 0 or VDD.
6. Sum the 28 gate leakages to get the predicted circuit leakage.
7. Compare against SPICE using the same metrics as the gate table, plus a log-log parity plot. Then compare this accuracy with the gate-level accuracy.
8. Known limitation for the report: inside each XOR, one NAND output drives two gates. The ML sum ignores this loading and any non-ideal logic levels, so expect somewhat lower accuracy than at the gate level.

Output: circuit-level leakage estimates and their accuracy relative to SPICE.

⬇️
## Part 5 — Prepare the final deliverables
Goal: Make the work reproducible and document the results.
1. Organize the SPICE netlists, CSV datasets, ML models and scripts.
2. Provide a single `run_all` that regenerates everything, in order, from the model file using the fixed seeds.
3. Pin the Python package versions and record the simulator and its version.
4. Compile the model comparison table, the chosen-model test metrics, the gate table and the circuit table.
5. Include all plots: KCL check, trend plots, predicted-vs-SPICE plots, the gate parity plot and the circuit parity plot.
6. Write the report:
   - **Setup:** model file, VDD, circuit, simulator and version.
   - **Data generation:** sampling, netlist construction, data split and data-check results.
   - **Models:** the four model types tried, their hyperparameters and preprocessing, the comparison table and the reason for each final choice.
   - **Gate results:** most and least accurate gates and input combinations.
   - **Circuit results:** circuit accuracy compared with gate accuracy.
   - **Error analysis:** where the largest errors occur (which case, gate, input pattern or corner, e.g. high temperature or low vth0) and why.
   - **Limitations and improvements.**

Output: complete code, saved models, datasets, plots and the final report.

---

## Team responsibilities
| Member | Primary responsibility | Can start immediately on |
|---|---|---|
| Member 1 | Part 1: transistor datasets | Model card inspection, netlist templates, sampling script |
| Member 2 | Part 2: ML training and model selection | Training pipeline on the pilot dataset |
| Member 3 | Part 3: gate-level validation | Gate netlists, shared corner table, oracle check |
| Member 4 | Part 4: circuit-level validation and integration | Parity netlist, logic simulator, `run_all`, shared config |

Shared items with a single owner: the config file (Member 4), the corner table (Member 3), and the sign convention and leakage definition (agreed by everyone before coding).

The key idea: start with individual transistors, learn their behaviour with ML, use those models to estimate gate leakage, and finally combine the gate estimates to predict the leakage of the complete circuit.

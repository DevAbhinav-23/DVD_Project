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
data/                   # generated datasets (Part 1 CSVs)
results/part1/          # Part 1 plots and KCL summary
```
Each later part gets its own `partN_*/` folder and writes its outputs under `results/partN/`.

## Setup
Requires ngspice (developed with ngspice-42) and Python 3.12.
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Conventions (fix these before writing code)
- **Current sign:** current flowing *into* a terminal is positive. The KCL check is then `Id + Ig + Is + Ib ≈ 0`.
- **Leakage definition:** gate and circuit leakage = static current drawn from the VDD supply. On the ML side this is the sum of the predicted currents of every transistor terminal tied to VDD. SPICE and ML must use exactly the same definition.
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
   - predict the currents and sum them into the gate leakage.

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

# DVD_Project
This is the repo which contains the main codebase for the Digital VLSID Course 2026 project:
**ML-Driven PVT Variation Aware Leakage Estimation.**

The idea: simulate single transistors in SPICE, learn their terminal currents with ML, use those
models to estimate the leakage of logic gates, and finally add up gate estimates to predict the
leakage of a complete circuit (8 data bits plus 1 parity bit: 9 inputs).

## Status
| Part | What | State | Headline result |
|---|---|---|---|
| 1 | Transistor datasets (SPICE) | **Done** | 10,000 rows per case: 5,000 uniform + 5,000 targeted, with junction areas, all checks pass |
| 2 | ML models per transistor case | **Done** | MLP chosen for 3 cases, LightGBM for PMOS ON; 2.1–5.0% median test error (uniform) |
| 3 | Gate-level validation | **Done** | 3,600 gate runs: **1.3% median, 4.7% p95 error** vs SPICE |
| 4 | Circuit-level validation (parity checker) | **Done** | 102,400 runs; corrected error: **1.14% median, 3.63% p95, 1.40% mean** |
| 5 | Reproduction and report | **Done** | `run_all.py`, combined LaTeX report, and Overleaf package are available |

For Part 4 implementation details, read [Conventions](#conventions), the Part 3 results, and
[Part 4](#part-4--circuit-level-validation).

## Results at a glance
**Mean error** (mean of |ML − SPICE| / |SPICE|):

| Level | Mean error | Median | p95 |
|---|---|---|---|
| Transistor models, uniform test (mean of 4 cases × 4 terminals) | 4.8% | 2.1–5.0% per case | 8.2–21% per case |
| Transistor models, targeted test (gate operating points) | 8.0% | 3.3–6.7% per case | 14–51% per case |
| **Gates, all 3,600 runs (18 cases × 200 corners)** | **1.8% (98.2% mean accuracy)** | **1.3%** | **4.7%** |
| Gates per type: AND2 / OR2 / INV / NAND2 / NOR2 | 1.2% / 1.5% / 1.7% / 1.8% / 2.8% | 0.9% / 1.3% / 1.4% / 1.4% / 1.9% | 3.2% / 3.7% / 4.5% / 4.6% / 6.9% |
| **Nine-input parity circuit, corrected supply estimate (102,400 runs)** | **1.40% (98.60% mean accuracy)** | **1.14%** | **3.63%** |
| Circuit, plain gate sum (spec baseline) | 24.76% | 21.63% | 54.08% |

**Highest error:**
- **Gate level: NOR2.** NOR2 `10` (A = 1, B = 0) has the highest median error (3.3%);
  NOR2 `11` has the highest mean and p95 (4.5%, 9.3%). In both, the whole leakage is the Is of one OFF PMOS whose drain
  sits at the stack node y (0.15–0.2 or 0.9 × VDD), a region with only ~20 training rows. NAND2 `10`
  (1.7% median) is next. Apart from one run, the worst runs are 14–15% off (NOR2 11 and NOR2 10 at cold
  corners). **One run has the wrong sign:** NOR2 `11` at corner 76
  (−38 °C), the smallest leakage of all 3,600 runs (1.6e-11 A). There the OFF PMOS Is is the difference
  of a channel current (−3.3e-11 A) and a gate current (+1.7e-11 A) that nearly cancel; the model gets
  the magnitude within 1% but the sign wrong (187% relative error, 3e-11 A absolute).
- **Transistor level: the ON models (NMOS ON, PMOS ON) on the targeted test**, 10.2–11.4% mean,
  4.5–6.7% median, 40–51% p95. The error is all in Id and Is at |Vds| of µV to mV (16–18% mean each),
  where the channel current crosses zero. The gate leakage formula never uses those two currents; Ig and
  Ib of the same devices are at 1.7–6% median.
- **Lowest error:** AND2 / OR2 (0.9–1.2% median per input case).

## Handoff in short
**Done (Parts 1–3):**
- SPICE datasets for the 4 transistor cases (5k uniform + 5k targeted = 10k rows each), validated.
  Re-simulated on 2026-11-10 with drain/source junction areas (AD = AS = W × 2 Lmin, same samples), then
  Part 2 retrained from scratch and Parts 3–4 re-evaluated with the new models.
- 4 model types compared per case; the MLP chosen and saved (`results/part2/models/*.joblib`).
- Learning curve over 1k / 2k / 5k / 7k training rows.
- 5 gates × all input cases × 200 shared corners simulated in SPICE, oracle check passed, ML gate
  leakage computed and compared (1.3% median, 1.8% mean error).

**Part 4 implementation:** `part4_circuit/` builds a nine-input parity checker from 32 NAND2s,
checks all 512 logic vectors, simulates the complete circuit at the existing 200 corners, and
compares plain and input-current-corrected ML gate sums. `run_all.py` integrates all stages.
See [Part 4](#part-4--circuit-level-validation) for commands and outputs.

## Our assignment
| Item | Value |
|---|---|
| Model file | 22nm MGK (PTM metal-gate / high-k, BSIM4) |
| Nominal VDD | 0.9 V (sampled range 0.81 – 0.99 V) |
| Channel length L | 22 nm |
| Widths (NMOS and PMOS) | 22 nm – 176 nm (1 × Lmin to 8 × Lmin) |
| Test circuit | 8 data bits + 1 even-parity bit (9 inputs) |
| Target | Up to 99% mean accuracy (mean relative error of about 1%) |

All of these values live in **one shared config file** ([config.py](config.py)), along with the model
file path, random seeds, corner count, gate widths and simulator settings. Every script reads them
from there; nobody hard-codes them.

## Conventions
Every part follows these. Part 4 must too, or its numbers are not comparable with Part 3.
- **Current sign:** current flowing *into* a terminal is positive. The KCL check is then `Id + Ig + Is + Ib ≈ 0`.
- **Leakage definition:** gate and circuit leakage = static current drawn from the VDD supply,
  `-i(vsupply)` in SPICE. Current drawn from the input sources is **not** included in the main result
  (TA question 3; reported as a variant). SPICE and ML must use exactly the same definition.
- **ML leakage formula:** computed by KCL from the OFF transistors' currents and every transistor's
  gate and body currents, never from an ON transistor's drain or source current
  (`part3_gates/gates.py:leakage`, explained in Part 3).
- **Error metric:** relative error `|ML − SPICE| / |SPICE|`, reported as median, 95th percentile (p95)
  and mean. Bias = signed median of `(ML − SPICE) / SPICE`.
- **Netlist options:** every netlist (transistor, gate and circuit) includes
  `.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9` (`config.SPICE_OPTIONS`).
- **Gate sizing:** every transistor in a gate is minimum size, W = L = 22 nm (`config.GATE_W`). The spec
  gives no sizing. Some training samples use this width, so changing it means regenerating the
  targeted data and retraining.
- **Shared corner table:** the 200 PVT corners are generated **once** (`data/corners.csv`) and reused for
  every gate and for the parity circuit. Each corner holds VDD, temperature, one NMOS parameter set
  and one PMOS parameter set.

## Decisions and open questions
| # | Question | Status |
|---|---|---|
| 1 | Does the parity checker have 8 inputs or 9 inputs? | **Decided by the Part 4 owner:** 8 data bits + 1 parity bit, 512 vectors |
| 2 | Should the ML side solve the internal node voltages itself, or use the SPICE-recorded ones? | **Decided:** gate models use Part 3 SPICE-recorded voltages; circuit ML uses only the gate lookup and Boolean logic, with no circuit-SPICE voltages |
| 3 | Does gate-tunnelling current drawn through the input sources count as leakage? | **Open.** Main result excludes it; the variant including it is reported |
| 4 | What sampling did the final run use? | 5,000 uniform and 5,000 targeted rows per case. The brief specifies uniform sampling for the initial dataset. |

## Repository layout
```
config.py               # shared settings for every part
requirements.txt        # pinned Python packages
models/22nm_MGK.pm      # assigned PTM model file
docs/                   # project specification (DVD_ML_PROJECT.pdf)
part1_dataset/
  netlists/             # example single-transistor netlists (nmos_on/off, pmos_on/off .cir)
  spice_utils.py        # model card with corner parameters, run ngspice, read back Id, Ig, Is, Ib
  generate.py           # draw samples and simulate -> data/<case>.csv (10k rows: 5k uniform + 5k targeted)
  validate.py           # KCL, sanity, coverage checks and trend plots -> results/part1/
part2_models/
  leakage_model.py      # features, log10|I| + sign target, saved CaseModel (load_case_model)
  train_compare.py      # 4 model families x 4 cases -> comparison table, chosen models, plots
  evaluate_test.py      # per-row SPICE vs ML on both test sets
  learning_curve.py     # chosen model vs training-set size (1k, 2k, 5k, 7k)
part3_gates/
  netlists/             # one runnable SPICE netlist per gate (inv, nand2, nor2, and2, or2 .cir)
  corners.py            # the 200 shared PVT corners -> data/corners.csv (also used by Part 4)
  gates.py              # gate topologies, gate netlists, batched ngspice runs, leakage formula
  simulate.py           # 18 cases x 200 corners in SPICE + oracle check -> results/part3/
  compare.py            # ML gate leakage vs SPICE -> results table, parity plot
part4_circuit/
  circuit.py            # shared ordered NAND graph, logic evaluation, transistor netlists
  verify.py             # exhaustive 512-vector logic and topology checks
  test_circuit.py       # current ownership, missing-data and wrong-logic checks
  simulate.py           # 512 vectors x 200 corners, resumable per-corner SPICE batches
  compare.py            # plain/corrected hierarchical sums, diagnostics, tables and plots
run_all.py              # regenerate all stages, or --part4-only using saved upstream artifacts
data/                   # generated datasets (Part 1 CSVs) and the corner table
results/part1/          # Part 1 plots, KCL and coverage summaries, validation summary
results/part2/          # Part 2 tables, plots, splits and the four saved models
results/part3/          # Part 3 SPICE records, predictions, gate table, oracle check, parity plot
results/part4/          # circuit netlist, compressed records/predictions, metrics, plots and metadata
```
Each later part gets its own `partN_*/` folder and writes its outputs under `results/partN/`.

## Setup
Requires ngspice and Python 3.12. The saved dataset and gate runs used ngspice-42. The
saved parity circuit sweep used ngspice-47.
On Ubuntu/WSL2: `sudo apt-get install ngspice python3-venv python3-pip`.
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running everything done so far
```
.venv/bin/python part1_dataset/generate.py        # ~25 s on 12 cores, both datasets -> data/
.venv/bin/python part1_dataset/validate.py        # -> results/part1/
.venv/bin/python part2_models/train_compare.py    # ~1 h on 4 cores -> results/part2/ (models included)
.venv/bin/python part2_models/evaluate_test.py    # per-row SPICE vs ML on both test sets
.venv/bin/python part2_models/learning_curve.py   # ~80 min, needs train_compare.py first
.venv/bin/python part3_gates/simulate.py          # ~1 min on 16 cores, 3,600 SPICE runs + oracle check
.venv/bin/python part3_gates/compare.py           # ~5 s, ML gate leakage, gate table, parity plot
.venv/bin/python run_all.py --part4-only         # verify, circuit SPICE, hierarchical comparison
```
All scripts use the fixed seeds in `config.py`, so a rerun reproduces the same data. The saved models
and results are committed, so Part 4 does **not** need to rerun Parts 1–3.

---

## Part 1 — Transistor datasets (done)
**Goal:** training data for four transistor cases (NMOS ON, NMOS OFF, PMOS ON, PMOS OFF) from SPICE.

### What was done
- **Netlists:** one single-transistor netlist per case, every terminal driven by its own source
  (`part1_dataset/netlists/`). Samples run in batches inside one ngspice process per worker.
- **Sampling (uniform set, the spec deliverable):** per row, independently: VDD uniform 0.81–0.99 V;
  Vd, Vs uniform in [0, VDD]; W uniform 22–176 nm; temperature uniform −40–125 °C; `vth0, toxe, ndep,
  u0, xj` each uniform over nominal ±10% (separate NMOS / PMOS draws; PMOS vth0 scaled to keep its
  sign). Vg and Vb are fixed by the case, using the sampled VDD:

  | Case | Vg | Vb |
  |---|---|---|
  | NMOS ON | VDD | 0 |
  | NMOS OFF | 0 | 0 |
  | PMOS ON | 0 | VDD |
  | PMOS OFF | VDD | VDD |

- **Targeted set (extra):** 5,000 more rows per case at the voltages transistors actually see inside
  static gates (below).

One file per case, `data/<case>.csv`, 10,000 rows:

| Rows | Count | Terminal voltages |
|---|---|---|
| 0 – 4,999 (uniform) | 5,000 (`N_SAMPLES`) | Vd, Vs uniform in [0, VDD], as the spec requires |
| 5,000 – 9,999 (targeted) | 5,000 (`N_TARGETED`) | Where transistors sit inside static gates |

The row order is how the two parts are told apart (no extra column, so the file keeps exactly the
spec's columns). Read it with `part2_models/train_compare.py:load_datasets(case)`, which returns both
parts and checks the row count against `config.py`.

Columns: `vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj` (inputs) and `id, ig, is, ib`
(targets). Units are SI (V, m, A, m⁻³ for ndep, m²/Vs for u0); `temp` in °C. `<case>` is `nmos_on`,
`nmos_off`, `pmos_on` or `pmos_off`.

**Why the targeted set exists.** Inside a gate, an ON transistor carries only leakage, so its
|Vds| is a few mV or less, often with one terminal on its rail; OFF transistors have their terminals
at or near 0 and VDD. Uniform Vd, Vs almost never lands there (e.g. 1 of 5,000 uniform PMOS ON rows has
|Vds| < 4 mV with a terminal on VDD), so models trained only on the uniform set are untested exactly
where Parts 3 and 4 use them. The targeted set fills those regions:
- **ON:** one terminal (drain or source, at random) on the device's own rail (VDD for PMOS, 0 for
  NMOS) half the time, else uniform; the other a log-uniform |Vds| of 0.1 µV–50 mV away, either sign.
- **OFF:** each of Vd, Vs exactly at 0 (30%), exactly at VDD (30%), 1 µV–100 mV off a rail (20%) or
  uniform (20%). If both land on the same rail, Vs is moved just off it (an all-terminals-equal OFF
  device never occurs in a gate).
- **W:** half at `config.GATE_W` (the gate width), half uniform.

The ranges come from circuit behaviour, not from the Part 3 SPICE results (those are evaluation-only).
`generate.py --cases nmos_on ...` regenerates a subset; the sizes come from `N_SAMPLES` and `N_TARGETED` in `config.py`.

### Results
All checks pass ([results/part1/validation_summary.txt](results/part1/validation_summary.txt)).
- **KCL:** a row passes when |Id+Ig+Is+Ib| ≤ 1e-3 · max|I| + 1e-13 A (relative plus absolute, like SPICE's
  reltol / abstol). All rows of both sets pass; the largest residual is 0.011 pA. The residual is a few-fA
  floor in the BSIM4 model's current bookkeeping: it appears only where every current is in the pA range,
  and it is unchanged when the solver tolerances are tightened 1000×.
- **Coverage** (`results/part1/coverage.csv`, `coverage.png`): e.g. PMOS ON rows with |Vds| < 4 mV and a
  terminal on VDD: 1 (uniform) vs 2,025 (targeted); NMOS OFF rows with terminals on opposite rails: 1 vs 1,471.
- **Trends** (`off_current_vs_temp.png`, `off_current_vs_vth0.png`, `gate_current_vs_toxe.png`, each from
  the random data and a controlled sweep at nominal): OFF current rises with temperature and falls as
  |vth0| grows; |Ig| falls as toxe grows.

### Data notes
- **Signs change within a case:** in the ON cases Id and Is flip in about 50% of rows (whenever Vs > Vd);
  in the OFF cases gate leakage is comparable to channel leakage, so Id is not simply −Is.
- **Range:** |I| spans about 1e-17 to 5e-4 A, so the models predict log10|I| and the sign separately.
- **Numerical floor:** currents below about 1e-14 A are at SPICE's numerical floor (e.g. Ig, Ib of
  targeted OFF devices whose terminals are within µV of their gate and body).

---

## Part 2 — ML models (done)
**Goal:** predict a transistor's four terminal currents without running SPICE.

### Method
- **Data:** the uniform and targeted parts of `data/<case>.csv` (`load_datasets`) are each split 70 / 15 / 15 with
  `SEEDS["split"]` and combined for training and validation. The two test slices are reported separately.
  Row indices are saved in `results/part2/splits/<case>_<set>_<split>_idx.csv`.
- **Target:** each current is predicted as `sign(I) × 10^y` with `y = log10|I|`, clipped at 1e-15 A.
  Where a terminal's sign is mixed in training (Id and Is), a LightGBM classifier predicts it (99–100%
  correct, vs 94–95% for an MLP classifier).
- **Features:** the 12 inputs plus Vds, |Vds|, log10|Vds|, Vgs, Vgd, Vbs, Vbd, gate and body voltage
  relative to min/max(Vd, Vs), 1/kT, logs of W, toxe, ndep and u0, and the subthreshold exponents
  (Vgs − |vth0|)/kT. Columns constant within a case are dropped.
- **Model types:** degree-2/3 polynomial ridge (baseline), Random Forest, LightGBM, and an MLP
  (3 × 64 tanh, full-batch L-BFGS). Hyperparameter grids in `results/part2/hyperparameters.json`.
- **Selection:** per case, the family with the lowest validation mean over terminals of
  (median + p95 relative error) / 2.

### Results
The MLP wins NMOS ON, NMOS OFF and PMOS OFF; LightGBM wins PMOS ON. Validation set (both datasets), mean over the four terminals, median / p95
relative error (`results/part2/comparison_table.md`):

| Case | Poly ridge | Random Forest | LightGBM | MLP |
|---|---|---|---|---|
| NMOS ON | 14.0% / 74% | 13.3% / 68% | 5.8% / 31% | **2.8% / 29%** |
| NMOS OFF | 19.4% / 99% | 9.1% / 51% | 5.5% / 33% | **2.8% / 12%** |
| PMOS ON | 12.4% / 67% | 12.9% / 61% | **5.4% / 30%** | 2.5% / 37% |
| PMOS OFF | 21.0% / 94% | 9.9% / 52% | 5.5% / 31% | **2.9% / 13%** |

- **PMOS ON:** the selection score, (median + p95) / 2, is 17.6 for LightGBM and 19.7 for the MLP, so
  LightGBM is chosen by the fixed rule even though the MLP's median is half as large. Swapping in the MLP
  for PMOS ON was checked as a variant only: gates 1.26% median (vs 1.33%), circuit 1.33% mean (vs 1.40%).
  The rule's choice is kept so no model is selected on the gate or circuit test results.
- **OFF cases got harder with junction areas:** the junction leakage roughly doubles the OFF body current,
  and Ib is now at 4–7% median error (Id, Ig, Is stay at 1.6–2.5%). Ib is a small part of gate leakage.

Test set, chosen model, mean over terminals (`results/part2/test_metrics.md`, parity plots in
`results/part2/plots/parity_<case>[_targeted].png`):

| Case | Uniform test: median / p95 | Targeted test: median / p95 |
|---|---|---|
| NMOS ON (MLP) | 2.1% / 8.2% | 4.5% / 51% |
| NMOS OFF (MLP) | 2.6% / 11% | 3.5% / 15% |
| PMOS ON (LightGBM) | 5.0% / 21% | 6.7% / 40% |
| PMOS OFF (MLP) | 2.6% / 13% | 3.3% / 14% |

Retrained from scratch on the 5k uniform + 5k targeted data with junction areas (2026-11-10). Before the
areas were added (2026-11-08), all four cases chose the MLP at 1.7–2.1% uniform median; gates were 1.22%
median and the circuit 1.35% mean.

- **Without the targeted data**, the same models scored 1.1–1.3% on the uniform test but 120–180%
  median error on the targeted ON test points, with the sign of Id and Is right in only 42–72% of them.
- **The remaining large targeted errors** are Id and Is of ON devices at |Vds| of µV to mV, where the
  channel current passes through zero. Part 3's leakage formula does not use those currents. The Ig and
  Ib of the same devices, which it does use, are at 1.7–6% median error.

**Learning curve** (`results/part2/learning_curve.csv`, `plots/learning_curve.png`): the chosen model
retrained on nested random subsets of the training split, scored on both test sets. Each cell is
median / p95 on the uniform test · median / p95 on the targeted test.

| Case | 1k | 2k | 5k | 7k (full) |
|---|---|---|---|---|
| NMOS ON (MLP) | 4.8% / 25% · 10.9% / 124% | 2.5% / 15% · 6.0% / 113% | 2.1% / 8.7% · 4.3% / 61% | 2.1% / 8.2% · 4.3% / 59% |
| NMOS OFF (MLP) | 11.6% / 118% · 17.9% / 147% | 6.3% / 35% · 9.1% / 53% | 3.0% / 13% · 4.4% / 20% | 2.7% / 11% · 3.4% / 15% |
| PMOS ON (LightGBM) | 11.6% / 43% · 14.9% / 128% | 8.5% / 33% · 11.2% / 79% | 5.6% / 23% · 7.7% / 43% | 5.0% / 20% · 6.7% / 40% |
| PMOS OFF (MLP) | 15.0% / 93% · 19.8% / 155% | 6.5% / 33% · 9.0% / 41% | 2.7% / 15% · 4.4% / 20% | 2.7% / 13% · 3.1% / 15% |

Re-run on the junction-area data (7,000 training rows per case).
- **NMOS ON** levels off at 5k rows on both test sets.
- **OFF cases** still improve from 5k to 7k, most on the targeted test (4.4% to 3.1–3.4% median). With
  junction areas the OFF body current is harder to fit, so more rows would still help them.
- **PMOS ON (LightGBM)** also keeps improving up to 7k, but stays above the MLP's level on typical points.

### Using the models
```python
sys.path.insert(0, "part2_models")
from leakage_model import INPUTS, load_case_model
m = load_case_model("results/part2/models/nmos_off.joblib")   # nmos_on / nmos_off / pmos_on / pmos_off
currents = m.predict(df[INPUTS])   # 12 input columns -> DataFrame id, ig, is, ib in A (sign included)
```

---

## Part 3 — Gate-level validation (done)
**Goal:** check that the transistor models estimate gate leakage accurately.

### What was done
- **Gates** (`part3_gates/gates.py:GATES`): static CMOS INV, NAND2, NOR2, and AND2 / OR2 as
  NAND2 / NOR2 + INV in one netlist. All transistors W = L = 22 nm. All NMOS in a gate share the
  corner's NMOS parameters, all PMOS its PMOS parameters. Topology of NAND2 (pin order matters, see Part 4):

  | Transistor | Type | Drain | Gate | Source | Body |
  |---|---|---|---|---|---|
  | mp1 | PMOS | out | a | vdd | vdd |
  | mp2 | PMOS | out | b | vdd | vdd |
  | mn1 | NMOS | out | a | x | 0 |
  | mn2 | NMOS | x | b | 0 | 0 |

- **Corners** (`part3_gates/corners.py`): 200 PVT corners drawn once with `SEEDS["corners"]` into
  `data/corners.csv`; columns `corner, vdd, temp, nmos_<p>, pmos_<p>` for p in `vth0, toxe, ndep, u0, xj`.
- **SPICE** (`simulate.py`): all 18 gate-input cases × 200 corners = 3,600 runs, inputs exactly 0 or VDD.
  Every transistor terminal is wired through its own 0 V source, so each run records all terminal
  currents, the supply and input-source currents, and the output and internal node voltages
  (x, y, nand_out, nor_out). One row per run in `results/part3/spice_gates.csv`.
- **Oracle check** (`results/part3/oracle_check.txt`): SPICE's own terminal currents, put through the
  leakage formula, reproduce −i(vsupply) to a relative 7e-7 (limit 1e-6). The tiny gap is SPICE's own KCL
  residual (solver tolerance at the internal nodes plus each ON transistor's few-fA floor).
- **ML prediction** (`compare.py`): each transistor's (Vd, Vg, Vs, Vb) comes from the SPICE-recorded node
  voltages (decision 2), the ON / OFF model is picked from the gate voltage (above or below VDD/2), and the
  predicted currents go through the same leakage formula. Vg is the recorded voltage too: for the inverter
  inside AND2 / OR2 that is the NAND / NOR output, a few mV off the rail.
- **Leakage formula** (`gates.py:leakage`): the current drawn from VDD, computed **without any ON
  transistor's drain or source current**. Inside a gate an ON transistor sits at |Vds| ≈ 0 and only
  carries the leakage of the rest of the gate; the models are unreliable there. So:
  - each ON transistor's channel is one unknown t (its drain current); its source current follows from
    its own KCL, is = −(ig + ib) − t. Its gate and body currents are used as predicted;
  - OFF transistors use all four predicted currents;
  - KCL at every internal node solves the unknowns, and the VDD current is the sum at the VDD node.

  `leakage_vdd_terminals` keeps the plain sum of every terminal current at VDD for comparison; for SPICE
  currents both agree, for ML currents the plain sum is far worse (below).

### Results
Over all 3,600 gate runs: **median error 1.33%, p95 4.71%, mean 1.81% (98.2% mean accuracy), bias −0.28%**,
every run but one with the right sign (NOR2 11 at corner 76, see [Results at a glance](#results-at-a-glance)) (`results/part3/gate_table.md`, `plots/gate_parity.png`). Per case
(median / p95 error):

| Gate | 0 / 00 | 1 / 01 | 10 | 11 |
|---|---|---|---|---|
| INV | 1.4% / 4.2% | 1.3% / 5.2% | | |
| NAND2 | 1.4% / 5.2% | 1.4% / 4.2% | 1.7% / 4.2% | 1.3% / 5.1% |
| NOR2 | 1.4% / 4.2% | 1.0% / 3.6% | 3.3% / 7.7% | 2.9% / 9.3% |
| AND2 | 0.8% / 3.3% | 0.9% / 3.0% | 0.9% / 3.0% | 1.1% / 3.5% |
| OR2 | 1.1% / 3.5% | 1.1% / 3.5% | 1.4% / 3.7% | 1.4% / 4.1% |

Inputs are written A then B, e.g. NAND2 `01` = A 0, B 1.
- **Formula and retraining both mattered** (overall median / p95, Vg snapped to the rail):

  | | plain VDD-terminal sum | KCL formula |
  |---|---|---|
  | uniform-only models | 132% / 275% (wrong sign in 14 cases) | 4.4% / 18% |
  | retrained (uniform + targeted) | 3.9% / 16% | 1.4% / 5.0% |

- **Least accurate:** NOR2 10 and 11. Their whole leakage is the Is of one OFF PMOS whose drain sits at a
  stack-node voltage (0.15–0.2 or 0.9 × VDD), where the training data has only ~20 rows. NAND2 00 is next.
- **AND2 / OR2 inverter input:** the internal NAND / NOR output is at most 1.8% of VDD off the rail.
  Snapping Vg to the rail instead raises the median error by up to 1.1 points (OR2 00: 1.1% to 1.9%).
- **Input-source current (question 3):** counting the gate current drawn from inputs held at VDD gives
  1.1% median, 3.7% p95.

`results/part3/gate_predictions.csv` holds one row per run: `gate, inputs, corner, vdd, temp,
spice_leak, ml_leak` plus the variant columns (`ml_leak_rail_vg`, `spice_leak_with_inputs`,
`ml_leak_with_inputs`, `ml_leak_vdd_terminals`) and `rel_err`.

---

## Part 4 — Circuit-level validation

**Complete:** all 512 vectors at all 200 corners passed input-voltage and gate-logic checks.
The corrected leakage estimate has 1.14% median, 3.63% p95, 1.40% mean and 6.67% maximum error
(models retrained on the 5k + 5k data with junction areas; before the areas: 1.07% / 3.55% / 1.35% / 6.60%).
The plain gate sum has 24.76% mean error. Corrected mean accuracy is 98.60%, below the 99% objective.
The saved ngspice-47 sweep reports logic checks for all cases. The seven structural tests,
end-to-end `run_all.py --part4-only` check, and 1,200 independent `.op`/DC comparisons
are documented for the earlier Part 4 run.

See the [Part 4 report](results/part4/report_part4.md), [metrics](results/part4/circuit_table.md),
and [worked calculation](results/part4/example_calculation.md). The corrected SPICE-gate diagnostic
still differs from the full circuit by 0.71% on average, showing the effect of the isolated-gate
approximation even with SPICE gate currents. The worst corrected corner is 72 (124.91 C, VDD
0.94936 V): 5.60% mean error across vectors and 6.67% in the worst case. High-temperature corners
have higher errors on average, but some cold corners are also among the worst.

The submission uses the four saved transistor models and the Part 3 NAND2 lookup with Boolean
inputs at the supply rails. It includes the specified plain gate sum and the supply-only estimate
with the internal input-current correction. The
[deliverables checklist](part4_circuit/DELIVERABLES.md) maps the artifacts to the brief.

In plain language, **PVT** means process (fabricated transistor properties), voltage
(the supply), and temperature. A **corner** is one set of those conditions; here the
200 corners are random samples, rather than just named manufacturing extremes.
A **vector** is a nine-bit input pattern. One **simulation case** solves the complete
transistor circuit for one vector at one corner. A **netlist** is the text description
of the devices and their connections. The ML **calculation** estimates that same
case by following the Boolean logic and combining saved gate-current predictions.
We measure settled leakage, not the current consumed while inputs switch.

For the error tables, **median** means half the errors are below that value; **p95**
means 95% are below it; **mean** is their average. **Bias** retains the sign, so a
negative bias means underprediction. A 2% relative error means the estimated leakage
differs from SPICE by 2% of the SPICE value. **KCL** is conservation of current at a node.

The implemented circuit has **8 data inputs plus 1 even-parity input**, ordered
`d0 d1 d2 d3 d4 d5 d6 d7 parity`. Output `error` is the XOR of all nine inputs:
0 means valid even parity; 1 indicates a parity error. All 512 patterns are evaluated,
including valid and invalid parity. Seven XORs form a balanced tree over the data bits;
one final XOR compares their parity with the supplied parity bit. Each XOR uses four
ordered NAND2s: 32 NAND2 gates and 128 transistors in total.

### Method and checks

- `circuit.py:GRAPH` is the single source of truth for both Boolean logic and SPICE wiring.
  NAND pin a drives the upper NMOS; pin b drives the lower NMOS, exactly as in Part 3.
- W = L = 22 nm for every transistor; the assigned MGK model and `config.SPICE_OPTIONS`
  are reused. All devices in a circuit share that corner's NMOS/PMOS parameter draws.
- The complete transistor circuit is simulated at all **512 x 200 = 102,400** operating
  points. Every primary input is 0 or VDD. No explicit output load is added.
- The SPICE record includes supply current, nine input-source currents, all 32 NAND
  output voltages, and corner parameters. Every internal gate's logic is checked, not
  only the final output. Missing, non-finite, duplicate and incorrect cases fail the run.
- Each corner is one ngspice process. An integer DC sweep is decoded into nine ideal input
  voltage sources at 0/VDD; zero-volt input ammeters measure their currents. A quarter-code
  offset avoids decoder discontinuities at the integer sweep points. Input levels are checked
  within the specified 1 nV SPICE voltage tolerance. The 128 circuit transistors are unchanged.
  An independent `--method op` uses separately altered input sources and operating-point calls
  for cross-checking. Workers run concurrently; hashed per-corner checkpoints allow safe resume.
- `compare.py` recreates the 800 NAND2 gate lookup entries using the saved models and
  Part 3 voltages, and checks them against committed Part 3 predictions. No circuit-SPICE
  measurement is used in the ML estimate.

### Three ML estimates

1. **Plain gate sum:** sum the 32 NAND2 supply leakages indexed by ordered input bits
   and corner. This is the hierarchical sum requested in the specification.
2. **Corrected supply estimate:** add the signed ML gate currents into every high NAND
   input driven by another gate. These currents came from isolated input sources in
   Part 3, but come through the driving gate from circuit VDD in Part 4. Exclude primary
   input-source currents from this main result.
3. **Supply plus high primary-input currents:** add those primary-input currents too,
   and compare against a SPICE reference with exactly the same definition.

The correction uses the sum of PMOS and NMOS `ig` on the relevant a/b pin, preserving
its sign. It is independent of the circuit reference. Low inputs need no extra correction
under the rail-input approximation. Both plain and corrected results must be reported.

Two additional **evaluation-only** estimates use isolated-gate SPICE leakage/input
currents in place of ML currents. Their residual against circuit SPICE measures the
rail-input/loading approximation. They are diagnostics, not ML predictions or training data.

### Run

```bash
python part4_circuit/test_circuit.py
# Small trial (separate output, cannot overwrite full results):
python part4_circuit/simulate.py --corners 0 1 --workers 2 --output results/part4/pilot
python part4_circuit/compare.py --output results/part4/pilot
# Independent solver-method cross-check (optional, separate reference):
python part4_circuit/simulate.py --method op --corners 0 1 --workers 2 --output results/part4/pilot
python part4_circuit/cross_check.py --include-extremes
# Full circuit stage, using committed Parts 1-3:
python run_all.py --part4-only --workers 6
# Regenerate the entire project (includes hours of ML training/learning curves):
python run_all.py
```

Use the Python executable from your virtual environment. This machine's Ubuntu environment
is `/home/skd/.venvs/dvd-project/bin/python`; the documented `.venv` setup also works.
Worker count is adjustable; six is the conservative default for this 12-thread machine.
The saved full sweep used ngspice-47 and Python 3.12.13.

### Outputs in `results/part4/`

- `parity9_example.cir`: complete runnable transistor netlist at one corner/vector.
- `parity9_dc.cir`: production 512-vector DC netlist (writes `measurements.txt` when run).
- `spice_circuit.csv.gz`: full-circuit SPICE record (standard gzip-compressed CSV).
- `nand2_lookup.csv`: the 800 ordered gate/corner entries and per-pin input currents.
- `circuit_predictions.csv.gz`: all ML/diagnostic estimates and per-case errors.
- `circuit_table.csv` / `.md`: SPICE/prediction medians, bias, median/p95/mean/max errors.
- `errors_by_corner.csv`, `errors_by_vector.csv`, `worst_cases.csv`: error breakdowns.
- `plots/circuit_parity.png`, `plots/error_vs_temperature.png`: comparisons and error analysis.
- `simulation_summary.json`, `python_versions.json`: simulator, coverage, logic checks and versions.
- `environment_freeze.txt`, `artifact_hashes.json`: complete package versions and input/code provenance.
- `report_part4.md`, `error_decomposition.json`, `errors_by_pvt_quartile.csv`: report and error analysis.
- `example_calculation.md`, `example_gate_breakdown.csv`: a worked example with all 32 gate contributions.
- `op_dc_crosscheck.json`: historical comparison with an independently initialized `.op` pilot.

Read compressed records directly with `pandas.read_csv(path, dtype={"vector": str})`.
The string dtype preserves leading zeros in the nine-bit vector.

Limitations: isolated-gate rail inputs ignore analog level shifts and loading. The correction
accounts for current ownership but does not solve coupled analog gate voltages. Gate models
retain their existing prediction errors; the 99% accuracy objective is evaluated, not assumed.

---

## Part 5 — Final deliverables

- The [combined LaTeX report](report/completed/project_report.tex) includes the setup, sampling and validation, model comparison, gate and circuit results, and limitations. Import the [Overleaf ZIP](report/completed_report_overleaf.zip), select `project_report.tex` as the main document, and compile to verify the PDF layout.
- [`run_all.py`](run_all.py) runs the regeneration stages in order with fixed seeds. Use `--part4-only` to reuse the saved upstream artifacts. The Part 4 mode was tested end to end on the earlier Part 4 run.
- [Model comparison](results/part2/comparison_table.md), [test metrics](results/part2/test_metrics.md), [gate results](results/part3/gate_table.md), and [circuit results](results/part4/circuit_table.md) are available separately alongside the datasets, netlists, saved models, and figures.

---

## Team responsibilities
| Member | Primary responsibility | State |
|---|---|---|
| Member 1 | Part 1: transistor datasets | Done |
| Member 2 | Part 2: ML training and model selection | Done |
| Member 3 | Part 3: gate-level validation | Done |
| Member 4 | Part 4: circuit-level validation and integration (`run_all`) | Done |

Shared items with a single owner: the config file (Member 4), the corner table (Member 3), and the sign
convention and leakage definition (agreed by everyone before coding).

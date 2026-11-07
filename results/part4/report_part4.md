# Part 4: Nine-input parity circuit validation

## Setup and circuit

PTM 22nm MGK, nominal VDD 0.9 V, W=L=22 nm for NMOS and PMOS. Simulator: ngspice-42 : Circuit level simulation program; Python 3.12.3. Package versions accompany the results. The nine inputs are eight data bits plus one even-parity bit. A balanced seven-XOR data tree and a final parity XOR use 32 ordered NAND2 gates (128 transistors). Output 0 is valid even parity; output 1 signals an error.

## Terms and evaluation

PVT means process (transistor fabrication parameters), voltage (VDD), and temperature. A corner is one sampled PVT setting. A vector is one nine-bit input pattern. A simulation case is one vector at one corner. Static leakage is the current drawn from VDD after the transistor circuit settles, not switching current.

This run contains **102,400 cases**, 200 shared corners and 512 vectors. Full coverage is 512 x 200 = 102,400 cases. The reference is the complete transistor circuit, not a sum of isolated SPICE gates. The circuit ML calculation uses Boolean logic and 800 isolated NAND2 lookup entries derived from the saved transistor models. Circuit-SPICE node voltages are evaluation-only.

The plain sum follows the specified hierarchical approximation. The corrected sum also includes signed gate currents into high inputs driven by internal gates. Primary input sources are excluded from the main supply-only result, and included in a separately matched variant. No model retraining was needed.

## Results

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.2929e-07 |  -21.672   |         21.672   |       53.578  |       24.753   |       67.112  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.148e-06  |   -1.0956  |          1.3661  |        3.5026 |        1.5489  |        6.4622 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.2123e-06 |   -1.1083  |          1.3537  |        3.4309 |        1.5412  |        6.1938 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

Corrected mean error is **1.549%**, corresponding to 98.451% mean accuracy under the project's 100-minus-mean-relative-error convention. The approximate 1% mean-error objective is **not met**. The submission reports the prescribed rail-input plain sum alongside this correction. Both use the Part 3 NAND2 lookup derived from the four saved transistor models.

The isolated NAND2 baseline has 1.980% mean error and 4.899% p95 error. Summation can average some transistor-model errors, while inter-gate analog loading introduces additional error. Even the corrected SPICE-gate diagnostic has 0.712% mean error against full-circuit SPICE; the rail-input approximation itself is imperfect.

Using the full-circuit current as the common denominator, the mean signed error decomposes exactly into -0.346 percentage points from replacing isolated SPICE-gate currents with ML currents, and -0.699 percentage points from composing isolated gates with the input-current correction. These signed components can cancel; they are not an additive decomposition of absolute errors.

## Validation

All recorded gate outputs passed Boolean checks. Maximum internal NAND output deviation from its ideal logic rail: 0.5366% of VDD. Input sources are checked against 0/VDD using the required 1 nV voltage tolerance. The independent operating-point/DC cross-check is stored separately when run. Tests cover all 512 parity patterns, pin-current ownership, batched aggregation, missing measurements and deliberately corrupted node/input voltages.

## Error analysis

Worst corners by corrected mean error:

|   corner |     vdd |     temp |   nmos_vth0 |   pmos_vth0 |   mean_err_pct |   p95_err_pct |   max_err_pct |
|---------:|--------:|---------:|------------:|------------:|---------------:|--------------:|--------------:|
|       53 | 0.89907 | 111.13   |     0.38113 |    -0.23837 |         6.0452 |        6.2939 |        6.4622 |
|       70 | 0.91207 | -32.379  |     0.3621  |    -0.2585  |         4.7782 |        4.9496 |        5.0491 |
|      104 | 0.94789 |  -8.7214 |     0.33651 |    -0.26985 |         4.6035 |        4.7379 |        4.7984 |
|       68 | 0.94141 | 104.48   |     0.3326  |    -0.27644 |         4.5274 |        4.7697 |        4.7991 |
|      162 | 0.85331 |  88.213  |     0.34963 |    -0.23291 |         4.3546 |        4.6121 |        4.8002 |

Worst vectors by corrected mean error over corners:

| vector      |   mean_err_pct |   p95_err_pct |   bias_pct |
|:------------|---------------:|--------------:|-----------:|
| `111111101` |         1.6424 |        3.5733 |    -1.3445 |
| `111011101` |         1.6367 |        3.6082 |    -1.3314 |
| `111110111` |         1.6358 |        3.5524 |    -1.337  |
| `111011111` |         1.6357 |        3.5522 |    -1.337  |
| `101111101` |         1.6306 |        3.5956 |    -1.3237 |

Temperature quartiles (descriptive associations, not causal effects):

|   quartile_low_to_high |      min |      max |   runs |   mean_err_pct |   p95_err_pct |
|-----------------------:|---------:|---------:|-------:|---------------:|--------------:|
|                      1 | -38.48   |   6.4904 |  25600 |         1.3306 |        3.1892 |
|                      2 |   6.7832 |  44.46   |  25600 |         1.2401 |        2.9564 |
|                      3 |  44.965  |  84.927  |  25600 |         1.1845 |        3.079  |
|                      4 |  87.09   | 124.91   |  25600 |         2.4403 |        4.3745 |

The full quartile table also covers VDD and NMOS/PMOS threshold magnitudes. Each corner is reused over every vector; these are 200 PVT draws, not 102,400 independent draws of fabrication and temperature conditions. Worst individual cases and both per-corner/per-vector summaries accompany this report.

## Limitations and possible improvements

The gate lookup assumes ideal input rails and isolated-gate node voltages. The input-current correction changes current accounting but does not solve coupled analog voltages. The full circuit has fanout and non-ideal high/low levels. Existing transistor models also retain their own fitting errors. Future work could use gate models conditioned on analog input voltages and loading, solve coupled voltages, or improve transistor fits using additional independently generated training samples. Circuit evaluation data must remain outside model training.

## Reproduction

```bash
python run_all.py --part4-only --workers 6
```

This command reuses Parts 1-3, validates/reuses matching per-corner checkpoints, and regenerates circuit predictions, tables, plots, versions and this report. `python run_all.py` also regenerates the upstream datasets, models and gate results; that much longer full training pipeline was not rerun for this Part 4 addition.

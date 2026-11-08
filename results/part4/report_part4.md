# Part 4: Nine-input parity circuit validation

## Setup and circuit

PTM 22nm MGK, nominal VDD 0.9 V, W=L=22 nm for NMOS and PMOS. Simulator: ngspice-47 : Circuit level simulation program; Python 3.12.13. Package versions accompany the results. The nine inputs are eight data bits plus one even-parity bit. A balanced seven-XOR data tree and a final parity XOR use 32 ordered NAND2 gates (128 transistors). Output 0 is valid even parity; output 1 signals an error.

## Terms and evaluation

PVT means process (transistor fabrication parameters), voltage (VDD), and temperature. A corner is one sampled PVT setting. A vector is one nine-bit input pattern. A simulation case is one vector at one corner. Static leakage is the current drawn from VDD after the transistor circuit settles, not switching current.

This run contains **102,400 cases**, 200 shared corners and 512 vectors. Full coverage is 512 x 200 = 102,400 cases. The reference is the complete transistor circuit, not a sum of isolated SPICE gates. The circuit ML calculation uses Boolean logic and 800 isolated NAND2 lookup entries derived from the saved transistor models. Circuit-SPICE node voltages are evaluation-only.

The plain sum follows the specified hierarchical approximation. The corrected sum also includes signed gate currents into high inputs driven by internal gates. Primary input sources are excluded from the main supply-only result, and included in a separately matched variant. No model retraining was needed.

## Results

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.1592e-07 |  -22.149   |         22.149   |       53.506  |       24.841   |       66.585  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.1525e-06 |   -0.80895 |          1.0676  |        3.5467 |        1.3549  |        6.6018 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.2165e-06 |   -0.74537 |          1.0188  |        3.4944 |        1.3182  |        6.3457 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

Corrected mean error is **1.355%**, corresponding to 98.645% mean accuracy under the project's 100-minus-mean-relative-error convention. The approximate 1% mean-error objective is **not met**. The submission reports the prescribed rail-input plain sum alongside this correction. Both use the Part 3 NAND2 lookup derived from the four saved transistor models.

The isolated NAND2 baseline has 1.708% mean error and 5.035% p95 error. Summation can average some transistor-model errors, while inter-gate analog loading introduces additional error. Even the corrected SPICE-gate diagnostic has 0.712% mean error against full-circuit SPICE; the rail-input approximation itself is imperfect.

Using the full-circuit current as the common denominator, the mean signed error decomposes exactly into -0.151 percentage points from replacing isolated SPICE-gate currents with ML currents, and -0.699 percentage points from composing isolated gates with the input-current correction. These signed components can cancel; they are not an additive decomposition of absolute errors.

## Validation

All recorded gate outputs passed Boolean checks. Maximum internal NAND output deviation from its ideal logic rail: 0.5366% of VDD. Input sources are checked against 0/VDD using the required 1 nV voltage tolerance. The independent operating-point/DC cross-check is stored separately when run. Tests cover all 512 parity patterns, pin-current ownership, batched aggregation, missing measurements and deliberately corrupted node/input voltages.

## Error analysis

Worst corners by corrected mean error:

|   corner |     vdd |    temp |   nmos_vth0 |   pmos_vth0 |   mean_err_pct |   p95_err_pct |   max_err_pct |
|---------:|--------:|--------:|------------:|------------:|---------------:|--------------:|--------------:|
|       73 | 0.98252 |  81.655 |     0.39697 |    -0.23667 |         6.1824 |        6.4069 |        6.6018 |
|       35 | 0.98043 |  20.853 |     0.34304 |    -0.23458 |         5.2438 |        5.4489 |        5.5677 |
|      144 | 0.98343 |  82.284 |     0.38856 |    -0.24004 |         5.1082 |        5.2055 |        5.2209 |
|       89 | 0.97028 |  87.787 |     0.34206 |    -0.25193 |         5.1012 |        5.5019 |        5.9568 |
|      166 | 0.98377 | 104.07  |     0.40439 |    -0.24627 |         4.1884 |        4.5404 |        4.7879 |

Worst vectors by corrected mean error over corners:

| vector      |   mean_err_pct |   p95_err_pct |   bias_pct |
|:------------|---------------:|--------------:|-----------:|
| `111111101` |         1.4591 |        3.7253 |   -0.91487 |
| `111111011` |         1.4535 |        3.7078 |   -0.91944 |
| `111110111` |         1.4524 |        3.7142 |   -0.90724 |
| `111011111` |         1.4523 |        3.714  |   -0.90723 |
| `111011101` |         1.4494 |        3.6969 |   -0.93433 |

Temperature quartiles (descriptive associations, not causal effects):

|   quartile_low_to_high |      min |      max |   runs |   mean_err_pct |   p95_err_pct |
|-----------------------:|---------:|---------:|-------:|---------------:|--------------:|
|                      1 | -38.48   |   6.4904 |  25600 |         1.1723 |        3.1841 |
|                      2 |   6.7832 |  44.46   |  25600 |         1.2906 |        3.6811 |
|                      3 |  44.965  |  84.927  |  25600 |         1.4982 |        3.6697 |
|                      4 |  87.09   | 124.91   |  25600 |         1.4588 |        3.6352 |

The full quartile table also covers VDD and NMOS/PMOS threshold magnitudes. Each corner is reused over every vector; these are 200 PVT draws, not 102,400 independent draws of fabrication and temperature conditions. Worst individual cases and both per-corner/per-vector summaries accompany this report.

## Limitations and possible improvements

The gate lookup assumes ideal input rails and isolated-gate node voltages. The input-current correction changes current accounting but does not solve coupled analog voltages. The full circuit has fanout and non-ideal high/low levels. Existing transistor models also retain their own fitting errors. Future work could use gate models conditioned on analog input voltages and loading, solve coupled voltages, or improve transistor fits using additional independently generated training samples. Circuit evaluation data must remain outside model training.

## Reproduction

```bash
python run_all.py --part4-only --workers 6
```

This command reuses Parts 1-3, validates/reuses matching per-corner checkpoints, and regenerates circuit predictions, tables, plots, versions and this report. `python run_all.py` also regenerates the upstream datasets, models and gate results; that much longer full training pipeline was not rerun for this Part 4 addition.

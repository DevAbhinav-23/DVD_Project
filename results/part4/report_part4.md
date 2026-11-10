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
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.207e-07  |  -21.625   |         21.625   |       54.075  |       24.763   |       66.691  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.1432e-06 |   -0.62136 |          1.1434  |        3.6295 |        1.4032  |        6.6716 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.211e-06  |   -0.60354 |          1.1258  |        3.5529 |        1.378   |        6.6348 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

Corrected mean error is **1.403%**, corresponding to 98.597% mean accuracy under the project's 100-minus-mean-relative-error convention. The approximate 1% mean-error objective is **not met**. The submission reports the prescribed rail-input plain sum alongside this correction. Both use the Part 3 NAND2 lookup derived from the four saved transistor models.

The isolated NAND2 baseline has 1.788% mean error and 4.558% p95 error. Summation can average some transistor-model errors, while inter-gate analog loading introduces additional error. Even the corrected SPICE-gate diagnostic has 0.712% mean error against full-circuit SPICE; the rail-input approximation itself is imperfect.

Using the full-circuit current as the common denominator, the mean signed error decomposes exactly into 0.017 percentage points from replacing isolated SPICE-gate currents with ML currents, and -0.699 percentage points from composing isolated gates with the input-current correction. These signed components can cancel; they are not an additive decomposition of absolute errors.

## Validation

All recorded gate outputs passed Boolean checks. Maximum internal NAND output deviation from its ideal logic rail: 0.5366% of VDD. Input sources are checked against 0/VDD using the required 1 nV voltage tolerance. The independent operating-point/DC cross-check is stored separately when run. Tests cover all 512 parity patterns, pin-current ownership, batched aggregation, missing measurements and deliberately corrupted node/input voltages.

## Error analysis

Worst corners by corrected mean error:

|   corner |     vdd |    temp |   nmos_vth0 |   pmos_vth0 |   mean_err_pct |   p95_err_pct |   max_err_pct |
|---------:|--------:|--------:|------------:|------------:|---------------:|--------------:|--------------:|
|       72 | 0.94936 | 124.91  |     0.34668 |    -0.23957 |         5.6007 |        6.187  |        6.6716 |
|      166 | 0.98377 | 104.07  |     0.40439 |    -0.24627 |         5.4101 |        5.8021 |        5.9935 |
|       53 | 0.89907 | 111.13  |     0.38113 |    -0.23837 |         5.176  |        5.3181 |        5.4777 |
|       87 | 0.91825 | 122.29  |     0.36895 |    -0.27729 |         4.8964 |        5.0868 |        5.3532 |
|       78 | 0.81425 |  14.615 |     0.35139 |    -0.27024 |         4.7369 |        4.7999 |        4.8291 |

Worst vectors by corrected mean error over corners:

| vector      |   mean_err_pct |   p95_err_pct |   bias_pct |
|:------------|---------------:|--------------:|-----------:|
| `111111111` |         1.4872 |        3.8098 |   -0.75262 |
| `111111101` |         1.4822 |        3.9177 |   -0.81613 |
| `111110111` |         1.4757 |        3.9043 |   -0.80358 |
| `111011111` |         1.4756 |        3.9039 |   -0.80345 |
| `111111011` |         1.4737 |        3.8984 |   -0.80911 |

Temperature quartiles (descriptive associations, not causal effects):

|   quartile_low_to_high |      min |      max |   runs |   mean_err_pct |   p95_err_pct |
|-----------------------:|---------:|---------:|-------:|---------------:|--------------:|
|                      1 | -38.48   |   6.4904 |  25600 |        1.2355  |        2.7078 |
|                      2 |   6.7832 |  44.46   |  25600 |        0.97023 |        2.3576 |
|                      3 |  44.965  |  84.927  |  25600 |        1.2789  |        3.5566 |
|                      4 |  87.09   | 124.91   |  25600 |        2.1283  |        5.1361 |

The full quartile table also covers VDD and NMOS/PMOS threshold magnitudes. Each corner is reused over every vector; these are 200 PVT draws, not 102,400 independent draws of fabrication and temperature conditions. Worst individual cases and both per-corner/per-vector summaries accompany this report.

## Limitations and possible improvements

The gate lookup assumes ideal input rails and isolated-gate node voltages. The input-current correction changes current accounting but does not solve coupled analog voltages. The full circuit has fanout and non-ideal high/low levels. Existing transistor models also retain their own fitting errors. Future work could use gate models conditioned on analog input voltages and loading, solve coupled voltages, or improve transistor fits using additional independently generated training samples. Circuit evaluation data must remain outside model training.

## Reproduction

```bash
python run_all.py --part4-only --workers 6
```

This command reuses Parts 1-3, validates/reuses matching per-corner checkpoints, and regenerates circuit predictions, tables, plots, versions and this report. `python run_all.py` also regenerates the upstream datasets, models and gate results; that much longer full training pipeline was not rerun for this Part 4 addition.

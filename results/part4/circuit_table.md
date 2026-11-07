# Nine-input parity circuit: ML versus full-circuit SPICE

102,400 cases; 200 corners; 512 vectors.

Vector order: d0 d1 d2 d3 d4 d5 d6 d7 parity. Even parity: error=0 is valid.
32 NAND2 gates, 128 minimum-sized transistors, identical pin order to Part 3.

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.2929e-07 |  -21.672   |         21.672   |       53.578  |       24.753   |       67.112  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.148e-06  |   -1.0956  |          1.3661  |        3.5026 |        1.5489  |        6.4622 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.2123e-06 |   -1.1083  |          1.3537  |        3.4309 |        1.5412  |        6.1938 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

The prescribed plain gate sum is the baseline. The corrected estimate adds signed gate
currents for high inputs driven by internal gates. Primary-input source currents remain
excluded from the main supply-only comparison; their inclusion is reported separately.

SPICE gate lookups are evaluation-only diagnostics: their residual against circuit SPICE
shows the isolated-gate/rail-input approximation, without transistor-model prediction error.
No full-circuit SPICE voltages or currents are used to calculate the ML estimates.

Part 3 NAND2 baseline: median 1.606%, p95 4.899%, mean 1.980% error.

## Worst corrected cases

|   corner | vector      |     vdd |   temp |   nmos_vth0 |   pmos_vth0 |   i_supply |   ml_corrected |   rel_err_corrected |
|---------:|:------------|--------:|-------:|------------:|------------:|-----------:|---------------:|--------------------:|
|       53 | `111111111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8368e-06 |     1.7181e-06 |            0.064622 |
|       53 | `111111101` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8814e-06 |     1.7604e-06 |            0.064295 |
|       53 | `111111011` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8719e-06 |     1.7516e-06 |            0.064283 |
|       53 | `111110111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8811e-06 |     1.7604e-06 |            0.064152 |
|       53 | `111011111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8811e-06 |     1.7604e-06 |            0.064149 |
|       53 | `110111111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8716e-06 |     1.7516e-06 |            0.064136 |
|       53 | `111101111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8716e-06 |     1.7516e-06 |            0.064126 |
|       53 | `101111111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8808e-06 |     1.7604e-06 |            0.064019 |
|       53 | `011111111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8713e-06 |     1.7516e-06 |            0.063993 |
|       53 | `111011101` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8592e-06 |     1.7411e-06 |            0.063497 |
|       53 | `111011011` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8497e-06 |     1.7323e-06 |            0.063481 |
|       53 | `110111101` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8497e-06 |     1.7323e-06 |            0.063481 |
|       53 | `111111110` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.841e-06  |     1.7242e-06 |            0.063469 |
|       53 | `110111011` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8402e-06 |     1.7235e-06 |            0.063465 |
|       53 | `101111101` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8589e-06 |     1.7411e-06 |            0.063366 |
|       53 | `111010111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8589e-06 |     1.7411e-06 |            0.063366 |
|       53 | `101111011` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8495e-06 |     1.7323e-06 |            0.063349 |
|       53 | `110110111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8495e-06 |     1.7323e-06 |            0.063349 |
|       53 | `011111101` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8494e-06 |     1.7323e-06 |            0.063336 |
|       53 | `111001111` | 0.89907 | 111.13 |     0.38113 |    -0.23837 | 1.8494e-06 |     1.7323e-06 |            0.063336 |

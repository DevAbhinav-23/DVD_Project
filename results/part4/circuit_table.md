# Nine-input parity circuit: ML versus full-circuit SPICE

102,400 cases; 200 corners; 512 vectors.

Vector order: d0 d1 d2 d3 d4 d5 d6 d7 parity. Even parity: error=0 is valid.
32 NAND2 gates, 128 minimum-sized transistors, identical pin order to Part 3.

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.1791e-07 |  -21.568   |         21.568   |       53.884  |       24.683   |       66.87   |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.1425e-06 |   -0.80252 |          1.1373  |        3.534  |        1.3762  |        5.4459 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.2138e-06 |   -0.78178 |          1.113   |        3.4762 |        1.3587  |        5.2404 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

The prescribed plain gate sum is the baseline. The corrected estimate adds signed gate
currents for high inputs driven by internal gates. Primary-input source currents remain
excluded from the main supply-only comparison; their inclusion is reported separately.

SPICE gate lookups are evaluation-only diagnostics: their residual against circuit SPICE
shows the isolated-gate/rail-input approximation, without transistor-model prediction error.
No full-circuit SPICE voltages or currents are used to calculate the ML estimates.

Part 3 NAND2 baseline: median 1.376%, p95 4.396%, mean 1.667% error.

## Worst corrected cases

|   corner | vector      |     vdd |   temp |   nmos_vth0 |   pmos_vth0 |   i_supply |   ml_corrected |   rel_err_corrected |
|---------:|:------------|--------:|-------:|------------:|------------:|-----------:|---------------:|--------------------:|
|      166 | `111111011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9106e-06 |     2.7521e-06 |            0.054459 |
|      166 | `111111101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9314e-06 |     2.7722e-06 |            0.054314 |
|      166 | `110111111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9097e-06 |     2.7521e-06 |            0.054151 |
|      166 | `111101111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9096e-06 |     2.7521e-06 |            0.054125 |
|      166 | `111110111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9305e-06 |     2.7722e-06 |            0.05401  |
|      166 | `111011111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9305e-06 |     2.7722e-06 |            0.054008 |
|      166 | `011111111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9087e-06 |     2.7521e-06 |            0.053844 |
|      166 | `101111111` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9296e-06 |     2.7722e-06 |            0.053731 |
|      166 | `110111011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8339e-06 |     2.683e-06  |            0.053262 |
|      166 | `010111011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8606e-06 |     2.7083e-06 |            0.053255 |
|      166 | `100111011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8815e-06 |     2.7284e-06 |            0.053144 |
|      166 | `011011011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8815e-06 |     2.7284e-06 |            0.053143 |
|      166 | `111011011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8547e-06 |     2.7031e-06 |            0.053121 |
|      166 | `110111101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8547e-06 |     2.7031e-06 |            0.053121 |
|      166 | `010111101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8814e-06 |     2.7284e-06 |            0.053116 |
|      166 | `101011011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9024e-06 |     2.7485e-06 |            0.053033 |
|      166 | `100111101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9023e-06 |     2.7485e-06 |            0.053006 |
|      166 | `011011101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.9023e-06 |     2.7485e-06 |            0.053006 |
|      166 | `111011101` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.8755e-06 |     2.7232e-06 |            0.052983 |
|      166 | `011111011` | 0.98377 | 104.07 |     0.40439 |    -0.24627 | 2.833e-06  |     2.683e-06  |            0.052946 |

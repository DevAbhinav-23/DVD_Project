# Nine-input parity circuit: ML versus full-circuit SPICE

102,400 cases; 200 corners; 512 vectors.

Vector order: d0 d1 d2 d3 d4 d5 d6 d7 parity. Even parity: error=0 is valid.
32 NAND2 gates, 128 minimum-sized transistors, identical pin order to Part 3.

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.207e-07  |  -21.625   |         21.625   |       54.075  |       24.763   |       66.691  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.1432e-06 |   -0.62136 |          1.1434  |        3.6295 |        1.4032  |        6.6716 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.211e-06  |   -0.60354 |          1.1258  |        3.5529 |        1.378   |        6.6348 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

The prescribed plain gate sum is the baseline. The corrected estimate adds signed gate
currents for high inputs driven by internal gates. Primary-input source currents remain
excluded from the main supply-only comparison; their inclusion is reported separately.

SPICE gate lookups are evaluation-only diagnostics: their residual against circuit SPICE
shows the isolated-gate/rail-input approximation, without transistor-model prediction error.
No full-circuit SPICE voltages or currents are used to calculate the ML estimates.

Part 3 NAND2 baseline: median 1.443%, p95 4.558%, mean 1.788% error.

## Worst corrected cases

|   corner | vector      |     vdd |   temp |   nmos_vth0 |   pmos_vth0 |   i_supply |   ml_corrected |   rel_err_corrected |
|---------:|:------------|--------:|-------:|------------:|------------:|-----------:|---------------:|--------------------:|
|       72 | `111111110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9219e-06 |     2.727e-06  |            0.066716 |
|       72 | `111111111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9526e-06 |     2.758e-06  |            0.06591  |
|       72 | `111111000` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9106e-06 |     2.722e-06  |            0.064781 |
|       72 | `110011110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9106e-06 |     2.722e-06  |            0.064781 |
|       72 | `111100110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9106e-06 |     2.722e-06  |            0.064779 |
|       72 | `001111110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9106e-06 |     2.722e-06  |            0.064779 |
|       72 | `110011111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9412e-06 |     2.753e-06  |            0.063992 |
|       72 | `111111001` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9412e-06 |     2.753e-06  |            0.063992 |
|       72 | `111100111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9412e-06 |     2.753e-06  |            0.06399  |
|       72 | `001111111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.9412e-06 |     2.753e-06  |            0.06399  |
|       72 | `110011000` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.06283  |
|       72 | `111100000` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.062829 |
|       72 | `110000110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.062829 |
|       72 | `001111000` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.062829 |
|       72 | `000011110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.062829 |
|       72 | `001100110` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 2.8992e-06 |     2.717e-06  |            0.062827 |
|       72 | `111111101` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 3.0444e-06 |     2.8547e-06 |            0.062302 |
|       72 | `111110111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 3.0441e-06 |     2.8547e-06 |            0.062201 |
|       72 | `111011111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 3.044e-06  |     2.8547e-06 |            0.06219  |
|       72 | `101111111` | 0.94936 | 124.91 |     0.34668 |    -0.23957 | 3.0436e-06 |     2.8547e-06 |            0.062069 |

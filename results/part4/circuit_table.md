# Nine-input parity circuit: ML versus full-circuit SPICE

102,400 cases; 200 corners; 512 vectors.

Vector order: d0 d1 d2 d3 d4 d5 d6 d7 parity. Even parity: error=0 is valid.
32 NAND2 gates, 128 minimum-sized transistors, identical pin order to Part 3.

| variant                                  |   spice_median_A |   prediction_median_A |   bias_pct |   median_err_pct |   p95_err_pct |   mean_err_pct |   max_err_pct |
|:-----------------------------------------|-----------------:|----------------------:|-----------:|-----------------:|--------------:|---------------:|--------------:|
| ML plain sum (spec baseline)             |       1.1582e-06 |            8.1592e-07 |  -22.149   |         22.149   |       53.506  |       24.842   |       66.585  |
| ML corrected (internal high inputs)      |       1.1582e-06 |            1.1525e-06 |   -0.80898 |          1.0677  |        3.5467 |        1.355   |        6.6018 |
| ML corrected + primary high inputs       |       1.2154e-06 |            1.2165e-06 |   -0.7454  |          1.0188  |        3.4945 |        1.3182  |        6.3458 |
| SPICE gate lookup plain (diagnostic)     |       1.1582e-06 |            8.2536e-07 |  -21.512   |         21.512   |       53.854  |       24.61    |       66.974  |
| SPICE gate lookup corrected (diagnostic) |       1.1582e-06 |            1.1501e-06 |   -0.59754 |          0.59754 |        1.7802 |        0.71197 |        3.172  |

The prescribed plain gate sum is the baseline. The corrected estimate adds signed gate
currents for high inputs driven by internal gates. Primary-input source currents remain
excluded from the main supply-only comparison; their inclusion is reported separately.

SPICE gate lookups are evaluation-only diagnostics: their residual against circuit SPICE
shows the isolated-gate/rail-input approximation, without transistor-model prediction error.
No full-circuit SPICE voltages or currents are used to calculate the ML estimates.

Part 3 NAND2 baseline: median 1.296%, p95 5.035%, mean 1.708% error.

## Worst corrected cases

|   corner | vector      |     vdd |   temp |   nmos_vth0 |   pmos_vth0 |   i_supply |   ml_corrected |   rel_err_corrected |
|---------:|:------------|--------:|-------:|------------:|------------:|-----------:|---------------:|--------------------:|
|       73 | `111111011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1634e-06 |     2.0206e-06 |            0.066018 |
|       73 | `111111111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1866e-06 |     2.0423e-06 |            0.065974 |
|       73 | `111111101` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1728e-06 |     2.0296e-06 |            0.065938 |
|       73 | `110111111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.163e-06  |     2.0206e-06 |            0.06583  |
|       73 | `111101111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.163e-06  |     2.0206e-06 |            0.06582  |
|       73 | `111110111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1724e-06 |     2.0296e-06 |            0.065753 |
|       73 | `111011111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1724e-06 |     2.0296e-06 |            0.065751 |
|       73 | `111111110` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.2277e-06 |     2.0814e-06 |            0.065675 |
|       73 | `011111111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1626e-06 |     2.0206e-06 |            0.065644 |
|       73 | `101111111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.172e-06  |     2.0296e-06 |            0.065578 |
|       73 | `110111011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1058e-06 |     1.9704e-06 |            0.064301 |
|       73 | `110111101` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1152e-06 |     1.9793e-06 |            0.064225 |
|       73 | `111011011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1152e-06 |     1.9793e-06 |            0.064225 |
|       73 | `111100011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1752e-06 |     2.0356e-06 |            0.06417  |
|       73 | `110011011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1752e-06 |     2.0356e-06 |            0.064168 |
|       73 | `001111011` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1752e-06 |     2.0356e-06 |            0.064168 |
|       73 | `111011101` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1246e-06 |     1.9883e-06 |            0.064151 |
|       73 | `111111001` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1984e-06 |     2.0574e-06 |            0.064143 |
|       73 | `110011111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1984e-06 |     2.0574e-06 |            0.064143 |
|       73 | `111100111` | 0.98252 | 81.655 |     0.39697 |    -0.23667 | 2.1984e-06 |     2.0574e-06 |            0.064143 |

# Worked circuit calculation

Vector `000000000` (d0 through d7, then parity), corner 0: VDD=0.842208 V, temperature=87.773 C. Expected error output=0.

Each NAND's input bits come from Boolean evaluation of the shared circuit graph. Its base leakage comes from the matching Part 3 lookup entry at this corner. For each high input driven by another gate, add that pin's predicted gate current. Primary inputs are powered by separate sources and stay outside the main supply sum.

Number of NANDs in each ordered input state: `00`: 8, `01`: 16, `10`: 0, `11`: 8.

1. Sum 32 isolated gate leakages: **1.02638803e-06 A**.
2. Add internal high-input gate currents: **2.09419290e-07 A**.
3. Corrected circuit estimate: **1.23580732e-06 A**.
4. Complete-circuit SPICE reference: **1.24359123e-06 A**.
5. Relative error = |estimate - reference| / |reference| = **0.6259%**.

`example_gate_breakdown.csv` gives all 32 contributions and their input connections. All currents are amperes; 1e-6 A equals one microampere.

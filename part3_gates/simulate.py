"""Part 3: SPICE reference for the 18 gate-input cases at the 200 shared corners.

Writes results/part3/spice_gates.csv (one row per simulation: corner, node voltages, supply and
input currents, every transistor terminal current), the oracle check and one example netlist per
gate in part3_gates/netlists/.

Usage:  python part3_gates/simulate.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from corners import load_corners
from gates import CASES, GATES, build_netlist, leakage, run_jobs

OUT_DIR = config.RESULTS_DIR / "part3"
NETLIST_DIR = Path(__file__).resolve().parent / "netlists"
ORACLE_TOL = 1e-6   # max relative difference between the summed terminal currents and -i(Vsupply)


def write_example_netlists(corners):
    """One runnable netlist per gate (corner 0, all inputs 1) for the deliverables."""
    NETLIST_DIR.mkdir(exist_ok=True)
    corner = corners[0]
    for gate in GATES:
        bits = next(b for g, b in CASES if g == gate and set(b) == {"1"})
        (NETLIST_DIR / f"{gate}.cir").write_text(build_netlist(gate, bits, corner, control=True))


def oracle_check(df):
    """Run the SPICE terminal currents through the leakage formula and compare with SPICE."""
    lines, worst = [], 0.0
    for include_inputs, target in [(False, df["i_supply"]),
                                   (True, df["i_supply"] + df["i_in_vdd"])]:
        summed = pd.Series(np.nan, index=df.index)
        for (gate, bits), g in df.groupby(["gate", "inputs"]):
            summed[g.index] = leakage(gate, bits, g, include_inputs)
        rel = ((summed - target).abs() / target.abs()).max()
        worst = max(worst, rel)
        name = "supply + inputs at VDD" if include_inputs else "supply only"
        lines.append(f"  {name:24s} max |formula - SPICE| / |SPICE| = {rel:.2e}")
    status = "PASS" if worst < ORACLE_TOL else "FAIL"
    return [f"Oracle check ({status}, limit {ORACLE_TOL:g}), {len(df)} simulations:"] + lines


def main():
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    corners = [{k: float(v) for k, v in row.items()} for row in load_corners().to_dict("records")]
    write_example_netlists(corners)

    jobs = [(gate, bits, corner) for gate, bits in CASES for corner in corners]
    results = run_jobs(jobs)
    failed = [(g, b, int(c["corner"])) for (g, b, c), r in zip(jobs, results) if r is None]
    if failed:
        raise RuntimeError(f"{len(failed)} simulations failed, e.g. {failed[:5]}")

    rows = [{"gate": g, "inputs": b, **c, **r} for (g, b, c), r in zip(jobs, results)]
    df = pd.DataFrame(rows)
    # Current delivered by the input sources held at VDD (gate tunnelling into the inputs)
    df["i_in_vdd"] = sum(np.where(df["inputs"].str[k] == "1", df[f"i_in_{n}"].fillna(0), 0.0)
                         for k, n in enumerate(["a", "b"]))
    df.to_csv(OUT_DIR / "spice_gates.csv", index=False)

    summary = oracle_check(df)
    summary += ["", "Output and internal node voltages / VDD (min .. max over corners):"]
    vcols = [c for c in df.columns if c.startswith("v_")]
    for (gate, bits), g in df.groupby(["gate", "inputs"], sort=False):
        parts = [f"{c[2:]} {(g[c] / g['vdd']).min():.4f}..{(g[c] / g['vdd']).max():.4f}"
                 for c in vcols if g[c].notna().all()]
        summary.append(f"  {gate:5s} {bits:2s}  " + "  ".join(parts))
    (OUT_DIR / "oracle_check.txt").write_text("\n".join(summary) + "\n")

    print("\n".join(summary))
    print(f"\n{len(df)} simulations -> {(OUT_DIR / 'spice_gates.csv').relative_to(config.ROOT)} "
          f"({time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()

"""Compare the independent .op pilot against the production DC sweep.

To regenerate the independent reference (about a minute):
python part4_circuit/simulate.py --method op --corners 0 1 --workers 2 --output results/part4/pilot
python part4_circuit/cross_check.py
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from circuit import GRAPH, ROOT
from corners import load_corners


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=ROOT / "results/part4/pilot/spice_circuit.csv.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "results/part4")
    parser.add_argument("--include-extremes", action="store_true",
                        help="also independently simulate selected vectors at PVT extremes")
    args = parser.parse_args()
    op = pd.read_csv(args.reference, dtype={"vector": str})
    if args.include_extremes:
        corners = load_corners()
        selected = {int(corners.loc[corners[p].idxmin(), "corner"])
                    for p in ("temp", "vdd", "nmos_vth0", "pmos_vth0")}
        selected |= {int(corners.loc[corners[p].idxmax(), "corner"])
                     for p in ("temp", "vdd", "nmos_vth0", "pmos_vth0")}
        vectors = sorted({"000000000", "111111111", "101010101", "010101010",
                          *(f"{1 << k:09b}" for k in range(9)),
                          *(f"{511 ^ (1 << k):09b}" for k in range(9))})
        extra = args.output / "pilot/extremes"
        subprocess.run([sys.executable, str(ROOT / "part4_circuit/simulate.py"), "--method", "op",
                        "--corners", *map(str, sorted(selected)), "--vectors", *vectors,
                        "--workers", "2", "--output", str(extra)], check=True)
        op = pd.concat([op, pd.read_csv(extra / "spice_circuit.csv.gz", dtype={"vector": str})], ignore_index=True)
        op = op.drop_duplicates(["corner", "vector"])
    dc = pd.read_csv(args.output / "spice_circuit.csv.gz", dtype={"vector": str})
    matched = op.merge(dc, on=["corner", "vector"], suffixes=("_op", "_dc"), validate="one_to_one")
    if len(matched) != len(op) or len(op) == 0:
        raise RuntimeError("production DC record does not cover the independent reference")
    supply_rel = ((matched.i_supply_op - matched.i_supply_dc).abs() / matched.i_supply_op.abs()).max()
    node_abs = max((matched[f"v_{out}_op"] - matched[f"v_{out}_dc"]).abs().max()
                   for out, _, _ in GRAPH)
    currents = [c for c in op if c.startswith("i_in_")]
    input_abs = max((matched[f"{c}_op"] - matched[f"{c}_dc"]).abs().max() for c in currents)
    if not np.isfinite([supply_rel, node_abs, input_abs]).all():
        raise RuntimeError("non-finite cross-check measurements")
    if supply_rel > 1e-5 or node_abs > 1e-6 or input_abs > 1e-12:
        raise RuntimeError(f"DC/.op mismatch: supply {supply_rel}, node {node_abs}, input {input_abs}")
    summary = {"status": "PASS", "cases": len(matched), "corners": sorted(op.corner.unique().astype(int).tolist()),
               "max_supply_relative_difference": supply_rel, "max_node_voltage_absolute_difference_V": node_abs,
               "max_input_current_absolute_difference_A": input_abs,
               "limits": {"supply_relative": 1e-5, "node_voltage_absolute_V": 1e-6,
                          "input_current_absolute_A": 1e-12}}
    (args.output / "op_dc_crosscheck.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

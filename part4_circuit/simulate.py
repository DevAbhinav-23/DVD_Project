"""Full-circuit operating points, batched per corner with resumable checkpoints.

python part4_circuit/simulate.py --corners 0 1 --workers 2 --output results/part4/smoke
python part4_circuit/simulate.py                    # all 512 x 200 cases
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import numpy as np
import pandas as pd

from circuit import (GRAPH, OUTPUT, PRIMARY, ROOT, all_vectors,
                     config, controlled_netlist, dc_netlist, logic)
from corners import load_corners


def parse_output(stdout, vectors):
    records, vector = {}, None
    for line in stdout.splitlines():
        marker = re.fullmatch(r"\s*@@vector ([01]+)\s*", line)
        if marker:
            vector = marker[1]
            if vector in records:
                raise RuntimeError(f"duplicate SPICE vector {vector}")
            records[vector] = {}
        match = re.fullmatch(r"\s*(\w+)\s*=\s*(\S+)\s*", line)
        if match and vector is not None:
            records[vector][match[1]] = float(match[2])
    expected = {"i_supply", *(f"i_in_{n}" for n in PRIMARY), *(f"v_{n}" for n, _, _ in GRAPH)}
    if set(records) != set(vectors):
        raise RuntimeError("SPICE did not return every requested vector")
    rows = []
    for vector in vectors:
        record = records[vector]
        if set(record) != expected or not np.isfinite(list(record.values())).all():
            raise RuntimeError(f"missing or non-finite measurements for {vector}")
        rows.append({"vector": vector, **record})
    return pd.DataFrame(rows)


def validate(df, corner, vectors):
    if len(df) != len(vectors) or df.vector.tolist() != vectors:
        raise RuntimeError("incomplete or unordered checkpoint")
    if not np.isfinite(df.select_dtypes(include="number").to_numpy()).all():
        raise RuntimeError("non-finite SPICE measurements")
    if (df.i_supply <= 0).any():
        raise RuntimeError("non-positive supply leakage")
    vdd = float(corner["vdd"])
    expected = np.array([[logic(v)[n] for n, _, _ in GRAPH] for v in vectors])
    actual = df[[f"v_{n}" for n, _, _ in GRAPH]].to_numpy() / vdd
    if all(f"v_input_{pin}" in df for pin in PRIMARY):
        input_volts = df[[f"v_input_{pin}" for pin in PRIMARY]].to_numpy() / vdd
        if not np.allclose(input_volts * vdd, [[int(b) * vdd for b in v] for v in vectors],
                           rtol=0, atol=config.CIRCUIT_INPUT_TOL_V):
            worst = np.max(np.abs(input_volts - [[int(b) for b in v] for v in vectors]))
            raise RuntimeError(f"decoded input sources are not at the requested rails (max {worst:g} VDD)")
    if not np.array_equal(actual > .5, expected.astype(bool)):
        raise RuntimeError(f"logic mismatch at corner {corner['corner']}")
    if (actual < -.01).any() or (actual > 1.01).any():
        raise RuntimeError("node voltage outside supply rails")
    return float(np.max(np.abs(actual - expected)))


def run_corner(job):
    corner, vectors, checkpoint_dir, method = job
    cid = int(corner["corner"])
    text = dc_netlist(corner) if method == "dc" else controlled_netlist(corner, vectors)
    # Invalidate a checkpoint on any netlist, vector, model, corner or simulator change.
    version = subprocess.check_output([config.NGSPICE, "--version"], text=True)
    digest = hashlib.sha256((text + version).encode()).hexdigest()[:20]
    checkpoint = Path(checkpoint_dir) / f"corner_{cid:03d}_{digest}.csv.gz"
    if checkpoint.exists():
        df = pd.read_csv(checkpoint, dtype={"vector": str})
        deviation = validate(df, corner, vectors)
        return cid, str(checkpoint), deviation, True
    with tempfile.TemporaryDirectory(prefix=f"dvd_part4_{cid}_") as tmp:
        netlist = Path(tmp) / "parity.cir"
        netlist.write_text(text)
        proc = subprocess.run([config.NGSPICE, "-b", str(netlist)],
                              cwd=tmp, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0 or re.search(r"(?im)^\s*error\b", proc.stderr):
            raise RuntimeError(f"corner {cid}: ngspice failed: {proc.stderr[-2000:]}")
        if method == "dc":
            df = pd.read_csv(Path(tmp) / "measurements.txt", sep=r"\s+")
            if len(df) != len(vectors) or not np.array_equal(df.iloc[:, 0], np.arange(len(vectors))):
                raise RuntimeError(f"corner {cid}: incomplete DC sweep")
            df = df.drop(columns=df.columns[0])
            df.insert(0, "vector", vectors)
        else:
            df = parse_output(proc.stdout, vectors)
    deviation = validate(df, corner, vectors)
    for key, value in corner.items():
        df[key] = value
    df["expected_error"] = [logic(v)[OUTPUT] for v in vectors]
    df["i_in_vdd"] = sum(np.where(df.vector.str[k] == "1", df[f"i_in_{pin}"], 0.)
                            for k, pin in enumerate(PRIMARY))
    temporary = checkpoint.with_name(checkpoint.name + ".tmp")
    df.to_csv(temporary, index=False, compression="gzip")
    temporary.replace(checkpoint)
    return cid, str(checkpoint), deviation, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corners", nargs="+", type=int)
    parser.add_argument("--vectors", nargs="+", help="nine bits: d0..d7, parity")
    parser.add_argument("--workers", type=int, default=config.CIRCUIT_WORKERS)
    parser.add_argument("--method", choices=["dc", "op"], default="dc",
                        help="dc batches all vectors; op independently initializes each vector")
    parser.add_argument("--output", type=Path, default=ROOT / "results/part4")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    vectors = args.vectors or all_vectors()
    if args.method == "dc" and vectors != all_vectors():
        parser.error("use --method op for a subset of vectors")
    if len(vectors) != len(set(vectors)):
        parser.error("duplicate vectors")
    for vector in vectors:
        logic(vector)
    corners = load_corners()
    if args.corners is not None:
        if len(set(args.corners)) != len(args.corners) or not set(args.corners) <= set(corners.corner):
            parser.error("unknown or duplicate corner IDs")
        corners = corners[corners.corner.isin(args.corners)]
    records = corners.to_dict("records")
    out = args.output.resolve()
    checkpoint_dir = out / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (out / "parity9_example.cir").write_text(controlled_netlist(records[0], [vectors[0]]))
    if args.method == "dc":
        (out / "parity9_dc.cir").write_text(dc_netlist(records[0]))
    started = time.monotonic()
    completed = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        remaining = iter(records)
        def submit_next():
            corner = next(remaining, None)
            if corner is None:
                return None
            return pool.submit(run_corner, (corner, vectors, str(checkpoint_dir), args.method))
        pending = {future for _ in range(min(args.workers, len(records)))
                   if (future := submit_next()) is not None}
        while pending:
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                try:
                    item = future.result()
                except Exception as exc:
                    print(f"Circuit sweep stopped: {exc}", flush=True)
                    for other in pending:
                        other.cancel()
                    raise
                completed.append(item)
                print(f"{len(completed)}/{len(records)} corners: {item[0]}, "
                      f"max node deviation {100 * item[2]:.3f}% VDD"
                      f"{' (cached)' if item[3] else ''}, {time.monotonic()-started:.1f}s", flush=True)
                following = submit_next()
                if following is not None:
                    pending.add(following)
    df = pd.concat([pd.read_csv(path, dtype={"vector": str})
                    for _, path, _, _ in sorted(completed)], ignore_index=True)
    if df.duplicated(["corner", "vector"]).any() or len(df) != len(records) * len(vectors):
        raise RuntimeError("duplicate or missing circuit cases")
    df.to_csv(out / "spice_circuit.csv.gz", index=False, compression="gzip")
    metadata = {"simulator": subprocess.check_output([config.NGSPICE, "--version"], text=True),
                "corners": len(records), "vectors": len(vectors), "simulations": len(df),
                "primary_input_order": PRIMARY, "nand2_count": len(GRAPH),
                "transistor_count": len(GRAPH) * 4, "logic_check": "all gate outputs PASS",
                "max_node_deviation_fraction_vdd": max(item[2] for item in completed),
                "elapsed_seconds": time.monotonic() - started,
                "cached_corners": sum(item[3] for item in completed),
                "newly_simulated_corners": sum(not item[3] for item in completed),
                "python": sys.version, "workers": args.workers,
                "solver": "SPARSE 1.3", "analysis_method": args.method,
                "ngspice_threads_per_worker": 1,
                "spice_options": config.SPICE_OPTIONS,
                "model_sha256": hashlib.sha256(config.MODEL_FILE.read_bytes()).hexdigest()}
    if args.method == "dc":
        expected = np.array([[int(b) for b in v] for v in df.vector]) * df.vdd.to_numpy()[:, None]
        metadata["max_primary_input_deviation_V"] = float(np.max(np.abs(
            df[[f"v_input_{pin}" for pin in PRIMARY]].to_numpy() - expected)))
    (out / "simulation_summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"PASS: {len(df)} complete circuit cases -> {out}")


if __name__ == "__main__":
    main()

"""Part 1: generate the four single-transistor datasets (data/<case>.csv).

Usage:  python part1_dataset/generate.py [--cases nmos_on ...] [--n 10000]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from spice_utils import CURRENTS, run_samples

MAX_REDRAW_ROUNDS = 10


def draw_samples(rng, n, case):
    """Draw n independent samples for one case. VDD is drawn first; Vd and Vs depend on it."""
    spec = config.CASES[case]
    nominal = config.NOMINAL[spec["type"]]

    vdd = config.VDD_NOM * rng.uniform(1 - config.VDD_VAR, 1 + config.VDD_VAR, n)
    cols = {
        "vdd": vdd,
        "temp": rng.uniform(config.TEMP_MIN, config.TEMP_MAX, n),
        "w": rng.uniform(config.W_MIN, config.W_MAX, n),
        "vd": rng.uniform(0, vdd),
        "vs": rng.uniform(0, vdd),
        "vg": vdd if spec["vg"] == "vdd" else np.full(n, float(spec["vg"])),
        "vb": vdd if spec["vb"] == "vdd" else np.full(n, float(spec["vb"])),
    }
    # Scale factor keeps the sign of negative nominals (PMOS vth0)
    for name in config.PROCESS_PARAMS:
        cols[name] = nominal[name] * rng.uniform(1 - config.PROCESS_VAR, 1 + config.PROCESS_VAR, n)

    return [{k: float(v[i]) for k, v in cols.items()} for i in range(n)]


def generate_case(case, n):
    """Simulate n good samples for one case, redrawing any that fail to converge."""
    rng = np.random.default_rng(config.SEEDS[case])
    mos_type = config.CASES[case]["type"]

    rows, redrawn, need = [], 0, n
    for _ in range(MAX_REDRAW_ROUNDS):
        samples = draw_samples(rng, need, case)
        for sample, currents in zip(samples, run_samples(samples, mos_type)):
            if currents is not None:
                rows.append({**sample, **currents})
        need = n - len(rows)
        if need == 0:
            break
        redrawn += need
    else:
        raise RuntimeError(f"{case}: still {need} failed samples after {MAX_REDRAW_ROUNDS} rounds")

    return pd.DataFrame(rows, columns=config.CSV_COLUMNS), redrawn


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", nargs="+", default=list(config.CASES), choices=list(config.CASES))
    parser.add_argument("--n", type=int, default=config.N_SAMPLES, help="samples per case")
    args = parser.parse_args()

    config.DATA_DIR.mkdir(exist_ok=True)
    for case in args.cases:
        t0 = time.time()
        df, redrawn = generate_case(case, args.n)
        out = config.DATA_DIR / f"{case}.csv"
        df.to_csv(out, index=False)

        print(f"\n{case}: {len(df)} rows -> {out.relative_to(config.ROOT)}  "
              f"(redrawn {redrawn}, {time.time() - t0:.1f} s)")
        for c in CURRENTS:
            mag = df[c].abs()
            print(f"  {c}: |I| from {mag.min():.3e} to {mag.max():.3e} A, "
                  f"median {mag.median():.3e} A, negative in {(df[c] < 0).mean():.0%} of rows")


if __name__ == "__main__":
    main()

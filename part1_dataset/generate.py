"""Part 1: generate the single-transistor datasets.

  data/<case>.csv           spec dataset: Vd, Vs uniform in [0, VDD]
  data/<case>_targeted.csv  targeted dataset: Vd, Vs where transistors sit inside static gates

Usage:  python part1_dataset/generate.py [--set uniform|targeted|both] [--cases nmos_on ...]
                                         [--n 10000] [--n-targeted 5000]
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

# Targeted sampling
ON_AT_RAIL = 0.5                # P(the reference terminal of an ON device sits on its rail)
ON_VDS_RANGE = (1e-7, 5e-2)     # V, |Vds| of ON devices, log-uniform (gate ON devices carry only leakage)
OFF_TERMINAL_P = {"zero": 0.3, "vdd": 0.3, "near_rail": 0.2, "uniform": 0.2}
NEAR_RAIL_RANGE = (1e-6, 1e-1)  # V, offset from a rail, log-uniform
GATE_W_P = 0.5                  # P(W = config.GATE_W), the width used in the gates


def _fixed_terminals(rng, n, case, vdd, cols):
    """Gate and body voltages are fixed by the case."""
    spec = config.CASES[case]
    cols["vg"] = vdd if spec["vg"] == "vdd" else np.full(n, float(spec["vg"]))
    cols["vb"] = vdd if spec["vb"] == "vdd" else np.full(n, float(spec["vb"]))


def _process_params(rng, n, case, cols):
    # Scale factor keeps the sign of negative nominals (PMOS vth0)
    nominal = config.NOMINAL[config.CASES[case]["type"]]
    for name in config.PROCESS_PARAMS:
        cols[name] = nominal[name] * rng.uniform(1 - config.PROCESS_VAR, 1 + config.PROCESS_VAR, n)


def _to_rows(cols, n):
    return [{k: float(v[i]) for k, v in cols.items()} for i in range(n)]


def draw_samples(rng, n, case):
    """Spec sampling: n independent samples. VDD is drawn first; Vd and Vs depend on it."""
    vdd = config.VDD_NOM * rng.uniform(1 - config.VDD_VAR, 1 + config.VDD_VAR, n)
    cols = {
        "vdd": vdd,
        "temp": rng.uniform(config.TEMP_MIN, config.TEMP_MAX, n),
        "w": rng.uniform(config.W_MIN, config.W_MAX, n),
        "vd": rng.uniform(0, vdd),
        "vs": rng.uniform(0, vdd),
    }
    _fixed_terminals(rng, n, case, vdd, cols)
    _process_params(rng, n, case, cols)
    return _to_rows(cols, n)


def _on_terminals(rng, n, mos_type, vdd):
    """ON device inside a gate: |Vds| tiny, one terminal often on the device's own rail."""
    rail = vdd if mos_type == "pmos" else np.zeros(n)
    v_ref = np.where(rng.random(n) < ON_AT_RAIL, rail, rng.uniform(0, vdd))
    vds = rng.choice([-1.0, 1.0], n) * 10 ** rng.uniform(*np.log10(ON_VDS_RANGE), n)
    v_other = v_ref + vds
    outside = (v_other < 0) | (v_other > vdd)
    v_other = np.where(outside, v_ref - vds, v_other)     # reflect back into [0, VDD]
    ref_is_source = rng.random(n) < 0.5
    return np.where(ref_is_source, v_other, v_ref), np.where(ref_is_source, v_ref, v_other)


def _off_terminal(rng, n, vdd):
    """One terminal of an OFF device: at a rail, just off a rail, or anywhere."""
    kinds = list(OFF_TERMINAL_P)
    kind = rng.choice(len(kinds), n, p=list(OFF_TERMINAL_P.values()))
    offset = 10 ** rng.uniform(*np.log10(NEAR_RAIL_RANGE), n)
    near = np.where(rng.random(n) < 0.5, offset, vdd - offset)
    choices = {"zero": np.zeros(n), "vdd": vdd, "near_rail": near, "uniform": rng.uniform(0, vdd)}
    return np.select([kind == k for k in range(len(kinds))], [choices[k] for k in kinds])


def draw_targeted_samples(rng, n, case):
    """Targeted sampling: terminal voltages at the operating points of transistors in static
    gates. Supply, temperature and process parameters are drawn exactly as in the spec."""
    mos_type = config.CASES[case]["type"]
    vdd = config.VDD_NOM * rng.uniform(1 - config.VDD_VAR, 1 + config.VDD_VAR, n)
    w = np.where(rng.random(n) < GATE_W_P, config.GATE_W[mos_type],
                 rng.uniform(config.W_MIN, config.W_MAX, n))
    if case.endswith("_on"):
        vd, vs = _on_terminals(rng, n, mos_type, vdd)
    else:
        vd, vs = _off_terminal(rng, n, vdd), _off_terminal(rng, n, vdd)
        # Both terminals on the same rail gives an all-terminals-equal device (zero current),
        # which never occurs in a gate: move the source just off that rail.
        offset = 10 ** rng.uniform(*np.log10(NEAR_RAIL_RANGE), n)
        vs = np.where(vd == vs, np.where(vd == 0, offset, vdd - offset), vs)
    cols = {"vdd": vdd, "temp": rng.uniform(config.TEMP_MIN, config.TEMP_MAX, n),
            "w": w, "vd": vd, "vs": vs}
    _fixed_terminals(rng, n, case, vdd, cols)
    _process_params(rng, n, case, cols)
    return _to_rows(cols, n)


def generate_case(case, n, targeted=False):
    """Simulate n good samples for one case, redrawing any that fail to converge."""
    rng = np.random.default_rng(config.SEEDS[f"{case}_targeted" if targeted else case])
    draw = draw_targeted_samples if targeted else draw_samples
    mos_type = config.CASES[case]["type"]

    rows, redrawn, need = [], 0, n
    for _ in range(MAX_REDRAW_ROUNDS):
        samples = draw(rng, need, case)
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
    parser.add_argument("--set", choices=["uniform", "targeted", "both"], default="both")
    parser.add_argument("--cases", nargs="+", default=list(config.CASES), choices=list(config.CASES))
    parser.add_argument("--n", type=int, default=config.N_SAMPLES, help="uniform samples per case")
    parser.add_argument("--n-targeted", type=int, default=config.N_TARGETED,
                        help="targeted samples per case")
    args = parser.parse_args()

    sets = {"uniform": [False], "targeted": [True], "both": [False, True]}[args.set]
    config.DATA_DIR.mkdir(exist_ok=True)
    for targeted in sets:
        for case in args.cases:
            t0 = time.time()
            n = args.n_targeted if targeted else args.n
            df, redrawn = generate_case(case, n, targeted)
            out = config.DATA_DIR / f"{case}{'_targeted' if targeted else ''}.csv"
            df.to_csv(out, index=False)

            print(f"\n{out.stem}: {len(df)} rows -> {out.relative_to(config.ROOT)}  "
                  f"(redrawn {redrawn}, {time.time() - t0:.1f} s)")
            for c in CURRENTS:
                mag = df[c].abs()
                print(f"  {c}: |I| from {mag.min():.3e} to {mag.max():.3e} A, "
                      f"median {mag.median():.3e} A, negative in {(df[c] < 0).mean():.0%} of rows")


if __name__ == "__main__":
    main()

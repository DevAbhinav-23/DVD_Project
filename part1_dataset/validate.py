"""Part 1: validate the datasets (KCL, sanity, coverage, trend plots) -> results/part1/.

Usage:  python part1_dataset/validate.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from spice_utils import CURRENTS, run_batch

OUT_DIR = config.RESULTS_DIR / "part1"
SWEEP_POINTS = 41
SWEEP_W = 44e-9                 # same width as the example netlists
# KCL passes when |Id+Ig+Is+Ib| <= KCL_LIMIT * max|I| + KCL_ABS (same form as SPICE's
# reltol / abstol). KCL_LIMIT is 10x below the 1% accuracy target. The residual is a few-fA
# floor from the BSIM4 current bookkeeping (unchanged with 1000x tighter tolerances), so it only
# matters for rows where every current is in the pA range; KCL_ABS = 0.1% of 0.1 nA, below
# which no gate leakage we evaluate lies.
KCL_LIMIT = 1e-3
KCL_ABS = 1e-13                 # A

# data/<case>.csv: N_SAMPLES uniform rows followed by N_TARGETED targeted rows
SETS = {"uniform": config.N_SAMPLES, "targeted": config.N_TARGETED}

# Gate operating points (fractions of VDD) used for the coverage table
ON_VDS_MAX = 4e-3               # V, |Vds| of an ON device that carries only leakage
RAIL_TOL = 0.01                 # within 1% of VDD counts as "at the rail"

# Plot styling
SAMPLE_COLOR = "#2a78d6"        # dataset scatter / uniform set
SWEEP_COLOR = "#eb6834"         # controlled sweep line / targeted set
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "axes.titlecolor": INK,
    "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "legend.frameon": False,
})

log_lines = []


def log(msg=""):
    print(msg)
    log_lines.append(msg)


def load_datasets():
    """{set: {case: DataFrame}}: the uniform and targeted parts of each data/<case>.csv."""
    sets = {s: {} for s in SETS}
    for case in config.CASES:
        df = pd.read_csv(config.DATA_DIR / f"{case}.csv")
        if len(df) != sum(SETS.values()):
            raise SystemExit(f"{case}.csv: expected {sum(SETS.values())} rows, found {len(df)}")
        sets["uniform"][case] = df.iloc[:config.N_SAMPLES].reset_index(drop=True)
        sets["targeted"][case] = df.iloc[config.N_SAMPLES:].reset_index(drop=True)
    return sets


def kcl_residual(df):
    currents = df[CURRENTS].to_numpy()
    residual = np.abs(currents.sum(axis=1))
    return residual, np.abs(currents).max(axis=1)


# ---------------------------------------------------------------- checks
def kcl_check(sets):
    rows = []
    for s, data in sets.items():
        for case, df in data.items():
            residual, scale = kcl_residual(df)
            rel = residual / scale
            rows.append({"set": s, "case": case, "rows": len(df),
                         "median_rel": np.median(rel), "p95_rel": np.percentile(rel, 95),
                         "max_rel": rel.max(), "max_abs_A": residual.max(),
                         "pass": bool((residual <= KCL_LIMIT * scale + KCL_ABS).all())})
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "kcl_summary.csv", index=False)

    log(f"KCL check: pass if |Id+Ig+Is+Ib| <= {KCL_LIMIT:g} * max|I| + {KCL_ABS:g} A")
    log(table.to_string(index=False, float_format=lambda x: f"{x:.2e}"))
    return table


def sanity_checks(sets):
    """Row count, NaNs, parameter ranges and fixed Vg/Vb for every dataset."""
    log("\nSanity checks")
    ok_all = True
    for s, data in sets.items():
        ok_all &= _sanity_checks(data, SETS[s], s)
    return ok_all


def _sanity_checks(data, n_rows, set_name):
    ok_all = True
    for case, df in data.items():
        spec = config.CASES[case]
        nominal = config.NOMINAL[spec["type"]]
        vdd = df["vdd"]
        checks = {
            "row count": len(df) == n_rows,
            "no NaN": not df.isna().any().any(),
            "vdd range": vdd.between(config.VDD_NOM * (1 - config.VDD_VAR),
                                     config.VDD_NOM * (1 + config.VDD_VAR)).all(),
            "vd, vs in [0, vdd]": ((df["vd"] >= 0) & (df["vd"] <= vdd)
                                   & (df["vs"] >= 0) & (df["vs"] <= vdd)).all(),
            "w range": df["w"].between(config.W_MIN, config.W_MAX).all(),
            "temp range": df["temp"].between(config.TEMP_MIN, config.TEMP_MAX).all(),
            "vg fixed": np.allclose(df["vg"], vdd if spec["vg"] == "vdd" else spec["vg"]),
            "vb fixed": np.allclose(df["vb"], vdd if spec["vb"] == "vdd" else spec["vb"]),
        }
        for name in config.PROCESS_PARAMS:
            ratio = df[name] / nominal[name]
            checks[f"{name} +/-10%"] = ratio.between(1 - config.PROCESS_VAR, 1 + config.PROCESS_VAR).all()
        failed = [k for k, v in checks.items() if not v]
        ok_all &= not failed
        log(f"  {set_name:9s} {case:9s} {'PASS' if not failed else 'FAIL: ' + ', '.join(failed)}")
    return ok_all


def gate_operating_points(df, case):
    """Boolean masks of rows at the operating points transistors have inside static gates."""
    mos_type = config.CASES[case]["type"]
    vdd, vd, vs = df["vdd"], df["vd"], df["vs"]
    at_vdd = lambda v: v >= (1 - RAIL_TOL) * vdd
    at_zero = lambda v: v <= RAIL_TOL * vdd
    if case.endswith("_on"):
        own_rail = at_vdd if mos_type == "pmos" else at_zero
        small = (vd - vs).abs() < ON_VDS_MAX
        return {f"|Vds| < {ON_VDS_MAX * 1e3:g} mV": small,
                f"|Vds| < {ON_VDS_MAX * 1e3:g} mV, terminal on rail": small & (own_rail(vd) | own_rail(vs))}
    full_rail = (at_vdd(vd) & at_zero(vs)) | (at_zero(vd) & at_vdd(vs))
    return {"terminals on opposite rails": full_rail,
            "one terminal on a rail": at_vdd(vd) | at_zero(vd) | at_vdd(vs) | at_zero(vs)}


def coverage_table(sets):
    rows = []
    for case in config.CASES:
        for label in gate_operating_points(sets["uniform"][case], case):
            row = {"case": case, "operating point": label}
            for s, data in sets.items():
                row[f"{s} rows"] = int(gate_operating_points(data[case], case)[label].sum())
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "coverage.csv", index=False)
    log(f"\nCoverage of gate operating points (rail = within {RAIL_TOL:.0%} of 0 or VDD)")
    log(table.to_string(index=False))
    return table


# ---------------------------------------------------------------- controlled sweeps
def nominal_sample(case):
    """Nominal corner with |Vds| = VDD (NMOS: drain high, PMOS: source high)."""
    spec = config.CASES[case]
    mos_type = spec["type"]
    vdd = config.VDD_NOM
    vd, vs = (vdd, 0.0) if mos_type == "nmos" else (0.0, vdd)
    return {"vdd": vdd, "temp": 27.0, "w": SWEEP_W, "vd": vd, "vs": vs,
            "vg": vdd if spec["vg"] == "vdd" else float(spec["vg"]),
            "vb": vdd if spec["vb"] == "vdd" else float(spec["vb"]),
            **config.NOMINAL[mos_type]}


def sweep(case, param, values):
    base = nominal_sample(case)
    results = run_batch([{**base, param: float(v)} for v in values], config.CASES[case]["type"])
    return pd.DataFrame(results)


def param_values(case, param):
    if param == "temp":
        return np.linspace(config.TEMP_MIN, config.TEMP_MAX, SWEEP_POINTS)
    nom = config.NOMINAL[config.CASES[case]["type"]][param]
    return nom * np.linspace(1 - config.PROCESS_VAR, 1 + config.PROCESS_VAR, SWEEP_POINTS)


# ---------------------------------------------------------------- plots
def trend_plot(data, cases, param, current, xlabel, ylabel, title, filename, xscale=1.0):
    """One panel per case: dataset scatter plus the controlled sweep on log y."""
    fig, axes = plt.subplots(1, len(cases), figsize=(5.2 * len(cases), 4.2), squeeze=False)
    trends = {}
    for ax, case in zip(axes[0], cases):
        df = data[case]
        ax.scatter(df[param] * xscale, df[current].abs(), s=3, alpha=0.15,
                   color=SAMPLE_COLOR, linewidths=0, label="dataset samples", rasterized=True)

        x = param_values(case, param)
        y = sweep(case, param, x)[current].abs().to_numpy()
        ax.plot(x * xscale, y, color=SWEEP_COLOR, linewidth=2,
                label=r"controlled sweep (nominal, $|V_{ds}|$ = VDD)")
        trends[case] = np.sign(np.diff(y)) * np.sign(np.diff(x))   # trend vs the value, not sweep order

        ax.set_yscale("log")
        ax.set_title(case.replace("_", " ").upper())
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
    axes[0][0].legend(loc="best", markerscale=4)
    fig.suptitle(title, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=150)
    plt.close(fig)
    return trends


def kcl_plot(sets):
    """Residual divided by the allowed residual: a sample passes when the ratio is <= 1."""
    fig, axes = plt.subplots(len(sets), 4, figsize=(16, 3.4 * len(sets)), sharex=True)
    bins = np.linspace(-14, 1, 61)
    for row, (s, data) in zip(axes, sets.items()):
        for ax, (case, df) in zip(row, data.items()):
            residual, scale = kcl_residual(df)
            ratio = residual / (KCL_LIMIT * scale + KCL_ABS)
            ax.hist(np.log10(np.maximum(ratio, 1e-14)), bins=bins, color=SAMPLE_COLOR,
                    edgecolor="#fcfcfb", linewidth=0.5)
            ax.axvline(0, color=INK_2, linewidth=1)
            ax.text(0, 0.97, "limit ", color=INK_2, va="top", ha="right",
                    transform=ax.get_xaxis_transform())
            ax.set_title(f"{case.replace('_', ' ').upper()}  ({s})")
        row[0].set_ylabel("samples")
    for ax in axes[-1]:
        ax.set_xlabel(r"log$_{10}$ ( |Id+Ig+Is+Ib| / allowed )")
    fig.suptitle(f"Kirchhoff check: residual / ({KCL_LIMIT:g}·max|I| + {KCL_ABS:g} A) per sample",
                 fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "kcl_check.png", dpi=150)
    plt.close(fig)


def coverage_plot(sets):
    """Vd vs Vs (as fractions of VDD) for the uniform and targeted sets."""
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.4))
    colors = {"uniform": SAMPLE_COLOR, "targeted": SWEEP_COLOR}
    for ax, case in zip(axes, config.CASES):
        for s, data in sets.items():
            df = data[case]
            ax.scatter(df["vs"] / df["vdd"], df["vd"] / df["vdd"], s=3, alpha=0.25, linewidths=0,
                       color=colors[s], label=f"{s} ({len(df):,})", rasterized=True)
        ax.set_title(case.replace("_", " ").upper())
        ax.set_xlabel("Vs / VDD")
        ax.set_aspect("equal")
    axes[0].set_ylabel("Vd / VDD")
    axes[0].legend(loc="upper left", markerscale=5)
    fig.suptitle("Terminal-voltage coverage: uniform (spec) vs targeted (gate operating points)",
                 fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "coverage.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def describe(trend):
    if np.all(trend > 0):
        return "increasing"
    if np.all(trend < 0):
        return "decreasing"
    return "not monotonic"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sets = load_datasets()
    data = sets["uniform"]

    kcl = kcl_check(sets)
    sane = sanity_checks(sets)
    kcl_plot(sets)
    coverage_table(sets)
    coverage_plot(sets)

    log("\nTrend checks (controlled sweeps, uniform dataset scatter)")
    expected = []
    t = trend_plot(data, ["nmos_off", "pmos_off"], "temp", "id",
                   "temperature (°C)", "|Id| (A)", "OFF current vs temperature",
                   "off_current_vs_temp.png")
    expected += [(f"|Ioff| vs temp, {c}", t[c], "increasing") for c in t]

    t = trend_plot(data, ["nmos_off", "pmos_off"], "vth0", "id",
                   "vth0 (V)", "|Id| (A)", "OFF current vs vth0",
                   "off_current_vs_vth0.png")
    # PMOS vth0 is negative: |Ioff| falls as |vth0| grows, i.e. rises as vth0 increases
    expected += [("|Ioff| vs vth0, nmos_off", t["nmos_off"], "decreasing"),
                 ("|Ioff| vs vth0, pmos_off", t["pmos_off"], "increasing")]

    t = trend_plot(data, list(config.CASES), "toxe", "ig",
                   "toxe (nm)", "|Ig| (A)", "Gate current vs toxe",
                   "gate_current_vs_toxe.png", xscale=1e9)
    expected += [(f"|Ig| vs toxe, {c}", t[c], "decreasing") for c in t]

    trends_ok = True
    for name, trend, want in expected:
        got = describe(trend)
        trends_ok &= got == want
        log(f"  {name:28s} {got:14s} {'PASS' if got == want else 'FAIL (expected ' + want + ')'}")

    log(f"\nOverall: KCL {'PASS' if kcl['pass'].all() else 'FAIL'}, "
        f"sanity {'PASS' if sane else 'FAIL'}, trends {'PASS' if trends_ok else 'FAIL'}")
    (OUT_DIR / "validation_summary.txt").write_text("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()

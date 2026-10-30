"""Part 1: validate the datasets (KCL check, sanity checks, trend plots) -> results/part1/.

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
# Max allowed |Id+Ig+Is+Ib| / max|I|: 10x below the 1% accuracy target. The residual is a
# few-fA floor from the BSIM4 current bookkeeping (unchanged with 1000x tighter tolerances),
# so it only matters for rows where every current is in the pA range.
KCL_LIMIT = 1e-3

# Plot styling
SAMPLE_COLOR = "#2a78d6"        # dataset scatter
SWEEP_COLOR = "#eb6834"         # controlled sweep line
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
    return {case: pd.read_csv(config.DATA_DIR / f"{case}.csv") for case in config.CASES}


# ---------------------------------------------------------------- checks
def kcl_check(data):
    rows = []
    for case, df in data.items():
        currents = df[CURRENTS].to_numpy()
        residual = np.abs(currents.sum(axis=1))
        rel = residual / np.abs(currents).max(axis=1)
        rows.append({"case": case, "rows": len(df),
                     "median_rel": np.median(rel), "p95_rel": np.percentile(rel, 95),
                     "max_rel": rel.max(), "max_abs_A": residual.max(),
                     "pass": bool(rel.max() < KCL_LIMIT)})
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "kcl_summary.csv", index=False)

    log(f"KCL check: |Id+Ig+Is+Ib| / max|I|  (limit {KCL_LIMIT:g})")
    log(table.to_string(index=False, float_format=lambda x: f"{x:.2e}"))
    return table


def sanity_checks(data):
    """Row count, NaNs, parameter ranges and fixed Vg/Vb for every case."""
    log("\nSanity checks")
    ok_all = True
    for case, df in data.items():
        spec = config.CASES[case]
        nominal = config.NOMINAL[spec["type"]]
        vdd = df["vdd"]
        checks = {
            "row count": len(df) == config.N_SAMPLES,
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
        log(f"  {case:9s} {'PASS' if not failed else 'FAIL: ' + ', '.join(failed)}")
    return ok_all


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


def kcl_plot(data):
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.6), sharey=True)
    bins = np.linspace(-20, -4, 65)
    for ax, (case, df) in zip(axes, data.items()):
        currents = df[CURRENTS].to_numpy()
        rel = np.abs(currents.sum(axis=1)) / np.abs(currents).max(axis=1)
        ax.hist(np.log10(np.maximum(rel, 1e-20)), bins=bins, color=SAMPLE_COLOR,
                edgecolor="#fcfcfb", linewidth=0.5)
        ax.axvline(np.log10(KCL_LIMIT), color=INK_2, linewidth=1)
        ax.text(np.log10(KCL_LIMIT), 0.97, "limit ", color=INK_2, va="top", ha="right",
                transform=ax.get_xaxis_transform())
        ax.set_title(case.replace("_", " ").upper())
        ax.set_xlabel(r"log$_{10}$ ( |Id+Ig+Is+Ib| / max|I| )")
    axes[0].set_ylabel("samples")
    fig.suptitle("Kirchhoff check: relative current residual per sample", fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "kcl_check.png", dpi=150)
    plt.close(fig)


def describe(trend):
    if np.all(trend > 0):
        return "increasing"
    if np.all(trend < 0):
        return "decreasing"
    return "not monotonic"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_datasets()

    kcl = kcl_check(data)
    sane = sanity_checks(data)
    kcl_plot(data)

    log("\nTrend checks (controlled sweeps)")
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

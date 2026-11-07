"""Part 2: run the saved models on the held-out test rows -> results/part2/test_predictions.csv

One row per test sample and case, with the inputs, the SPICE current, the ML prediction and
the relative error for each terminal, plus an error-distribution plot.

Usage:  python part2_models/evaluate_test.py      (run train_compare.py first)
"""
import sys
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_compare import CASES, OUT_DIR, TARGETS, load_datasets  # noqa: E402
from leakage_model import I_FLOOR, INPUTS, load_case_model  # noqa: E402
import config  # noqa: E402  (path added by train_compare)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore")
COLORS = dict(zip(TARGETS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))


def main():
    frames = []
    for case in CASES:
        model = load_case_model(OUT_DIR / "models" / f"{case}.joblib")
        for set_name, df in load_datasets(case).items():
            te = pd.read_csv(OUT_DIR / "splits" / f"{case}_{set_name}_test_idx.csv").row.values
            test = df.iloc[te]
            pred = model.predict(test)
            out = test[INPUTS].copy()
            out.insert(0, "row", te)
            out.insert(0, "test_set", set_name)
            out.insert(0, "case", case)
            for t in TARGETS:
                out[f"{t}_spice"] = test[t]
                out[f"{t}_ml"] = pred[t]
                # relative error is undefined for SPICE currents at the numerical floor
                out[f"{t}_err_pct"] = np.where(test[t].abs() >= I_FLOOR,
                                               100 * np.abs(pred[t] - test[t]) / np.abs(test[t]), np.nan)
            frames.append(out)
    res = pd.concat(frames, ignore_index=True)
    res.to_csv(OUT_DIR / "test_predictions.csv", index=False)

    rows = []
    for (case, set_name), g in res.groupby(["case", "test_set"], sort=False):
        for t in TARGETS:
            e = g[f"{t}_err_pct"].dropna()
            rows.append({"case": case, "test_set": set_name, "terminal": t, "n": len(e), "median_err_pct": e.median(),
                         "p95_err_pct": e.quantile(0.95), "within_1pct": (e < 1).mean() * 100,
                         "within_5pct": (e < 5).mean() * 100, "within_10pct": (e < 10).mean() * 100})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_DIR / "test_summary.csv", index=False)
    print(summary.round(2).to_string(index=False))

    fig, axes = plt.subplots(1, 4, figsize=(16, 3.8), sharey=True)
    bins = np.logspace(-4, 3, 50)
    for ax, case in zip(axes, CASES):
        g = res[(res.case == case) & (res.test_set == "targeted")]
        for t in TARGETS:
            ax.hist(np.clip(g[f"{t}_err_pct"].dropna(), 1e-4, 1e3), bins=bins, histtype="step", lw=1.8,
                    color=COLORS[t], label=t)
        ax.axvline(1, color="#898781", lw=1, ls="--")
        ax.set_xscale("log")
        ax.set_title(case, fontsize=10)
        ax.set_xlabel("Relative error (%)")
        ax.grid(color="#e1e0d9", lw=0.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel("Test samples")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.92))
    fig.suptitle("Relative error on the targeted (gate operating point) test set (dashed line = 1%)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(OUT_DIR / "plots" / "test_error_hist.png", dpi=130)
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'test_predictions.csv'}")


if __name__ == "__main__":
    main()

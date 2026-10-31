"""Part 2: learning curve of the chosen model per case -> results/part2/learning_curve.*

Retrains each case's chosen family (from test_metrics.csv) on nested random subsets of
the training split and scores every fit on the same, untouched test split. The
validation split stays whole, since it drives early stopping and the grid choice.

Usage:  python part2_models/learning_curve.py      (run train_compare.py first)
"""
import sys
import warnings
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_compare import CASES, GRIDS, OUT_DIR, SEED, TARGETS, metrics, split_idx, train_family  # noqa: E402
from leakage_model import make_features, to_log  # noqa: E402
import config  # noqa: E402  (path added by train_compare)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

warnings.filterwarnings("ignore")
SIZES = [1000, 2000, 5000, 7000]
COLORS = dict(zip(CASES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))


def plot(lc):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, col, lab in zip(axes, ["median_err_pct", "p95_err_pct"],
                            ["Median relative error (%)", "95th-percentile relative error (%)"]):
        for case in CASES:
            s = lc[lc.case == case]
            ax.plot(s.n_train, s[col], marker="o", ms=6, lw=2, color=COLORS[case], label=case)
        ax.set_xscale("log"), ax.set_yscale("log")
        ax.set_xticks(SIZES, [f"{n // 1000}k" for n in SIZES])
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel("Training samples")
        ax.set_title(lab + " (test set, mean of 4 terminals)", fontsize=10)
        ax.grid(color="#e1e0d9", lw=0.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.5, 0.93))
    fig.suptitle("Learning curve of the chosen model per case", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(OUT_DIR / "plots" / "learning_curve.png", dpi=130)
    plt.close(fig)


def main():
    chosen = pd.read_csv(OUT_DIR / "test_metrics.csv").groupby("case").family.first()
    rows = []
    for case in CASES:
        fam = chosen[case]
        df = pd.read_csv(config.DATA_DIR / f"{case}.csv")
        tr, va, te = split_idx(len(df))
        X = make_features(df)
        X = X.loc[:, X.iloc[tr].nunique() > 1]
        Y = df[TARGETS].apply(to_log)
        order = np.random.default_rng(SEED).permutation(tr)  # nested subsets: 1k within 2k within ...
        for n in SIZES:
            sub = order[:n]
            cm, _ = train_family(fam, GRIDS[fam], X.iloc[sub], Y.iloc[sub], X.iloc[va], Y.iloc[va],
                                 df[TARGETS].iloc[sub])
            pred = cm.predict(df.iloc[te])
            ms = [metrics(df[t].iloc[te].values, pred[t].values) for t in TARGETS]
            row = {"case": case, "family": fam, "n_train": n,
                   "median_err_pct": np.mean([m["median_err_pct"] for m in ms]),
                   "p95_err_pct": np.mean([m["p95_err_pct"] for m in ms]),
                   "mean_err_pct": np.mean([m["mean_err_pct"] for m in ms])}
            rows.append(row)
            print(f"{case:9s} {fam:14s} n={n:5d}  median {row['median_err_pct']:.3f}%  p95 {row['p95_err_pct']:.2f}%",
                  flush=True)

    lc = pd.DataFrame(rows)
    lc.to_csv(OUT_DIR / "learning_curve.csv", index=False)
    plot(lc)
    print(f"Wrote {OUT_DIR / 'learning_curve.csv'}")


if __name__ == "__main__":
    main()

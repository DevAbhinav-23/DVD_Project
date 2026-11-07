"""Part 2: learning curve of the chosen model per case -> results/part2/learning_curve.*

Retrains each case's chosen family (from test_metrics.csv) on nested random subsets of
the training split and scores every fit on the same, untouched test splits. Data and split
are those of train_compare.py: uniform + targeted rows, each dataset split 70/15/15 with the
same seed, so the largest size is the full training split of the saved models. The
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
from train_compare import (CASES, GRIDS, OUT_DIR, SEED, TARGETS, load_datasets, metrics,  # noqa: E402
                           split_idx, train_family)
from leakage_model import make_features, to_log  # noqa: E402
import config  # noqa: E402  (path added by train_compare)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

warnings.filterwarnings("ignore")
SIZES = [1000, 2000, 5000]  # plus the full training split (7,000 rows per case)
COLORS = dict(zip(CASES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))
LINESTYLES = {"uniform": "-", "targeted": "--"}


def load_case(case):
    """All rows of one case plus train / val / per-dataset test indices, as in train_compare.py."""
    parts, tr, va, tests, offset = [], [], [], {}, 0
    for set_name, d in load_datasets(case).items():
        s_tr, s_va, s_te = split_idx(len(d))
        tr.append(s_tr + offset)
        va.append(s_va + offset)
        tests[set_name] = s_te + offset
        parts.append(d)
        offset += len(d)
    return pd.concat(parts, ignore_index=True), np.concatenate(tr), np.concatenate(va), tests


def plot(lc):
    sizes = sorted(lc.n_train.unique())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, col, lab in zip(axes, ["median_err_pct", "p95_err_pct"],
                            ["Median relative error (%)", "95th-percentile relative error (%)"]):
        for case in CASES:
            for set_name, ls in LINESTYLES.items():
                s = lc[(lc.case == case) & (lc.test_set == set_name)]
                ax.plot(s.n_train, s[col], marker="o", ms=5, lw=2, ls=ls, color=COLORS[case],
                        label=f"{case} ({set_name} test)")
        ax.set_xscale("log"), ax.set_yscale("log")
        ax.set_xticks(sizes, [f"{n / 1000:g}k" for n in sizes])
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel("Training samples")
        ax.set_title(lab + " (test set, mean of 4 terminals)", fontsize=10)
        ax.grid(color="#e1e0d9", lw=0.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.95))
    fig.suptitle("Learning curve of the chosen model per case", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(OUT_DIR / "plots" / "learning_curve.png", dpi=130)
    plt.close(fig)


def main():
    chosen = pd.read_csv(OUT_DIR / "test_metrics.csv").groupby("case").family.first()
    rows = []
    for case in CASES:
        fam = chosen[case]
        df, tr, va, tests = load_case(case)
        X = make_features(df)
        X = X.loc[:, X.iloc[tr].nunique() > 1]
        Y = df[TARGETS].apply(to_log)
        order = np.random.default_rng(SEED).permutation(tr)  # nested subsets: 1k within 2k within ...
        for n in SIZES + [len(tr)]:
            sub = order[:n]
            cm, _ = train_family(fam, GRIDS[fam], X.iloc[sub], Y.iloc[sub], X.iloc[va], Y.iloc[va],
                                 df[TARGETS].iloc[sub])
            for set_name, te in tests.items():
                pred = cm.predict(df.iloc[te])
                ms = [metrics(df[t].iloc[te].values, pred[t].values) for t in TARGETS]
                row = {"case": case, "test_set": set_name, "family": fam, "n_train": n,
                       "median_err_pct": np.mean([m["median_err_pct"] for m in ms]),
                       "p95_err_pct": np.mean([m["p95_err_pct"] for m in ms]),
                       "mean_err_pct": np.mean([m["mean_err_pct"] for m in ms])}
                rows.append(row)
                print(f"{case:9s} {fam:14s} n={n:5d} {set_name:8s} test  median {row['median_err_pct']:.3f}%"
                      f"  p95 {row['p95_err_pct']:.2f}%", flush=True)

    lc = pd.DataFrame(rows)
    lc.to_csv(OUT_DIR / "learning_curve.csv", index=False)
    plot(lc)
    print(f"Wrote {OUT_DIR / 'learning_curve.csv'}")


if __name__ == "__main__":
    main()

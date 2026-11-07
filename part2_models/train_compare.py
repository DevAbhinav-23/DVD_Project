"""Part 2: train and compare 4 model families on the 4 transistor cases -> results/part2/.

Usage:  python part2_models/train_compare.py            (about 45 min on 4 cores)
        python part2_models/train_compare.py --fast     (one config per family, smoke test)

For each case: fixed-seed 70/15/15 split -> for each family, tune a small grid on the
validation set (per terminal, log10|I| MAE) -> compare families on validation
(R^2, median and 95th-percentile relative error) -> pick the best family per case ->
report it on the untouched test set, save it, and draw predicted-vs-SPICE plots.

Outputs (in --out, default results/part2/):
  comparison_table.csv / .md     4 families x 4 cases x 4 terminals, validation set
  test_metrics.csv / .md         chosen model per case, test set
  models/<case>.joblib           CaseModel objects (see leakage_model.py)
  plots/parity_<case>.png        predicted vs SPICE, test set, log axes
  plots/family_comparison.png    validation error per family and case
  splits/<case>_<split>_idx.csv  row indices of each split (reproducibility)
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from leakage_model import I_FLOOR, INPUTS, TARGETS, CaseModel, Column, SignModel, make_features, to_log  # noqa: E402

CASES = list(config.CASES)
SEED = config.SEEDS["split"]
SPLIT = (0.70, 0.15, 0.15)  # train / val / test, applied to each dataset separately
# data/<case>.csv holds config.N_SAMPLES uniform rows (Vd, Vs uniform) followed by config.N_TARGETED
# targeted rows (gate operating points). The two parts are split separately with the same seed and
# combined, so each test slice can be reported on its own.
DATASETS = ("uniform", "targeted")


def load_datasets(case, data_dir=config.DATA_DIR):
    """{"uniform": DataFrame, "targeted": DataFrame}: the two parts of data/<case>.csv."""
    df = pd.read_csv(Path(data_dir) / f"{case}.csv")
    if len(df) != config.N_SAMPLES + config.N_TARGETED:
        raise SystemExit(f"{case}.csv: expected {config.N_SAMPLES} + {config.N_TARGETED} rows, "
                         f"found {len(df)}")
    return {"uniform": df.iloc[:config.N_SAMPLES].reset_index(drop=True),
            "targeted": df.iloc[config.N_SAMPLES:].reset_index(drop=True)}
OUT_DIR = config.RESULTS_DIR / "part2"

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore")  # LightGBM deprecation and L-BFGS iteration-limit noise
FAMILIES = ["poly_ridge", "random_forest", "lightgbm", "mlp"]  # xgboost also available via --families
COLORS = {"poly_ridge": "#2a78d6", "random_forest": "#eb6834", "lightgbm": "#1baf7a", "mlp": "#eda100",
          "xgboost": "#e87ba4"}
MULTI_OUTPUT = {"mlp", "poly_ridge"}  # one model with 4 outputs; the tree families fit one model per terminal
SIGN_MIXED_MIN = 0.002  # treat a terminal's sign as constant if the minority is rarer than this


# ---------------------------------------------------------------- metrics
def metrics(i_true, i_pred):
    # Rows whose SPICE current is below the noise floor have no meaningful relative error.
    keep = np.abs(i_true) >= I_FLOOR
    i_true, i_pred = i_true[keep], i_pred[keep]
    rel = np.abs(i_pred - i_true) / np.abs(i_true)
    lt, lp = to_log(i_true), to_log(i_pred)
    r2_log = 1 - np.sum((lt - lp) ** 2) / np.sum((lt - lt.mean()) ** 2)
    r2_lin = 1 - np.sum((i_true - i_pred) ** 2) / np.sum((i_true - i_true.mean()) ** 2)
    return {
        "r2_log": r2_log, "r2_lin": r2_lin,
        "median_err_pct": 100 * np.median(rel), "p95_err_pct": 100 * np.percentile(rel, 95),
        "mean_err_pct": 100 * np.mean(np.minimum(rel, 1.0)),  # capped at 100% per sample
        "sign_acc": np.mean(np.sign(i_true) == np.sign(i_pred)),
        "n_below_floor": int((~keep).sum()),
    }


# ---------------------------------------------------------------- model families
def _lgb_reg(params, Xtr, ytr, Xva, yva):
    m = lgb.LGBMRegressor(n_estimators=8000, learning_rate=0.03, subsample=0.8, subsample_freq=1,
                          colsample_bytree=0.8, min_child_samples=10, reg_lambda=1e-3,
                          random_state=SEED, n_jobs=-1, verbose=-1, **params)
    m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="l1",
          callbacks=[lgb.early_stopping(300, verbose=False)])
    return m


def _xgb_reg(params, Xtr, ytr, Xva, yva):
    import xgboost as xgb
    m = xgb.XGBRegressor(n_estimators=8000, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                         min_child_weight=2, tree_method="hist", random_state=SEED, n_jobs=-1,
                         early_stopping_rounds=300, eval_metric="mae", **params)
    m.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    return m


def _rf_reg(params, Xtr, ytr, Xva, yva):
    return RandomForestRegressor(n_estimators=400, random_state=SEED, n_jobs=-1, **params).fit(Xtr, ytr)


def _mlp_reg(params, Xtr, Ytr, Xva, Yva):
    # Full-batch L-BFGS converges far more precisely than Adam on these smooth maps
    # (about 2x lower median error in tests), at the cost of no early stopping.
    net = MLPRegressor(activation="tanh", solver="lbfgs", max_iter=2500, max_fun=100000, tol=1e-12,
                       random_state=SEED, **params)
    return TransformedTargetRegressor(regressor=make_pipeline(StandardScaler(), net),
                                      transformer=StandardScaler()).fit(Xtr, Ytr)


def _poly_reg(params, Xtr, Ytr, Xva, Yva):
    p = make_pipeline(StandardScaler(), PolynomialFeatures(params["degree"]), StandardScaler(),
                      Ridge(alpha=params["alpha"]))
    return TransformedTargetRegressor(regressor=p, transformer=StandardScaler()).fit(Xtr, Ytr)


GRIDS = {
    "poly_ridge": [dict(degree=2, alpha=1e-3), dict(degree=3, alpha=1e-2), dict(degree=3, alpha=1.0)],
    "lightgbm": [dict(num_leaves=31), dict(num_leaves=63), dict(num_leaves=15, max_depth=6)],
    "xgboost": [dict(max_depth=6), dict(max_depth=8), dict(max_depth=4)],
    "random_forest": [dict(max_features=1.0, min_samples_leaf=1), dict(max_features=0.5, min_samples_leaf=1)],
    "mlp": [dict(hidden_layer_sizes=(64, 64, 64), alpha=1e-6)],
}
FAST_GRIDS = {k: v[:1] for k, v in GRIDS.items()}


def fit_sign_classifier(family, Xtr, s):
    # The sign only flips in a narrow band (Vd ≈ Vs, or where gate and channel leakage cancel),
    # where a boosted-tree classifier is far more reliable than the others (MLP classifier: 94-95%
    # sign accuracy on NMOS ON vs 99-100%). So every family uses the same LightGBM sign model, and
    # the comparison between families is about the magnitude regressor.
    m = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.05, random_state=SEED, n_jobs=-1, verbose=-1)
    y = (s > 0).astype(int)
    m.fit(Xtr, y)

    return SignModel(m)


def train_family(family, grid, Xtr, Ytr, Xva, Yva, Itr):
    """Return (CaseModel, chosen hyperparameters per target)."""
    regs, chosen = {}, {}
    if family in MULTI_OUTPUT:  # one multi-output model for the four log-currents
        fit = _mlp_reg if family == "mlp" else _poly_reg
        best = None
        for p in grid:
            m = fit(p, Xtr, Ytr.values, Xva, Yva.values)
            mae = np.mean(np.abs(m.predict(Xva) - Yva.values))
            if best is None or mae < best[0]:
                best = (mae, m, p)
        for k, t in enumerate(TARGETS):
            regs[t], chosen[t] = Column(best[1], k), best[2]
    else:
        fit = {"lightgbm": _lgb_reg, "xgboost": _xgb_reg, "random_forest": _rf_reg}[family]
        for t in TARGETS:
            best = None
            for p in grid:
                m = fit(p, Xtr, Ytr[t], Xva, Yva[t])
                mae = np.mean(np.abs(m.predict(Xva) - Yva[t]))
                if best is None or mae < best[0]:
                    best = (mae, m, p)
            regs[t], chosen[t] = best[1], best[2]
    signs = {}
    for t in TARGETS:
        s = np.sign(Itr[t].values)
        frac_pos = np.mean(s > 0)
        if min(frac_pos, 1 - frac_pos) < SIGN_MIXED_MIN:
            signs[t] = 1.0 if frac_pos >= 0.5 else -1.0
        else:
            signs[t] = fit_sign_classifier(family, Xtr, s)
    return CaseModel(family, list(Xtr.columns), regs, signs), chosen


# ---------------------------------------------------------------- plots
def parity_plot(case, df_test, pred, path):
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    for ax, t in zip(axes, TARGETS):
        keep = np.abs(df_test[t].values) >= I_FLOOR
        x, y = np.abs(df_test[t].values[keep]), np.abs(pred[t].values[keep])
        lo, hi = np.log10(max(min(x.min(), y.min()), 1e-22)), np.log10(max(x.max(), y.max()))
        ax.plot([10 ** lo, 10 ** hi], [10 ** lo, 10 ** hi], color="#898781", lw=1, zorder=1)
        ax.scatter(x, y, s=6, alpha=0.5, color="#2a78d6", linewidths=0, zorder=2)
        ax.set_xscale("log"), ax.set_yscale("log")
        m = metrics(df_test[t].values, pred[t].values)
        ax.set_title(f"|{t.upper()}|   median {m['median_err_pct']:.2f}%   p95 {m['p95_err_pct']:.1f}%", fontsize=10)
        ax.set_xlabel("SPICE (A)")
        ax.grid(color="#e1e0d9", lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("ML prediction (A)")
    fig.suptitle(f"{case}: predicted vs SPICE, test set", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def comparison_plot(table, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    agg = table.groupby(["case", "family"])[["median_err_pct", "p95_err_pct"]].mean().reset_index()
    xs = np.arange(len(CASES))
    wbar = 0.2
    for ax, col, lab in zip(axes, ["median_err_pct", "p95_err_pct"],
                            ["Median relative error (%)", "95th-percentile relative error (%)"]):
        fams = [f for f in COLORS if f in set(agg.family)]
        for j, f in enumerate(fams):
            v = [agg[(agg.case == c) & (agg.family == f)][col].mean() for c in CASES]
            ax.bar(xs + (j - (len(fams) - 1) / 2) * wbar, v, wbar * 0.9, color=COLORS[f], label=f)
        ax.set_xticks(xs, CASES)
        ax.set_yscale("log")
        ax.set_ylabel(lab + ", mean of 4 terminals")
        ax.grid(axis="y", color="#e1e0d9", lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.5, 0.93))
    fig.suptitle("Validation-set comparison of model families", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- main
def split_idx(n):
    idx = np.arange(n)
    tr, rest = train_test_split(idx, train_size=SPLIT[0], random_state=SEED)
    va, te = train_test_split(rest, train_size=SPLIT[1] / (SPLIT[1] + SPLIT[2]), random_state=SEED)
    return tr, va, te


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(config.DATA_DIR))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--cases", nargs="*", default=CASES)
    ap.add_argument("--families", nargs="*", default=FAMILIES)
    ap.add_argument("--fast", action="store_true", help="one config per family (smoke test)")
    a = ap.parse_args()

    out = Path(a.out)
    for sub in ("models", "plots", "splits"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    grids = FAST_GRIDS if a.fast else GRIDS
    rows, test_rows, hparams = [], [], {}

    for case in a.cases:
        parts, idx = [], {"train": [], "val": [], "test_uniform": [], "test_targeted": []}
        offset = 0
        for set_name, d in load_datasets(case, a.data_dir).items():
            d.columns = [c.strip().lower() for c in d.columns]
            missing = set(INPUTS + TARGETS) - set(d.columns)
            if missing:
                raise SystemExit(f"{case}.csv ({set_name}): missing columns {sorted(missing)}")
            d = d.dropna(subset=INPUTS + TARGETS).reset_index(drop=True)
            s_tr, s_va, s_te = split_idx(len(d))
            for name, ix in zip(("train", "val", "test"), (s_tr, s_va, s_te)):
                pd.Series(ix, name="row").to_csv(out / "splits" / f"{case}_{set_name}_{name}_idx.csv", index=False)
            idx["train"].append(s_tr + offset)
            idx["val"].append(s_va + offset)
            idx[f"test_{set_name}"].append(s_te + offset)
            parts.append(d.assign(dataset=set_name))
            offset += len(d)
        df = pd.concat(parts, ignore_index=True)
        tr, va = np.concatenate(idx["train"]), np.concatenate(idx["val"])
        tests = {k[5:]: np.concatenate(v) for k, v in idx.items() if k.startswith("test_") and v}
        te = np.concatenate(list(tests.values()))

        X = make_features(df)
        X = X.loc[:, X.iloc[tr].nunique() > 1]  # drop columns constant in this case (e.g. vb)
        Y = df[TARGETS].apply(to_log)
        Xtr, Xva = X.iloc[tr], X.iloc[va]
        Ytr, Yva = Y.iloc[tr], Y.iloc[va]
        print(f"\n== {case}: {len(df)} rows, {X.shape[1]} features, split {len(tr)}/{len(va)}/{len(te)}")

        models = {}
        for fam in a.families:
            t0 = time.time()
            cm, chosen = train_family(fam, grids[fam], Xtr, Ytr, Xva, Yva, df[TARGETS].iloc[tr])
            pred = cm.predict(df.iloc[va])
            for t in TARGETS:
                rows.append({"case": case, "family": fam, "terminal": t,
                             **metrics(df[t].iloc[va].values, pred[t].values)})
            models[fam] = cm
            hparams[f"{case}/{fam}"] = chosen
            v = pd.DataFrame([r for r in rows if r["case"] == case and r["family"] == fam])
            print(f"  {fam:14s} val median {v.median_err_pct.mean():7.3f}%  p95 {v.p95_err_pct.mean():8.2f}%"
                  f"  R2log {v.r2_log.mean():.5f}  ({time.time() - t0:.0f}s)", flush=True)

        # Selection: lowest validation score = mean over terminals of (median + p95)/2.
        v = pd.DataFrame([r for r in rows if r["case"] == case])
        score = v.assign(s=(v.median_err_pct + v.p95_err_pct) / 2).groupby("family").s.mean()
        best = score.idxmin()
        print(f"  -> chosen: {best}", flush=True)
        cm = models[best]
        joblib.dump(cm, out / "models" / f"{case}.joblib")
        for set_name, ix in tests.items():
            pred_te = cm.predict(df.iloc[ix])
            for t in TARGETS:
                test_rows.append({"case": case, "test_set": set_name, "family": best, "terminal": t,
                                  **metrics(df[t].iloc[ix].values, pred_te[t].values)})
            suffix = "" if set_name == "uniform" else f"_{set_name}"
            parity_plot(f"{case} ({set_name})", df.iloc[ix], pred_te, out / "plots" / f"parity_{case}{suffix}.png")
            r = pd.DataFrame(test_rows[-4:])
            print(f"  test {set_name:9s} median {r.median_err_pct.mean():.3f}%  p95 {r.p95_err_pct.mean():.2f}%", flush=True)

    table = pd.DataFrame(rows)
    test = pd.DataFrame(test_rows)
    table.to_csv(out / "comparison_table.csv", index=False)
    test.to_csv(out / "test_metrics.csv", index=False)
    cols = ["r2_log", "median_err_pct", "p95_err_pct"]
    wide = table.pivot_table(index=["case", "terminal"], columns="family", values=cols)
    (out / "comparison_table.md").write_text(_md(wide, cols, a.families))
    (out / "test_metrics.md").write_text(test[["case", "test_set", "family", "terminal"] + cols + ["mean_err_pct", "sign_acc"]]
                                         .to_markdown(index=False, floatfmt=".4g"))
    (out / "hyperparameters.json").write_text(json.dumps(hparams, indent=1, default=str))
    if len(a.families) > 1:
        comparison_plot(table, out / "plots" / "family_comparison.png")
    print(f"\nWrote results to {out}")


def _md(wide, cols, families):
    lines = []
    for col, title in zip(cols, ["R² on log10|I|", "Median relative error (%)", "95th-percentile relative error (%)"]):
        sub = wide[col][families]
        lines += [f"### {title} (validation set)", "", sub.to_markdown(floatfmt=".4g"), ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()

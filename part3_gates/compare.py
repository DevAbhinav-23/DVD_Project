"""Part 3: predict gate leakage with the Part 2 transistor models and compare against SPICE.

For every simulation in results/part3/spice_gates.csv, each transistor's (Vd, Vg, Vs, Vb) is
built from the SPICE-recorded node voltages, the ON or OFF model is picked from its gate voltage,
and the predicted terminal currents are summed with the same leakage formula as the oracle check.

Vg handling: the transistor models were trained with Vg exactly at 0 or VDD. Inputs are exactly
at a rail, but in AND2 / OR2 the inverter is driven by the internal NAND / NOR output, a few mV
off the rail. The main result ("rail") snaps Vg to the rail the model was trained at; "actual"
feeds the recorded Vg instead and is reported for the error analysis.

Usage:  python part3_gates/compare.py      # needs part3_gates/simulate.py first
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "part2_models"))
import config
from gates import CASES, GATES, TERMINALS, leakage, leakage_vdd_terminals, node_voltages, nodes
from leakage_model import INPUTS, TARGETS, load_case_model

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT_DIR = config.RESULTS_DIR / "part3"
MODEL_DIR = config.RESULTS_DIR / "part2" / "models"
GATE_COLORS = {"inv": "#2a78d6", "nand2": "#eb6834", "nor2": "#1baf7a", "and2": "#eda100",
               "or2": "#e87ba4"}


def transistor_inputs(spice, vg_mode):
    """One row per transistor per simulation: model case plus the 12 model inputs."""
    parts = []
    for (gate, bits), g in spice.groupby(["gate", "inputs"], sort=False):
        volts = node_voltages(gate, bits, g["vdd"], {n: g[f"v_{n}"] for n in nodes(gate)})
        for name, mos_type, *terms in GATES[gate]:
            v = {t: volts[node] for t, node in zip(TERMINALS, terms)}
            gate_high = v["g"] > g["vdd"] / 2
            on = gate_high if mos_type == "nmos" else ~gate_high
            vg = np.where(gate_high, g["vdd"], 0.0) if vg_mode == "rail" else v["g"]
            part = pd.DataFrame({
                "sim": g.index, "fet": name,
                "case": np.where(on, f"{mos_type}_on", f"{mos_type}_off"),
                "vdd": g["vdd"], "temp": g["temp"], "w": config.GATE_W[mos_type],
                "vd": v["d"], "vs": v["s"], "vg": vg, "vb": v["b"],
                **{p: g[f"{mos_type}_{p}"] for p in config.PROCESS_PARAMS},
            }, index=g.index)
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def predict_leakage(spice, models, vg_mode, include_inputs=False, formula=leakage):
    """ML gate leakage for every simulation (same formula as the SPICE oracle check)."""
    fets = transistor_inputs(spice, vg_mode)
    fets[TARGETS] = np.nan
    for case, idx in fets.groupby("case").groups.items():
        fets.loc[idx, TARGETS] = models[case].predict(fets.loc[idx, INPUTS]).to_numpy()
    wide = fets.pivot(index="sim", columns="fet", values=TARGETS)
    wide.columns = [f"{fet}_{c}" for c, fet in wide.columns]

    out = pd.Series(np.nan, index=spice.index)
    for (gate, bits), g in spice.groupby(["gate", "inputs"]):
        out[g.index] = formula(gate, bits, wide.loc[g.index], include_inputs)
    return out


def error_stats(ml, spice):
    rel = (ml - spice) / spice
    err = rel.abs()
    return {
        "spice_median": spice.median(), "ml_median": ml.median(),
        "bias_pct": 100 * rel.median(),
        "median_err_pct": 100 * err.median(), "p95_err_pct": 100 * err.quantile(0.95),
        "mean_err_pct": 100 * err.mean(),
    }


def results_table(pred, ml_col, spice_col):
    rows = [{"gate": gate, "inputs": bits,
             **error_stats(*(pred.loc[(pred.gate == gate) & (pred.inputs == bits), c]
                             for c in (ml_col, spice_col)))}
            for gate, bits in CASES]
    rows.append({"gate": "all", "inputs": "", **error_stats(pred[ml_col], pred[spice_col])})
    return pd.DataFrame(rows)


def parity_plot(pred, path):
    fig, ax = plt.subplots(figsize=(6.4, 6))
    x, y = pred["spice_leak"].abs(), pred["ml_leak"].abs()
    lo, hi = min(x.min(), y.min()) / 1.5, max(x.max(), y.max()) * 1.5
    ax.plot([lo, hi], [lo, hi], color="#898781", lw=1, zorder=1)
    for gate, color in GATE_COLORS.items():
        sel = pred.gate == gate
        ax.scatter(x[sel], y[sel], s=7, alpha=0.6, color=color, linewidths=0, zorder=2,
                   label=gate.upper())
    ax.set_xscale("log"), ax.set_yscale("log")
    ax.set_xlim(lo, hi), ax.set_ylim(lo, hi)
    s = error_stats(pred["ml_leak"], pred["spice_leak"])
    ax.set_title(f"Gate leakage, {len(pred)} simulations   median {s['median_err_pct']:.2f}%"
                 f"   p95 {s['p95_err_pct']:.1f}%", fontsize=10)
    ax.set_xlabel("|SPICE leakage| (A)")
    ax.set_ylabel("|ML leakage| (A)")
    ax.grid(color="#e1e0d9", lw=0.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, markerscale=2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    spice = pd.read_csv(OUT_DIR / "spice_gates.csv", dtype={"inputs": str})
    models = {case: load_case_model(MODEL_DIR / f"{case}.joblib") for case in config.CASES}

    pred = spice[["gate", "inputs", "corner", "vdd", "temp"]].copy()
    pred["spice_leak"] = spice["i_supply"]
    pred["ml_leak"] = predict_leakage(spice, models, "rail")
    pred["ml_leak_actual_vg"] = predict_leakage(spice, models, "actual")
    pred["spice_leak_with_inputs"] = spice["i_supply"] + spice["i_in_vdd"]
    pred["ml_leak_with_inputs"] = predict_leakage(spice, models, "rail", include_inputs=True)
    pred["ml_leak_vdd_terminals"] = predict_leakage(spice, models, "rail",
                                                    formula=leakage_vdd_terminals)
    pred["rel_err"] = (pred["ml_leak"] - pred["spice_leak"]) / pred["spice_leak"]
    pred.to_csv(OUT_DIR / "gate_predictions.csv", index=False)

    table = results_table(pred, "ml_leak", "spice_leak")
    table.to_csv(OUT_DIR / "gate_table.csv", index=False)
    variants = {"main (Vg at rail)": ("ml_leak", "spice_leak"),
                "recorded Vg": ("ml_leak_actual_vg", "spice_leak"),
                "supply + inputs at VDD": ("ml_leak_with_inputs", "spice_leak_with_inputs"),
                "previous formula (VDD terminals)": ("ml_leak_vdd_terminals", "spice_leak")}
    var_table = table[["gate", "inputs"]].copy()
    for label, (ml_col, spice_col) in variants.items():
        t = results_table(pred, ml_col, spice_col)
        var_table[f"{label}: median / p95 err %"] = [
            f"{m:.2f} / {p:.1f}" for m, p in zip(t.median_err_pct, t.p95_err_pct)]

    md = ["## Gate leakage: ML vs SPICE (leakage = current drawn from VDD, 200 corners per row)", "",
          table.to_markdown(index=False, floatfmt=".4g"), "",
          "## Variants (Vg handling, leakage definition, previous formula)", "",
          var_table.to_markdown(index=False), ""]
    (OUT_DIR / "gate_table.md").write_text("\n".join(md))

    (OUT_DIR / "plots").mkdir(exist_ok=True)
    parity_plot(pred, OUT_DIR / "plots" / "gate_parity.png")
    print("\n".join(md))


if __name__ == "__main__":
    main()

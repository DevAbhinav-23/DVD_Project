"""Hierarchical NAND2 lookup estimates versus full-circuit SPICE.

Circuit SPICE voltages never enter ML predictions. Part 3 recorded voltages
are used only to evaluate the saved transistor models for the NAND2 lookup.
"""
import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogFormatterSciNotation, LogLocator, NullFormatter
import numpy as np
import pandas as pd

from circuit import GRAPH, PRIMARY, ROOT, config, logic
sys.path.insert(0, str(ROOT / "part2_models"))
# This file shares its name with Part 3 compare.py, so import that module by path.
import importlib.util
spec = importlib.util.spec_from_file_location("gate_compare", ROOT / "part3_gates/compare.py")
gate_compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_compare)
from gates import leakage
from corners import load_corners
from leakage_model import INPUTS, TARGETS, load_case_model


def validate_shared_corners(frame):
    columns = ["vdd", "temp", *(f"{kind}_{p}" for kind in ("nmos", "pmos")
                                for p in config.PROCESS_PARAMS)]
    corners = load_corners().set_index("corner")
    if not set(frame.corner) <= set(corners.index):
        raise RuntimeError("reference contains unknown PVT corner IDs")
    expected = corners.loc[frame.corner, columns].to_numpy()
    if not np.allclose(frame[columns].to_numpy(), expected, rtol=1e-12, atol=0):
        raise RuntimeError("reference PVT values do not match the shared corner table")


def make_lookup():
    spice = pd.read_csv(ROOT / "results/part3/spice_gates.csv", dtype={"inputs": str})
    spice = spice[spice.gate == "nand2"].reset_index(drop=True)
    validate_shared_corners(spice)
    fets = gate_compare.transistor_inputs(spice, "actual")
    fets[TARGETS] = np.nan
    for case, idx in fets.groupby("case").groups.items():
        model = load_case_model(ROOT / "results/part2/models" / f"{case}.joblib")
        fets.loc[idx, TARGETS] = model.predict(fets.loc[idx, INPUTS]).to_numpy()
    wide = fets.pivot(index="sim", columns="fet", values=TARGETS)
    wide.columns = [f"{fet}_{current}" for current, fet in wide.columns]
    lookup = spice[["corner", "inputs"]].copy()
    lookup["spice_leak"] = spice.i_supply
    lookup["ml_leak"] = np.nan
    for bits, group in spice.groupby("inputs"):
        lookup.loc[group.index, "ml_leak"] = leakage("nand2", bits, wide.loc[group.index])
    for pin, fets_on_pin in [("a", ["mp1", "mn1"]), ("b", ["mp2", "mn2"])]:
        lookup[f"ml_ig_{pin}"] = sum(wide[f"{fet}_ig"] for fet in fets_on_pin)
        lookup[f"spice_ig_{pin}"] = spice[f"i_in_{pin}"]
    # Guard against a changed interpretation or incompatible saved-model environment.
    saved = pd.read_csv(ROOT / "results/part3/gate_predictions.csv", dtype={"inputs": str})
    saved = saved[saved.gate == "nand2"].set_index(["corner", "inputs"])
    lookup = lookup.set_index(["corner", "inputs"]).sort_index()
    if len(lookup) != 4 * config.N_CORNERS or not lookup.index.is_unique:
        raise RuntimeError("incomplete NAND2 gate lookup")
    if not np.allclose(lookup.ml_leak, saved.loc[lookup.index].ml_leak, rtol=1e-9, atol=1e-18):
        raise RuntimeError("NAND2 predictions no longer reproduce Part 3")
    return lookup


def vector_counts(vector):
    """Count each input pattern and each high input pin by driver ownership."""
    values = logic(vector)
    counts = {bits: {"gates": 0, "internal_a": 0, "internal_b": 0,
                     "primary_a": 0, "primary_b": 0} for bits in ("00", "01", "10", "11")}
    for _, a, b in GRAPH:
        bits = f"{values[a]}{values[b]}"
        counts[bits]["gates"] += 1
        for pin, node in [("a", a), ("b", b)]:
            if values[node]:
                owner = "primary" if node in PRIMARY else "internal"
                counts[bits][f"{owner}_{pin}"] += 1
    return counts


def estimates(corner_lookup, counts):
    result = {}
    for source in ("ml", "spice"):
        plain = sum(c["gates"] * corner_lookup.loc[bits, f"{source}_leak"]
                    for bits, c in counts.items())
        internal = sum(c[f"internal_{pin}"] * corner_lookup.loc[bits, f"{source}_ig_{pin}"]
                       for bits, c in counts.items() for pin in ("a", "b"))
        primary = sum(c[f"primary_{pin}"] * corner_lookup.loc[bits, f"{source}_ig_{pin}"]
                      for bits, c in counts.items() for pin in ("a", "b"))
        result[f"{source}_plain"] = plain
        result[f"{source}_corrected"] = plain + internal
        result[f"{source}_with_inputs"] = plain + internal + primary
    return result


def batch_estimates(corner_lookup, counts_by_vector):
    """Evaluate one corner's vectors together instead of millions of scalar lookups."""
    patterns = ["00", "01", "10", "11"]
    fields = ["gates", "internal_a", "internal_b", "primary_a", "primary_b"]
    counts = np.array([[[entry[bits][field] for field in fields] for bits in patterns]
                       for entry in counts_by_vector.values()])
    result = {"vector": list(counts_by_vector)}
    for source in ("ml", "spice"):
        lookup = corner_lookup.loc[patterns]
        a, b = (lookup[f"{source}_ig_{pin}"].to_numpy() for pin in ("a", "b"))
        plain = counts[:, :, 0] @ lookup[f"{source}_leak"].to_numpy()
        internal = counts[:, :, 1] @ a + counts[:, :, 2] @ b
        primary = counts[:, :, 3] @ a + counts[:, :, 4] @ b
        result[f"{source}_plain"] = plain
        result[f"{source}_corrected"] = plain + internal
        result[f"{source}_with_inputs"] = plain + internal + primary
    return pd.DataFrame(result)


def stats(prediction, reference):
    signed = (prediction - reference) / reference
    err = signed.abs()
    return {"spice_median_A": reference.median(), "prediction_median_A": prediction.median(),
            "bias_pct": 100 * signed.median(), "median_err_pct": 100 * err.median(),
            "p95_err_pct": 100 * err.quantile(.95), "mean_err_pct": 100 * err.mean(),
            "max_err_pct": 100 * err.max()}


def markdown_table(frame):
    """Preserve leading zeros in input vectors when tabulate detects numbers."""
    frame = frame.copy()
    if "vector" in frame:
        frame["vector"] = "`" + frame["vector"].astype(str) + "`"
    return frame.to_markdown(index=False, floatfmt=".5g")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/part4")
    args = parser.parse_args()
    out = args.output.resolve()
    spice = pd.read_csv(out / "spice_circuit.csv.gz", dtype={"vector": str})
    validate_shared_corners(spice)
    if spice.duplicated(["corner", "vector"]).any() or (spice.i_supply <= 0).any():
        raise RuntimeError("invalid full-circuit reference")
    lookup = make_lookup()
    lookup.to_csv(out / "nand2_lookup.csv")
    counts = {v: vector_counts(v) for v in spice.vector.unique()}
    predictions = []
    for cid, group in spice.groupby("corner", sort=True):
        batch = batch_estimates(lookup.loc[cid], {v: counts[v] for v in group.vector})
        batch.insert(0, "corner", cid)
        predictions.append(batch)
    prediction = pd.concat(predictions, ignore_index=True)
    df = spice.merge(prediction, on=["corner", "vector"], validate="one_to_one")
    prediction_columns = list(prediction.columns[2:])
    if not np.isfinite(df[prediction_columns].to_numpy()).all() or (df[prediction_columns] <= 0).any().any():
        raise RuntimeError("non-finite or non-positive circuit leakage estimate")
    df["spice_with_inputs_reference"] = df.i_supply + df.i_in_vdd
    variants = [("ML plain sum (spec baseline)", "ml_plain", "i_supply"),
                ("ML corrected (internal high inputs)", "ml_corrected", "i_supply"),
                ("ML corrected + primary high inputs", "ml_with_inputs", "spice_with_inputs_reference"),
                ("SPICE gate lookup plain (diagnostic)", "spice_plain", "i_supply"),
                ("SPICE gate lookup corrected (diagnostic)", "spice_corrected", "i_supply")]
    rows = [{"variant": name, **stats(df[estimate], df[reference])}
            for name, estimate, reference in variants]
    table = pd.DataFrame(rows)
    table.to_csv(out / "circuit_table.csv", index=False)
    df["rel_err_plain"] = (df.ml_plain - df.i_supply).abs() / df.i_supply.abs()
    df["rel_err_corrected"] = (df.ml_corrected - df.i_supply).abs() / df.i_supply.abs()
    example = df.iloc[0]
    levels = logic(example.vector)
    gate_rows = []
    for output, a, b in GRAPH:
        bits = f"{levels[a]}{levels[b]}"
        entry = lookup.loc[(example.corner, bits)]
        extra_a = entry.ml_ig_a if levels[a] and a not in PRIMARY else 0.
        extra_b = entry.ml_ig_b if levels[b] and b not in PRIMARY else 0.
        gate_rows.append({"gate_output": output, "input_a": a, "input_b": b, "bits_ab": bits,
                          "ml_gate_supply_A": entry.ml_leak, "internal_high_a_correction_A": extra_a,
                          "internal_high_b_correction_A": extra_b,
                          "corrected_contribution_A": entry.ml_leak + extra_a + extra_b})
    gate_breakdown = pd.DataFrame(gate_rows)
    if not np.isclose(gate_breakdown.corrected_contribution_A.sum(), example.ml_corrected, rtol=1e-12, atol=1e-18):
        raise RuntimeError("worked gate breakdown does not reproduce the aggregate estimate")
    gate_breakdown.to_csv(out / "example_gate_breakdown.csv", index=False)
    pattern_counts = vector_counts(example.vector)
    explanation = ["# Worked circuit calculation", "",
                   f"Vector `{example.vector}` (d0 through d7, then parity), corner {int(example.corner)}: "
                   f"VDD={example.vdd:.6f} V, temperature={example.temp:.3f} C. "
                   f"Expected error output={int(example.expected_error)}.", "",
                   "Each NAND's input bits come from Boolean evaluation of the shared circuit graph. "
                   "Its base leakage comes from the matching Part 3 lookup entry at this corner. "
                   "For each high input driven by another gate, add that pin's predicted gate current. "
                   "Primary inputs are powered by separate sources and stay outside the main supply sum.", "",
                   "Number of NANDs in each ordered input state: " + ", ".join(
                       f"`{bits}`: {c['gates']}" for bits, c in pattern_counts.items()) + ".", "",
                   f"1. Sum 32 isolated gate leakages: **{example.ml_plain:.8e} A**.",
                   f"2. Add internal high-input gate currents: **{example.ml_corrected-example.ml_plain:.8e} A**.",
                   f"3. Corrected circuit estimate: **{example.ml_corrected:.8e} A**.",
                   f"4. Complete-circuit SPICE reference: **{example.i_supply:.8e} A**.",
                   f"5. Relative error = |estimate - reference| / |reference| = **{100*example.rel_err_corrected:.4f}%**.", "",
                   "`example_gate_breakdown.csv` gives all 32 contributions and their input connections. "
                   "All currents are amperes; 1e-6 A equals one microampere.", ""]
    (out / "example_calculation.md").write_text("\n".join(explanation))
    columns = ["corner", "vector", "vdd", "temp", "expected_error", "i_supply", "i_in_vdd",
               "v_error", *prediction.columns[2:], "spice_with_inputs_reference",
               "rel_err_plain", "rel_err_corrected"]
    df[columns].to_csv(out / "circuit_predictions.csv.gz", index=False, compression="gzip")
    for key in ("corner", "vector"):
        summaries = []
        for value, group in df.groupby(key):
            conditions_for_corner = ({p: group[p].iloc[0] for p in
                                     ["vdd", "temp", "nmos_vth0", "pmos_vth0"]} if key == "corner" else {})
            summaries.append({key: value, "runs": len(group), **conditions_for_corner,
                              **stats(group.ml_corrected, group.i_supply)})
        pd.DataFrame(summaries).to_csv(out / f"errors_by_{key}.csv", index=False)
    conditions = []
    for parameter in ("temp", "vdd", "nmos_vth0", "pmos_vth0"):
        values = df[parameter].abs() if parameter == "pmos_vth0" else df[parameter]
        quartiles = pd.qcut(values, 4, labels=False, duplicates="drop")
        for quartile, group in df.groupby(quartiles):
            conditions.append({"parameter": "abs_pmos_vth0" if parameter == "pmos_vth0" else parameter,
                               "quartile_low_to_high": int(quartile) + 1,
                               "min": float(values.loc[group.index].min()),
                               "max": float(values.loc[group.index].max()), "runs": len(group),
                               **stats(group.ml_corrected, group.i_supply)})
    condition_table = pd.DataFrame(conditions)
    condition_table.to_csv(out / "errors_by_pvt_quartile.csv", index=False)
    worst = df.nlargest(20, "rel_err_corrected")
    worst_columns = ["corner", "vector", "vdd", "temp", "nmos_vth0", "pmos_vth0",
                     "i_supply", "ml_corrected", "rel_err_corrected"]
    worst[worst_columns].to_csv(out / "worst_cases.csv", index=False)
    plots = out / "plots"
    plots.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    for ax, column, label in zip(axes, ["ml_plain", "ml_corrected"], ["Plain gate sum", "Input-current corrected"]):
        lo = min(df.i_supply.min(), df[column].min()) / 1.2
        hi = max(df.i_supply.max(), df[column].max()) * 1.2
        ax.hexbin(df.i_supply, df[column], gridsize=65, xscale="log", yscale="log", mincnt=1,
                  bins="log", cmap="viridis")
        ax.plot([lo, hi], [lo, hi], color="tomato", lw=1)
        ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="Full-circuit SPICE leakage (A)",
               ylabel="Hierarchical ML leakage (A)", title=label)
        errors = stats(df[column], df.i_supply)
        ax.set_title(f"{label}\nMean error {errors['mean_err_pct']:.2f}%, p95 {errors['p95_err_pct']:.2f}%", fontsize=11)
        ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1., 2., 5.)))
        ax.xaxis.set_major_formatter(LogFormatterSciNotation(base=10, minor_thresholds=(np.inf, np.inf)))
        ax.xaxis.set_minor_formatter(NullFormatter())
    fig.suptitle(f"Nine-input parity checker: {len(df):,} operating points")
    fig.savefig(plots / "circuit_parity.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    ax.scatter(df.temp, df.rel_err_corrected * 100, s=2, alpha=.1, rasterized=True)
    ax.set(xlabel="Temperature (C)", ylabel="Corrected relative error (%)",
           title="Circuit error versus temperature")
    fig.savefig(plots / "error_vs_temperature.png", dpi=150)
    plt.close(fig)
    baseline = pd.read_csv(ROOT / "results/part3/gate_predictions.csv", dtype={"inputs": str})
    baseline = baseline[baseline.gate == "nand2"]
    gate_stats = stats(baseline.ml_leak, baseline.spice_leak)
    text = ["# Nine-input parity circuit: ML versus full-circuit SPICE", "",
            f"{len(df):,} cases; {df.corner.nunique()} corners; {df.vector.nunique()} vectors.", "",
            "Vector order: d0 d1 d2 d3 d4 d5 d6 d7 parity. Even parity: error=0 is valid.",
            "32 NAND2 gates, 128 minimum-sized transistors, identical pin order to Part 3.", "",
            table.to_markdown(index=False, floatfmt=".5g"), "",
            "The prescribed plain gate sum is the baseline. The corrected estimate adds signed gate",
            "currents for high inputs driven by internal gates. Primary-input source currents remain",
            "excluded from the main supply-only comparison; their inclusion is reported separately.", "",
            "SPICE gate lookups are evaluation-only diagnostics: their residual against circuit SPICE",
            "shows the isolated-gate/rail-input approximation, without transistor-model prediction error.",
            "No full-circuit SPICE voltages or currents are used to calculate the ML estimates.", "",
            f"Part 3 NAND2 baseline: median {gate_stats['median_err_pct']:.3f}%, "
            f"p95 {gate_stats['p95_err_pct']:.3f}%, mean {gate_stats['mean_err_pct']:.3f}% error.", "",
            "## Worst corrected cases", "", markdown_table(worst[worst_columns]), ""]
    (out / "circuit_table.md").write_text("\n".join(text))
    main_stats = stats(df.ml_corrected, df.i_supply)
    diagnostic_stats = stats(df.spice_corrected, df.i_supply)
    decomposition = {
        "ml_vs_isolated_spice_mean_signed_pct": float(100 * ((df.ml_corrected - df.spice_corrected) / df.i_supply).mean()),
        "isolated_spice_vs_full_circuit_mean_signed_pct": float(100 * ((df.spice_corrected - df.i_supply) / df.i_supply).mean()),
        "total_mean_signed_pct": float(100 * ((df.ml_corrected - df.i_supply) / df.i_supply).mean())}
    (out / "error_decomposition.json").write_text(json.dumps(decomposition, indent=2) + "\n")
    best_target = "met" if main_stats["mean_err_pct"] <= 1 else "not met"
    corner_errors = pd.read_csv(out / "errors_by_corner.csv").nlargest(5, "mean_err_pct")
    vector_errors = pd.read_csv(out / "errors_by_vector.csv", dtype={"vector": str}).nlargest(5, "mean_err_pct")
    summary = json.loads((out / "simulation_summary.json").read_text())
    simulator_label = next((line.strip("* ") for line in summary["simulator"].splitlines()
                            if "ngspice-" in line), "see simulation_summary.json")
    report = ["# Part 4: Nine-input parity circuit validation", "",
              "## Setup and circuit", "",
              "PTM 22nm MGK, nominal VDD 0.9 V, W=L=22 nm for NMOS and PMOS. "
              f"Simulator: {simulator_label}; Python {summary['python'].split()[0]}. "
              "Package versions accompany the results. "
              "The nine inputs are eight data bits plus one even-parity bit. "
              "A balanced seven-XOR data tree and a final parity XOR use 32 ordered NAND2 gates "
              "(128 transistors). Output 0 is valid even parity; output 1 signals an error.", "",
              "## Terms and evaluation", "",
              "PVT means process (transistor fabrication parameters), voltage (VDD), and temperature. "
              "A corner is one sampled PVT setting. A vector is one nine-bit input pattern. "
              "A simulation case is one vector at one corner. Static leakage is the current "
              "drawn from VDD after the transistor circuit settles, not switching current.", "",
              f"This run contains **{len(df):,} cases**, {df.corner.nunique()} shared corners and "
              f"{df.vector.nunique()} vectors. Full coverage is 512 x 200 = 102,400 cases. "
              "The reference is the complete transistor circuit, not a sum of isolated SPICE gates. "
              "The circuit ML calculation uses Boolean logic and 800 isolated NAND2 lookup entries "
              "derived from the saved transistor models. Circuit-SPICE node voltages are evaluation-only.", "",
              "The plain sum follows the specified hierarchical approximation. The corrected sum "
              "also includes signed gate currents into high inputs driven by internal gates. "
              "Primary input sources are excluded from the main supply-only result, and included "
              "in a separately matched variant. No model retraining was needed.", "",
              "## Results", "", table.to_markdown(index=False, floatfmt=".5g"), "",
              f"Corrected mean error is **{main_stats['mean_err_pct']:.3f}%**, corresponding to "
              f"{100-main_stats['mean_err_pct']:.3f}% mean accuracy under the project's "
              f"100-minus-mean-relative-error convention. The approximate 1% mean-error objective is **{best_target}**. "
              "The submission reports the prescribed rail-input plain sum alongside this correction. "
              "Both use the Part 3 NAND2 lookup derived from the four saved transistor models.", "",
              f"The isolated NAND2 baseline has {gate_stats['mean_err_pct']:.3f}% mean error and "
              f"{gate_stats['p95_err_pct']:.3f}% p95 error. Summation can average some transistor-model "
              "errors, while inter-gate analog loading introduces additional error. "
              f"Even the corrected SPICE-gate diagnostic has {diagnostic_stats['mean_err_pct']:.3f}% "
              "mean error against full-circuit SPICE; the rail-input approximation itself is imperfect.", "",
              "Using the full-circuit current as the common denominator, the mean signed error "
              f"decomposes exactly into {decomposition['ml_vs_isolated_spice_mean_signed_pct']:.3f} "
              "percentage points from replacing isolated SPICE-gate currents with ML currents, and "
              f"{decomposition['isolated_spice_vs_full_circuit_mean_signed_pct']:.3f} percentage points "
              "from composing isolated gates with the input-current correction. These signed "
              "components can cancel; they are not an additive decomposition of absolute errors.", "",
              "## Validation", "",
              f"All recorded gate outputs passed Boolean checks. Maximum internal NAND output deviation "
              f"from its ideal logic rail: {100*summary['max_node_deviation_fraction_vdd']:.4f}% of VDD. "
              "Input sources are checked against 0/VDD using the required 1 nV voltage tolerance. "
              "The independent operating-point/DC cross-check is stored separately when run. "
              "Tests cover all 512 parity patterns, pin-current ownership, batched aggregation, "
              "missing measurements and deliberately corrupted node/input voltages.", "",
              "## Error analysis", "", "Worst corners by corrected mean error:", "",
              markdown_table(corner_errors[["corner", "vdd", "temp", "nmos_vth0", "pmos_vth0",
                                             "mean_err_pct", "p95_err_pct", "max_err_pct"]]), "",
              "Worst vectors by corrected mean error over corners:", "",
              markdown_table(vector_errors[["vector", "mean_err_pct", "p95_err_pct", "bias_pct"]]), "",
              "Temperature quartiles (descriptive associations, not causal effects):", "",
              markdown_table(condition_table.loc[condition_table.parameter == "temp",
                                                  ["quartile_low_to_high", "min", "max", "runs",
                                                   "mean_err_pct", "p95_err_pct"]]), "",
              "The full quartile table also covers VDD and NMOS/PMOS threshold magnitudes. "
              f"Each corner is reused over every vector; these are {df.corner.nunique()} PVT draws, not {len(df):,} independent "
              "draws of fabrication and temperature conditions. Worst individual cases and both "
              "per-corner/per-vector summaries accompany this report.", "",
              "## Limitations and possible improvements", "",
              "The gate lookup assumes ideal input rails and isolated-gate node voltages. "
              "The input-current correction changes current accounting but does not solve coupled analog "
              "voltages. The full circuit has fanout and non-ideal high/low levels. Existing transistor "
              "models also retain their own fitting errors. Future work could use gate models conditioned "
              "on analog input voltages and loading, solve coupled voltages, or improve transistor fits "
              "using additional independently generated training samples. Circuit evaluation data must "
              "remain outside model training.", "",
              "## Reproduction", "", "```bash", "python run_all.py --part4-only --workers 6", "```", "",
              "This command reuses Parts 1-3, validates/reuses matching per-corner checkpoints, and "
              "regenerates circuit predictions, tables, plots, versions and this report. "
              "`python run_all.py` also regenerates the upstream datasets, models and gate results; "
              "that much longer full training pipeline was not rerun for this Part 4 addition.", ""]
    (out / "report_part4.md").write_text("\n".join(report))
    versions = {p: importlib.metadata.version(p) for p in
                ["numpy", "pandas", "matplotlib", "scikit-learn", "lightgbm", "joblib", "tabulate"]}
    (out / "python_versions.json").write_text(json.dumps(versions, indent=2) + "\n")
    installed = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    (out / "environment_freeze.txt").write_text("\n".join(installed) + "\n")
    sources = [ROOT / "config.py", ROOT / "requirements.txt", ROOT / "run_all.py",
               config.MODEL_FILE, config.CORNERS_FILE,
               ROOT / "results/part3/spice_gates.csv", ROOT / "results/part3/gate_predictions.csv",
               *sorted((ROOT / "results/part2/models").glob("*.joblib")),
               *sorted((ROOT / "part4_circuit").glob("*.py"))]
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    (out / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(table.to_string(index=False))
    print(f"{len(df):,} predictions saved to {out}")


if __name__ == "__main__":
    main()

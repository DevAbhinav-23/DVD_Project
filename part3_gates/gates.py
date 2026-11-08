"""Static CMOS gates: topology, SPICE netlists, batched ngspice runs and the leakage formula.

Currents follow the project convention: positive = flowing INTO the transistor terminal.
Every transistor terminal is wired to its node through its own 0 V source (an ammeter), so
SPICE reports every terminal current, not only the supply current.
"""
import itertools
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "part1_dataset"))
import config
from corners import corner_params
from spice_utils import CURRENTS, MODEL_NAME, model_card

TERMINALS = ["d", "g", "s", "b"]   # same order as CURRENTS = id, ig, is, ib

# Transistors as (name, type, drain, gate, source, body). "0" is ground, "a"/"b" are the inputs.
# Internal nodes: x between the series NMOS of NAND2, y between the series PMOS of NOR2,
# nand_out / nor_out = the NAND2 / NOR2 output inside AND2 / OR2.
GATES = {
    "inv": [
        ("mp1", "pmos", "out", "a", "vdd", "vdd"),
        ("mn1", "nmos", "out", "a", "0", "0"),
    ],
    "nand2": [
        ("mp1", "pmos", "out", "a", "vdd", "vdd"),
        ("mp2", "pmos", "out", "b", "vdd", "vdd"),
        ("mn1", "nmos", "out", "a", "x", "0"),
        ("mn2", "nmos", "x", "b", "0", "0"),
    ],
    "nor2": [
        ("mp1", "pmos", "y", "a", "vdd", "vdd"),
        ("mp2", "pmos", "out", "b", "y", "vdd"),
        ("mn1", "nmos", "out", "a", "0", "0"),
        ("mn2", "nmos", "out", "b", "0", "0"),
    ],
    "and2": [
        ("mp1", "pmos", "nand_out", "a", "vdd", "vdd"),
        ("mp2", "pmos", "nand_out", "b", "vdd", "vdd"),
        ("mn1", "nmos", "nand_out", "a", "x", "0"),
        ("mn2", "nmos", "x", "b", "0", "0"),
        ("mp3", "pmos", "out", "nand_out", "vdd", "vdd"),
        ("mn3", "nmos", "out", "nand_out", "0", "0"),
    ],
    "or2": [
        ("mp1", "pmos", "y", "a", "vdd", "vdd"),
        ("mp2", "pmos", "nor_out", "b", "y", "vdd"),
        ("mn1", "nmos", "nor_out", "a", "0", "0"),
        ("mn2", "nmos", "nor_out", "b", "0", "0"),
        ("mp3", "pmos", "out", "nor_out", "vdd", "vdd"),
        ("mn3", "nmos", "out", "nor_out", "0", "0"),
    ],
}


def inputs(gate):
    return [n for n in ("a", "b") if any(n in fet[2:] for fet in GATES[gate])]


def nodes(gate):
    """Nodes whose voltage SPICE solves for: the output and the internal nodes."""
    all_nodes = {n for fet in GATES[gate] for n in fet[2:]}
    return sorted(all_nodes - {"0", "vdd", *inputs(gate)})


# The 18 gate-input cases, e.g. ("nand2", "01") means A = 0, B = 1.
CASES = [(gate, "".join(bits)) for gate in GATES
         for bits in itertools.product("01", repeat=len(inputs(gate)))]


def node_voltages(gate, bits, vdd, solved):
    """{node: voltage} for every node of the gate. Inputs are exactly 0 or VDD;
    solved maps each node in nodes(gate) to its (SPICE-recorded) voltage."""
    volts = {"0": 0.0, "vdd": vdd}
    volts.update({n: vdd * int(bit) for n, bit in zip(inputs(gate), bits)})
    volts.update({n: solved[n] for n in nodes(gate)})
    return volts


def on_devices(gate, bits):
    """Names of the transistors that are ON for these inputs (from the logic levels)."""
    a, b = (int(c) for c in bits.ljust(2, "0"))
    level = {"0": 0, "vdd": 1, "a": a, "b": b, "nand_out": 1 - (a & b), "nor_out": 1 - (a | b)}
    return {name for name, mos_type, _, g, _, _ in GATES[gate]
            if level[g] == (1 if mos_type == "nmos" else 0)}


def _supply_rails(gate, bits, include_inputs):
    rails = {"vdd"}
    if include_inputs:
        rails |= {n for n, bit in zip(inputs(gate), bits) if bit == "1"}
    return rails


def leakage_vdd_terminals(gate, bits, currents, include_inputs=False):
    """Previous formula, kept for comparison: the sum of the currents INTO every transistor
    terminal tied to VDD. Exact for SPICE currents, but when the output is high it relies on the
    drain/source currents of ON transistors at |Vds| ~ 0, which the transistor models predict
    poorly (wrong sign in the gate operating region)."""
    rails = _supply_rails(gate, bits, include_inputs)
    return sum(currents[f"{name}_{c}"]
               for name, _, *terms in GATES[gate]
               for node, c in zip(terms, CURRENTS) if node in rails)


def leakage(gate, bits, currents, include_inputs=False):
    """Static current drawn from VDD, without using any ON transistor's drain or source current.

    Each ON transistor's channel enters as one unknown t (its drain current); its source current
    follows from its own KCL, is = -(ig + ib) - t. OFF transistors use all four currents and ON
    transistors their gate and body currents. KCL at every internal node fixes the unknowns, so
    each ON transistor carries exactly what the OFF devices and the gate/body currents push
    through it. The VDD current is then the sum at the VDD node. With include_inputs, terminals
    on inputs held at VDD also count (gate tunnelling supplied by the input sources).

    By KCL this equals leakage_vdd_terminals() exactly for SPICE currents (the oracle check).
    currents maps "<fet>_<id|ig|is|ib>" to amps (scalars, arrays or DataFrame columns), so the
    same formula serves the SPICE oracle check and the ML prediction.
    """
    on = sorted(on_devices(gate, bits))

    def node_sum(node):
        """Sum of currents into the terminals at node: known part + coefficients on the unknowns."""
        known, coef = 0.0, np.zeros(len(on))
        for name, _, *terms in GATES[gate]:
            for t, n, c in zip(TERMINALS, terms, CURRENTS):
                if n != node:
                    continue
                if name in on and t == "d":
                    coef[on.index(name)] += 1
                elif name in on and t == "s":
                    coef[on.index(name)] -= 1
                    known = known - currents[f"{name}_ig"] - currents[f"{name}_ib"]
                else:
                    known = known + currents[f"{name}_{c}"]
        return known, coef

    # KCL at the internal nodes: A t = -known
    rows = [node_sum(n) for n in nodes(gate)]
    A = np.array([coef for _, coef in rows]).reshape(len(rows), len(on))
    A_pinv = np.linalg.pinv(A)
    t = [sum(-A_pinv[k, j] * known for j, (known, _) in enumerate(rows)) for k in range(len(on))]

    total = 0.0
    for rail in _supply_rails(gate, bits, include_inputs):
        known, coef = node_sum(rail)
        # Only combinations of t that KCL determines may enter (e.g. the sum of parallel ON PMOS)
        if not np.allclose(coef @ (np.eye(len(on)) - A_pinv @ A), 0):
            raise ValueError(f"{gate} {bits}: supply current depends on an undetermined ON current")
        total = total + known + sum(coef[k] * t[k] for k in range(len(on)))
    return total


def measurements(gate):
    """(vector name, ngspice expression) for everything recorded per simulation."""
    out = [("i_supply", "-i(vsupply)")]                       # current delivered by VDD
    out += [(f"i_in_{n}", f"-i(vin_{n})") for n in inputs(gate)]   # current delivered by input n
    out += [(f"v_{n}", f"v({n})") for n in nodes(gate)]
    out += [(f"{name}_{c}", f"i(v{name}_{t})")               # ammeter current = INTO terminal t
            for name, *_ in GATES[gate] for t, c in zip(TERMINALS, CURRENTS)]
    return out


def build_netlist(gate, bits, corner, control=False):
    """Gate netlist at one corner; with control=True it also runs .op and prints the results."""
    vdd = corner["vdd"]
    lines = [
        f"* {gate.upper()} inputs {'AB'[:len(bits)]}={bits}, corner {int(corner['corner'])}",
        model_card("nmos", corner_params(corner, "nmos")),
        model_card("pmos", corner_params(corner, "pmos")),
        "",
        config.SPICE_OPTIONS,
        f".temp {corner['temp']!r}",
        "",
        f"vsupply vdd 0 DC {vdd!r}",
    ]
    lines += [f"vin_{n} {n} 0 DC {(vdd if bit == '1' else 0.0)!r}"
              for n, bit in zip(inputs(gate), bits)]
    lines += ["", "* M<name> d g s b, each terminal through a 0 V ammeter v<name>_<terminal>"]
    for name, mos_type, *terms in GATES[gate]:
        lines.append(f"{name} {' '.join(f'{name}_{t}' for t in TERMINALS)} {MODEL_NAME[mos_type]} "
                     f"W={config.GATE_W[mos_type]!r} L={config.L!r} "
                     f"AD={config.GATE_W[mos_type] * config.L_DIFF!r} AS={config.GATE_W[mos_type] * config.L_DIFF!r}")
        lines += [f"v{name}_{t} {node} {name}_{t} DC 0" for t, node in zip(TERMINALS, terms)]
    if control:
        lines += ["", ".control", "set numdgt=15", "op"]
        lines += [f"let {v} = {expr}" for v, expr in measurements(gate)]
        lines += [f"print {v}" for v, _ in measurements(gate)]
        lines += [".endc"]
    return "\n".join(lines + ["", ".end", ""])


def _control_script(jobs, netlist_paths):
    """One ngspice run that loads, solves and prints every netlist in turn."""
    lines = ["* batch driver", ".control", "set numdgt=15"]
    for k, ((gate, _, _), path) in enumerate(zip(jobs, netlist_paths)):
        lines += [f"echo @@run {k}", f"source {path}", "op"]
        lines += [f"let {v} = {expr}" for v, expr in measurements(gate)]
        lines += [f"print {v}" for v, _ in measurements(gate)]
        lines += ["destroy all", "remcirc"]   # a failed run cannot reuse the previous results
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n"


def _parse_output(stdout, jobs):
    """One dict {vector: value} per job; None where a run did not print every vector."""
    results = [dict() for _ in jobs]
    k = None
    for line in stdout.splitlines():
        m = re.match(r"\s*@@run (\d+)", line)
        if m:
            k = int(m.group(1))
            continue
        m = re.match(r"\s*(\w+)\s*=\s*(\S+)", line)
        if m and k is not None:
            results[k][m.group(1)] = float(m.group(2))
    expected = [{v for v, _ in measurements(gate)} for gate, _, _ in jobs]
    return [r if set(r) == want else None for r, want in zip(results, expected)]


def run_batch(jobs):
    """Simulate a list of (gate, bits, corner) jobs in a single ngspice process."""
    with tempfile.TemporaryDirectory(prefix="dvd_part3_") as tmp:
        tmp = Path(tmp)
        paths = []
        for k, (gate, bits, corner) in enumerate(jobs):
            path = tmp / f"g{k}.cir"
            path.write_text(build_netlist(gate, bits, corner))
            paths.append(path)
        driver = tmp / "driver.cir"
        driver.write_text(_control_script(jobs, paths))
        proc = subprocess.run([config.NGSPICE, "-b", str(driver)], capture_output=True, text=True)
    return _parse_output(proc.stdout, jobs)


def run_jobs(jobs, batch_size=100, workers=None):
    """Simulate many jobs, split into batches that run in parallel ngspice processes."""
    batches = [jobs[i:i + batch_size] for i in range(0, len(jobs), batch_size)]
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as pool:
        out = pool.map(run_batch, batches)
    return [r for batch in out for r in batch]

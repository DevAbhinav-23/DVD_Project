"""One ordered NAND graph shared by the parity logic and transistor netlist."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[1:1] = [str(ROOT), str(ROOT / "part1_dataset"), str(ROOT / "part3_gates")]
import config
from corners import corner_params
from gates import GATES
from spice_utils import MODEL_NAME, model_card

PRIMARY = tuple(f"d{k}" for k in range(config.PARITY_DATA_BITS)) + ("parity",)


def parity_graph():
    """Balanced eight-data-bit XOR tree followed by XOR with the parity input.

    Entries are (output, ordered input a, ordered input b). Pin a drives the
    upper NMOS in the Part 3 NAND2; preserving this order matters for leakage.
    """
    graph = []

    def xor(a, b, name):
        n1, n2, n3 = (f"{name}_n{k}" for k in (1, 2, 3))
        graph.extend([(n1, a, b), (n2, a, n1), (n3, b, n1), (name, n2, n3)])
        return name

    layer = list(PRIMARY[:-1])
    stage = 0
    while len(layer) > 1:
        layer = [xor(layer[k], layer[k + 1], f"s{stage}_{k // 2}")
                 for k in range(0, len(layer), 2)]
        stage += 1
    xor(layer[0], "parity", "error")
    return tuple(graph)


GRAPH = parity_graph()
OUTPUT = GRAPH[-1][0]


def logic(vector):
    if len(vector) != len(PRIMARY) or set(vector) - {"0", "1"}:
        raise ValueError(f"expected {len(PRIMARY)} binary inputs, got {vector!r}")
    values = dict(zip(PRIMARY, map(int, vector)))
    for out, a, b in GRAPH:
        values[out] = 1 - (values[a] & values[b])
    return values


def all_vectors():
    return [f"{n:0{len(PRIMARY)}b}" for n in range(2 ** len(PRIMARY))]


def build_netlist(corner, vector="000000000"):
    """Complete static CMOS circuit; no ideal logic elements or output load."""
    logic(vector)
    lines = ["* 8 data bits + even-parity bit; error=1 indicates odd total parity",
             "* Vector order: " + " ".join(PRIMARY),
             model_card("nmos", corner_params(corner, "nmos")),
             model_card("pmos", corner_params(corner, "pmos")),
             config.SPICE_OPTIONS, f".temp {float(corner['temp']):.17g}",
             f"vsupply vdd 0 DC {float(corner['vdd']):.17g}"]
    lines += [f"vin_{pin} {pin} 0 DC {int(bit) * float(corner['vdd']):.17g}"
              for pin, bit in zip(PRIMARY, vector)]
    for out, a, b in GRAPH:
        nodes = {"a": a, "b": b, "out": out, "x": f"{out}_stack", "vdd": "vdd", "0": "0"}
        for name, kind, *terms in GATES["nand2"]:
            lines.append(f"m{out}_{name} {' '.join(nodes[n] for n in terms)} "
                         f"{MODEL_NAME[kind]} W={config.GATE_W[kind]:.17g} L={config.L:.17g}")
    return "\n".join(lines) + "\n.end\n"


def controlled_netlist(corner, vectors):
    lines = build_netlist(corner, vectors[0]).rsplit(".end", 1)[0].splitlines()
    # This small circuit is parallelized across corners. Avoid OpenMP workers
    # spinning against each other inside every concurrent ngspice process.
    lines += [".control", "set numdgt=15", "set noaskquit", "set num_threads=1"]
    measures = [("i_supply", "-i(vsupply)")]
    measures += [(f"i_in_{pin}", f"-i(vin_{pin})") for pin in PRIMARY]
    measures += [(f"v_{out}", f"v({out})") for out, _, _ in GRAPH]
    for vector in vectors:
        lines += [f"echo @@vector {vector}"]
        lines += [f"alter vin_{pin} {int(bit) * float(corner['vdd']):.17g}"
                  for pin, bit in zip(PRIMARY, vector)]
        lines += ["op"]
        lines += [f"let {name} = {expr}" for name, expr in measures]
        lines += [f"print {name}" for name, _ in measures]
        lines += ["destroy all"]
    return "\n".join(lines + ["quit", ".endc", ".end", ""])


def dc_netlist(corner):
    """Sweep an integer code, decoded into nine exact 0/VDD ideal input sources.

    The zero-volt vin sources retain the same input-current measurements as
    the independent .op method. The behavioral sources only drive inputs;
    all 128 circuit transistors are unchanged. Reusing the previous DC point
    is substantially faster than reinitializing Newton at every .op call.
    """
    lines = build_netlist(corner).rsplit(".end", 1)[0].splitlines()
    lines = [line for line in lines if not line.startswith("vin_")]
    lines += ["vcode code 0 DC 0"]
    for k, pin in enumerate(PRIMARY):
        divisor = 2 ** (len(PRIMARY) - k - 1)
        lines += [f"vin_{pin} {pin} drive_{pin} DC 0",
                  f"bdrive_{pin} drive_{pin} 0 V={{{float(corner['vdd']):.17g}*"
                  # The quarter-code offset keeps integer sweep points away
                  # from floor() discontinuities during numerical linearization.
                  f"(floor((v(code)+0.25)/{divisor})-2*floor((v(code)+0.25)/{2 * divisor}))}}"]
    measures = [("i_supply", "-i(vsupply)")]
    measures += [(f"i_in_{pin}", f"-i(vin_{pin})") for pin in PRIMARY]
    measures += [(f"v_{out}", f"v({out})") for out, _, _ in GRAPH]
    measures += [(f"v_input_{pin}", f"v({pin})") for pin in PRIMARY]
    lines += [".control", "set numdgt=17", "set num_threads=1", "set wr_singlescale",
              "set wr_vecnames", f"dc vcode 0 {2 ** len(PRIMARY) - 1} 1"]
    lines += [f"let {name} = {expr}" for name, expr in measures]
    lines += ["wrdata measurements.txt " + " ".join(name for name, _ in measures)]
    return "\n".join(lines + ["quit", ".endc", ".end", ""])

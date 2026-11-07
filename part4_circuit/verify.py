"""Exhaustive logic and structural checks, independent of SPICE/ML predictions."""
from circuit import GRAPH, OUTPUT, PRIMARY, all_vectors, build_netlist, logic
from corners import load_corners


def verify_logic():
    assert len(PRIMARY) == 9
    assert len(GRAPH) == 32
    available = set(PRIMARY)
    for out, a, b in GRAPH:
        assert a in available and b in available, (out, a, b)
        assert out not in available
        available.add(out)
    for vector in all_vectors():
        values = logic(vector)
        assert values[OUTPUT] == sum(map(int, vector)) % 2, vector
        flipped = vector[:-1] + str(1 - int(vector[-1]))
        assert values[OUTPUT] != logic(flipped)[OUTPUT]
    netlist = build_netlist(load_corners().iloc[0].to_dict())
    assert sum(line.startswith("m") for line in netlist.splitlines()) == 128
    print("PASS: 512 vectors, parity-bit inversion, ordered acyclic graph, 32 NAND2s / 128 FETs")


if __name__ == "__main__":
    verify_logic()

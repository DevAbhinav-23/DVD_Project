"""Checks for ordering, current ownership and failed/incorrect SPICE results."""
import unittest

import pandas as pd

from circuit import GRAPH, PRIMARY, all_vectors, logic
from compare import batch_estimates, estimates, validate_shared_corners, vector_counts
from corners import load_corners
from simulate import parse_output, validate
from verify import verify_logic


class CircuitTests(unittest.TestCase):
    def test_reject_mismatched_shared_corner(self):
        frame = load_corners().iloc[:1].copy()
        validate_shared_corners(frame)
        frame.loc[frame.index[0], "vdd"] *= 1.01
        with self.assertRaises(RuntimeError):
            validate_shared_corners(frame)

    def test_exhaustive_parity(self):
        verify_logic()

    def test_input_current_ownership(self):
        # Use distinct gate-pattern and a/b currents to expose pin swaps.
        lookup = pd.DataFrame({
            "inputs": ["00", "01", "10", "11"],
            "ml_leak": [1., 2., 4., 8.], "spice_leak": [1., 2., 4., 8.],
            "ml_ig_a": [3., 5., 7., 11.], "ml_ig_b": [13., 17., 19., 23.],
            "spice_ig_a": [3., 5., 7., 11.], "spice_ig_b": [13., 17., 19., 23.],
        }).set_index("inputs")
        batch = batch_estimates(lookup, {v: vector_counts(v) for v in all_vectors()}).set_index("vector")
        for vector in all_vectors():
            counts = vector_counts(vector)
            self.assertEqual(sum(c["gates"] for c in counts.values()), 32)
            actual = estimates(lookup, counts)
            values = logic(vector)
            plain = internal = primary = 0.
            for _, a, b in GRAPH:
                row = lookup.loc[f"{values[a]}{values[b]}"]
                plain += row.ml_leak
                if values[a]:
                    if a in PRIMARY:
                        primary += row.ml_ig_a
                    else:
                        internal += row.ml_ig_a
                if values[b]:
                    if b in PRIMARY:
                        primary += row.ml_ig_b
                    else:
                        internal += row.ml_ig_b
            self.assertEqual(actual["ml_plain"], plain)
            self.assertEqual(actual["ml_corrected"], plain + internal)
            self.assertEqual(actual["ml_with_inputs"], plain + internal + primary)
            for column, value in actual.items():
                self.assertEqual(batch.loc[vector, column], value)

    def test_reject_missing_simulation(self):
        with self.assertRaises(RuntimeError):
            parse_output("@@vector 000000000\ni_supply = 1e-6", ["000000000", "000000001"])

    def test_reject_partial_measurements(self):
        with self.assertRaises(RuntimeError):
            parse_output("@@vector 000000000\ni_supply = 1e-6", ["000000000"])

    def test_reject_incorrect_internal_logic(self):
        vector = "000000000"
        values = logic(vector)
        record = {"vector": vector, "i_supply": 1e-6,
                  **{f"v_{out}": .9 * values[out] for out, _, _ in GRAPH}}
        df = pd.DataFrame([record])
        self.assertEqual(validate(df, {"corner": 0, "vdd": .9}, [vector]), 0.)
        df.loc[0, f"v_{GRAPH[0][0]}"] = .9 * (1 - values[GRAPH[0][0]])
        with self.assertRaises(RuntimeError):
            validate(df, {"corner": 0, "vdd": .9}, [vector])

    def test_reject_incorrect_decoded_input_voltage(self):
        vector = "000000001"
        values = logic(vector)
        record = {"vector": vector, "i_supply": 1e-6,
                  **{f"v_{out}": .9 * values[out] for out, _, _ in GRAPH},
                  **{f"v_input_{pin}": .9 * int(bit) for pin, bit in zip(PRIMARY, vector)}}
        df = pd.DataFrame([record])
        self.assertEqual(validate(df, {"corner": 0, "vdd": .9}, [vector]), 0.)
        df.loc[0, "v_input_parity"] = .89
        with self.assertRaises(RuntimeError):
            validate(df, {"corner": 0, "vdd": .9}, [vector])


if __name__ == "__main__":
    unittest.main()

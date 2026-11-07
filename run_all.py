"""Regenerate all project deliverables, or only Part 4 from committed Parts 1-3.

python run_all.py                     # includes costly training/learning curves
python run_all.py --part4-only        # reuse saved datasets/models/gate records
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part4-only", action="store_true")
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    if args.workers is not None and args.workers < 1:
        parser.error("workers must be positive")
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    scripts = [] if args.part4_only else [
        "part1_dataset/generate.py", "part1_dataset/validate.py",
        "part2_models/train_compare.py", "part2_models/evaluate_test.py",
        "part2_models/learning_curve.py", "part3_gates/corners.py", "part3_gates/simulate.py",
        "part3_gates/compare.py"]
    commands = [[script] for script in scripts]
    commands += [["part4_circuit/test_circuit.py"], ["part4_circuit/simulate.py"]]
    if args.workers is not None:
        commands[-1] += ["--workers", str(args.workers)]
    commands += [["part4_circuit/compare.py"]]
    for command in commands:
        print("Running:", sys.executable, *command, flush=True)
        subprocess.run([sys.executable, *command], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()

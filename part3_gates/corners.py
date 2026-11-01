"""The 200 shared PVT corners used by every gate (Part 3) and by the parity checker (Part 4).

A corner is one draw of VDD and temperature plus one NMOS and one PMOS parameter set, using the
Part 1 distributions. The table is drawn once with SEEDS["corners"] and saved to data/corners.csv.

Usage:  python part3_gates/corners.py      # (re)writes data/corners.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def draw_corners(n=config.N_CORNERS, seed=config.SEEDS["corners"]):
    """Columns: corner, vdd, temp, nmos_<param>, pmos_<param> for param in PROCESS_PARAMS."""
    rng = np.random.default_rng(seed)
    cols = {
        "corner": np.arange(n),
        "vdd": config.VDD_NOM * rng.uniform(1 - config.VDD_VAR, 1 + config.VDD_VAR, n),
        "temp": rng.uniform(config.TEMP_MIN, config.TEMP_MAX, n),
    }
    # Scale factor keeps the sign of negative nominals (PMOS vth0)
    for mos_type in ("nmos", "pmos"):
        for name in config.PROCESS_PARAMS:
            cols[f"{mos_type}_{name}"] = config.NOMINAL[mos_type][name] * rng.uniform(
                1 - config.PROCESS_VAR, 1 + config.PROCESS_VAR, n)
    return pd.DataFrame(cols)


def load_corners(path=config.CORNERS_FILE):
    """Read the shared corner table, drawing and saving it first if it does not exist yet."""
    if not Path(path).exists():
        draw_corners().to_csv(path, index=False)
    return pd.read_csv(path)


def corner_params(corner, mos_type):
    """{vth0, toxe, ndep, u0, xj} of one device type at one corner (a row of the table)."""
    return {name: corner[f"{mos_type}_{name}"] for name in config.PROCESS_PARAMS}


if __name__ == "__main__":
    df = draw_corners()
    df.to_csv(config.CORNERS_FILE, index=False)
    print(f"{len(df)} corners -> {config.CORNERS_FILE.relative_to(config.ROOT)}")
    print(df.describe().T[["min", "mean", "max"]].to_string())

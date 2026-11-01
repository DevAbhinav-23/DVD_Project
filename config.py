"""Shared project settings. Every part of the project reads its constants from here."""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent
MODEL_FILE = ROOT / "models" / "22nm_MGK.pm"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

# ---------------------------------------------------------------- simulator
NGSPICE = "ngspice"
SPICE_OPTIONS = ".options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9"

# ---------------------------------------------------------------- assignment
VDD_NOM = 0.9          # V
VDD_VAR = 0.10         # VDD drawn uniformly from VDD_NOM * (1 +/- VDD_VAR)
L = 22e-9              # m, channel length = feature size
W_MIN = 1 * L          # m
W_MAX = 8 * L          # m
TEMP_MIN = -40.0       # degC
TEMP_MAX = 125.0       # degC

# ---------------------------------------------------------------- process parameters
# Nominal values copied from models/22nm_MGK.pm. Each is drawn uniformly
# from nominal * (1 +/- PROCESS_VAR); NMOS and PMOS are drawn separately.
PROCESS_VAR = 0.10
PROCESS_PARAMS = ["vth0", "toxe", "ndep", "u0", "xj"]
NOMINAL = {
    "nmos": {"vth0": 0.3692, "toxe": 6.5e-10, "ndep": 1.2e19, "u0": 0.0181, "xj": 7.2e-9},
    "pmos": {"vth0": -0.25399, "toxe": 6.7e-10, "ndep": 4.4e18, "u0": 0.0023, "xj": 7.2e-9},
}

# ---------------------------------------------------------------- transistor cases
# Gate and body voltages are fixed per case: "vdd" means the sample's VDD, 0 means ground.
CASES = {
    "nmos_on":  {"type": "nmos", "vg": "vdd", "vb": 0},
    "nmos_off": {"type": "nmos", "vg": 0,     "vb": 0},
    "pmos_on":  {"type": "pmos", "vg": 0,     "vb": "vdd"},
    "pmos_off": {"type": "pmos", "vg": "vdd", "vb": "vdd"},
}

# ---------------------------------------------------------------- dataset
N_SAMPLES = 10_000
CSV_COLUMNS = ["vdd", "temp", "w", "vd", "vs", "vg", "vb",
               "vth0", "toxe", "ndep", "u0", "xj",
               "id", "ig", "is", "ib"]

# ---------------------------------------------------------------- random seeds
SEEDS = {
    "nmos_on": 101,
    "nmos_off": 102,
    "pmos_on": 103,
    "pmos_off": 104,
    "split": 42,        # Part 2: train / validation / test split
    "corners": 2026,    # Part 3 and 4: the 200 shared PVT corners
}
N_CORNERS = 200
CORNERS_FILE = DATA_DIR / "corners.csv"

# ---------------------------------------------------------------- gates (Parts 3 and 4)
# The spec gives no gate sizing, so every NMOS and PMOS in a gate is minimum size (W = Lmin).
GATE_W = {"nmos": W_MIN, "pmos": W_MIN}

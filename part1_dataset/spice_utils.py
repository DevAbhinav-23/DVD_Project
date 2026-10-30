"""Build single-transistor netlists, run them in ngspice and read back the terminal currents.

Currents follow the project convention: positive = flowing INTO the transistor terminal.
"""
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

CURRENTS = ["id", "ig", "is", "ib"]
MODEL_NAME = {"nmos": "nch", "pmos": "pch"}   # renamed so the model name is not a SPICE keyword


def _split_model_file(path=config.MODEL_FILE):
    """Return {"nmos": card_text, "pmos": card_text} from the PTM model file."""
    text = Path(path).read_text()
    cards = {}
    for block in re.split(r"(?im)^(?=\.model\s)", text)[1:]:
        mos_type = block.split()[1].lower()
        cards[mos_type] = block.strip()
    return cards


_CARDS = _split_model_file()


def model_card(mos_type, params):
    """Model card for one sample: renamed model with vth0, toxe, ndep, u0, xj replaced."""
    card = re.sub(r"(?i)^\.model\s+\S+", f".model {MODEL_NAME[mos_type]}", _CARDS[mos_type], count=1)
    for name in config.PROCESS_PARAMS:
        card, n = re.subn(rf"(?i)\b({name}\s*=\s*)\S+", rf"\g<1>{params[name]!r}", card)
        if n != 1:
            raise ValueError(f"expected exactly one '{name}' in the {mos_type} card, found {n}")
    return card


def build_netlist(sample, mos_type):
    """Single-transistor netlist (same layout as part1_dataset/netlists/*.cir)."""
    return f"""* {mos_type} single transistor sample
{model_card(mos_type, sample)}

{config.SPICE_OPTIONS}
.temp {sample['temp']!r}

M1 d g s b {MODEL_NAME[mos_type]} W={sample['w']!r} L={config.L!r}

Vd d 0 DC {sample['vd']!r}
Vg g 0 DC {sample['vg']!r}
Vs s 0 DC {sample['vs']!r}
Vb b 0 DC {sample['vb']!r}

.end
"""


def _control_script(netlist_paths):
    """One ngspice run that loads, solves and prints every netlist in turn."""
    lines = ["* batch driver", ".control", "set numdgt=15"]
    for k, path in enumerate(netlist_paths):
        lines += [
            f"echo @@sample {k}",
            f"source {path}",
            "op",
            "let id = -i(vd)",
            "let ig = -i(vg)",
            "let is = -i(vs)",
            "let ib = -i(vb)",
            "print id ig is ib",
            "destroy all",     # drop this sample's results so a failed run cannot reuse them
            "remcirc",
        ]
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n"


def _parse_output(stdout, n):
    """Return a list of n dicts {id, ig, is, ib}; None where a sample produced no result."""
    results = [dict() for _ in range(n)]
    k = None
    for line in stdout.splitlines():
        m = re.match(r"\s*@@sample (\d+)", line)
        if m:
            k = int(m.group(1))
            continue
        m = re.match(r"\s*(id|ig|is|ib)\s*=\s*(\S+)", line)
        if m and k is not None:
            results[k][m.group(1)] = float(m.group(2))
    return [r if len(r) == 4 else None for r in results]


def run_batch(samples, mos_type):
    """Simulate a list of samples of one transistor type in a single ngspice process."""
    with tempfile.TemporaryDirectory(prefix="dvd_part1_") as tmp:
        tmp = Path(tmp)
        paths = []
        for k, sample in enumerate(samples):
            path = tmp / f"s{k}.cir"
            path.write_text(build_netlist(sample, mos_type))
            paths.append(path)
        driver = tmp / "driver.cir"
        driver.write_text(_control_script(paths))
        proc = subprocess.run([config.NGSPICE, "-b", str(driver)],
                              capture_output=True, text=True)
    return _parse_output(proc.stdout, len(samples))


def run_samples(samples, mos_type, batch_size=250, workers=None):
    """Simulate many samples, split into batches that run in parallel ngspice processes."""
    batches = [samples[i:i + batch_size] for i in range(0, len(samples), batch_size)]
    workers = workers or os.cpu_count()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        out = pool.map(run_batch, batches, [mos_type] * len(batches))
    return [r for batch in out for r in batch]


if __name__ == "__main__":
    # Self-test: nominal corner of each case, compare with part1_dataset/netlists/*.cir
    for case, spec in config.CASES.items():
        mos_type = spec["type"]
        vdd = config.VDD_NOM
        vg = vdd if spec["vg"] == "vdd" else spec["vg"]
        vb = vdd if spec["vb"] == "vdd" else spec["vb"]
        vd, vs = (vdd, 0.0) if mos_type == "nmos" else (0.0, vdd)
        sample = {"vdd": vdd, "temp": 27.0, "w": 44e-9, "vd": vd, "vs": vs, "vg": vg, "vb": vb,
                  **config.NOMINAL[mos_type]}
        r = run_batch([sample], mos_type)[0]
        kcl = sum(r.values())
        print(f"{case:9s} " + "  ".join(f"{k}={r[k]: .6e}" for k in CURRENTS) + f"  kcl={kcl: .2e}")

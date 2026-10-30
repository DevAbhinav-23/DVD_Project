"""Feature engineering, target transform and the saved per-case model.

Each terminal current I is modelled as  I = sign(I) * 10**y,  y = log10|I|:
  * a regressor predicts y (currents span ~15 decades, so log space is essential);
  * a classifier predicts sign(I) when that terminal's sign is mixed in the training
    data (e.g. Id/Is flip with vd < vs); otherwise the constant sign is stored.

Part 3/4 usage (part2_models/ must be on sys.path so the pickled classes resolve):
    sys.path.insert(0, "part2_models")
    from leakage_model import load_case_model
    m = load_case_model("results/part2/models/nmos_off.joblib")
    currents = m.predict(df)   # df has the 12 input columns -> DataFrame id, ig, is, ib
"""
import joblib
import numpy as np
import pandas as pd

INPUTS = ["vdd", "temp", "w", "vd", "vs", "vg", "vb", "vth0", "toxe", "ndep", "u0", "xj"]
TARGETS = ["id", "ig", "is", "ib"]
I_FLOOR = 1e-21  # |I| below this is treated as numerically zero (SPICE abstol is 1e-18)

K_Q = 8.617e-5


def make_features(df):
    """Raw inputs plus physically motivated combinations (all device types)."""
    X = df[INPUTS].astype(float).copy()
    T = X["temp"] + 273.15
    vt = K_Q * T
    v_lo = np.minimum(X["vd"], X["vs"])
    v_hi = np.maximum(X["vd"], X["vs"])
    avth = X["vth0"].abs()
    X["vds"] = X["vd"] - X["vs"]
    X["vds_abs"] = X["vds"].abs()
    X["vgs"] = X["vg"] - X["vs"]
    X["vgd"] = X["vg"] - X["vd"]
    X["vbs"] = X["vb"] - X["vs"]
    X["vbd"] = X["vb"] - X["vd"]
    X["vg_vlo"] = X["vg"] - v_lo
    X["vg_vhi"] = X["vg"] - v_hi
    X["vb_vlo"] = X["vb"] - v_lo
    X["vb_vhi"] = X["vb"] - v_hi
    X["inv_vt"] = 1.0 / vt
    X["log_w"] = np.log(X["w"])
    X["log_toxe"] = np.log(X["toxe"])
    X["log_ndep"] = np.log(X["ndep"])
    X["log_u0"] = np.log(X["u0"])
    # Subthreshold exponents (gate overdrive / thermal voltage) for n- and p-type.
    X["ovn_vt"] = (X["vg"] - v_lo - avth) / vt
    X["ovp_vt"] = (v_hi - X["vg"] - avth) / vt
    X["vds_vt"] = X["vds_abs"] / vt
    return X


def to_log(i):
    return np.log10(np.maximum(np.abs(i), I_FLOOR))


class CaseModel:
    """Four terminal models (regressor on log10|I| + sign) for one device case."""

    def __init__(self, family, features, regs, signs):
        self.family = family
        self.features = features   # columns kept after dropping constants
        self.regs = regs           # {target: fitted regressor on log10|I|}
        self.signs = signs         # {target: +1 / -1 / fitted classifier}

    def _X(self, df):
        return make_features(df)[self.features]

    def predict_log(self, df):
        X = self._X(df)
        return pd.DataFrame({t: self.regs[t].predict(X) for t in TARGETS}, index=df.index)

    def predict_sign(self, df):
        X = self._X(df)
        out = {}
        for t in TARGETS:
            s = self.signs[t]
            out[t] = np.full(len(X), s) if np.isscalar(s) else np.where(s.predict(X) > 0, 1.0, -1.0)
        return pd.DataFrame(out, index=df.index)

    def predict(self, df):
        return self.predict_sign(df) * 10.0 ** self.predict_log(df)


def load_case_model(path):
    return joblib.load(path)


class Column:
    """Expose one output of a multi-output regressor as a single-target model."""

    def __init__(self, model, k):
        self.model, self.k = model, k

    def predict(self, X):
        return self.model.predict(X)[:, self.k]


class SignModel:
    """Wrap a {0,1} classifier so predict() returns -1 / +1."""

    def __init__(self, clf):
        self.clf = clf

    def predict(self, X):
        return np.where(self.clf.predict(X) == 1, 1.0, -1.0)

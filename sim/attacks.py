"""Attack definitions and generation (owner: Person 1).

An attack type is described by a plain `spec` dict (probabilities and amount parameters).
`attack_spec(cfg, t)` builds the hand-written spec from the config; the learned attacker
(sim/attacker.py) builds modified specs. `generate_attack_type` turns a spec into payments.

Signals an attacker cannot hide are listed per attack type in the config (`immutable`) and
read through `immutable_signals`. Nothing here is hard-coded: every number lives in the config.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ATTACK_TYPES = ("simswap", "screenshare", "collect", "replay", "stolen")
NETWORKS = ("home", "mobile", "public")

COLUMNS = [
    "kind", "attack_type", "median", "ratio", "amount", "new_device", "network", "new_payee",
    "velocity", "sim_change", "remote", "far_location", "fri", "u",
]


def immutable_signals(cfg, attack_type: str) -> list[str]:
    """Signals this attack needs and cannot hide (simswap: sim_change, screenshare: remote,
    collect and stolen: new_payee). The learned attacker must leave these at their base value."""
    defaults = {
        "simswap": ["sim_change"],
        "screenshare": ["remote"],
        "collect": ["new_payee"],
        "replay": [],
        "stolen": ["new_payee"],
    }
    attacks = getattr(cfg, "generator", cfg).attacks
    attack = attacks[attack_type]
    return list(getattr(attack, "immutable", defaults[attack_type]))


def attack_spec(cfg, attack_type: str) -> dict:
    """The hand-written parameters of one attack type, as a plain dict."""
    attacks = getattr(cfg, "generator", cfg).attacks
    A = attacks[attack_type]
    return {
        "new_device": float(A.new_device),
        "network": {k: float(A.network[k]) for k in NETWORKS},
        "new_payee": float(A.new_payee),
        "median_multiple": float(getattr(A, "median_multiple", A.ratio_center)),
        "sigma": float(getattr(A, "sigma", A.ratio_sigma)),
        "velocity": float(A.velocity),
        "sim_change": float(getattr(A, "sim_change", A.true_sim_change)),
        "remote": float(getattr(A, "remote", A.true_remote)),
        "far_location": float(A.far_location),
        "fri": [float(x) for x in A.fri],
        # chance the attacker routes the money to a clean payee number (fri forced to 0).
        # 0 for the hand-written attack; the learned attacker may raise it.
        "fri_evasion": 0.0,
    }


def _pick(rng, probs, n):
    p = np.asarray(probs, dtype=float)
    return rng.choice(len(p), size=n, p=p / p.sum())


def make_frame(kind, attack_type, median, ratio, flags, network, fri) -> pd.DataFrame:
    """Build a payment table in the shared A3 format. `u` is filled in by the caller."""
    n = len(median)
    amount = np.maximum(1, np.rint(median * ratio)).astype(int)
    return pd.DataFrame({
        "kind": kind,
        "attack_type": attack_type,
        "median": median.astype(int),
        "ratio": ratio.astype(float),
        "amount": amount,
        "new_device": flags["new_device"],
        "network": network,
        "new_payee": flags["new_payee"],
        "velocity": flags["velocity"],
        "sim_change": flags["sim_change"],
        "remote": flags["remote"],
        "far_location": flags["far_location"],
        "fri": fri.astype(int),
        "u": np.zeros(n),
    })[COLUMNS]


def generate_attack_type(attack_type, spec, user_medians, n, rng, ev, coverage,
                         evasive_params=None) -> pd.DataFrame:
    """Generate `n` attacks of one type from `spec`.

    rng: main stream. The draw order below is fixed; do not reorder it, or every seed changes.
    ev:  separate stream for the evasive and fri-evasion draws, so switching evasive mode on
         never shifts the main stream (normal and evasive data stay paired).
    evasive_params: the hand-written evasive variant (cfg.generator.evasive_params) or None.
    The `u` column is left at 0; the caller draws it last.
    """
    m = user_medians[rng.integers(0, len(user_medians), n)]
    r = np.maximum(
        1.2,
        np.exp(np.log(spec["median_multiple"]) + spec["sigma"] * rng.standard_normal(n)),
    )
    net_idx = _pick(rng, [spec["network"][k] for k in NETWORKS], n)
    velocity = rng.random(n) < spec["velocity"]
    fri = _pick(rng, spec["fri"], n)

    look_normal_u, look_ratio_u, fri_u = ev.random(n), ev.random(n), ev.random(n)
    fri_zero_p = spec.get("fri_evasion", 0.0)
    if evasive_params is not None:
        normal_prob = getattr(evasive_params, "look_normal_prob",
                              evasive_params.normal_amount_prob)
        r = np.where(look_normal_u < normal_prob, 1.0 + look_ratio_u, r)
        velocity = np.zeros(n, dtype=bool)
        net_idx = np.where(net_idx == 2, 1, net_idx)
        fri_zero_p = max(fri_zero_p, evasive_params.fri_zero_prob)
    fri = np.where(fri_u < fri_zero_p, 0, fri)

    flags = {
        "new_device": rng.random(n) < spec["new_device"],
        "new_payee": rng.random(n) < spec["new_payee"],
        "velocity": velocity,
        "far_location": rng.random(n) < spec["far_location"],
        "sim_change": (rng.random(n) < spec["sim_change"])
        & (rng.random(n) < getattr(coverage, "sim_feed", coverage.sim_change)),
        "remote": (rng.random(n) < spec["remote"]) & (rng.random(n) < coverage.remote),
    }
    return make_frame("attack", attack_type, m, r, flags, np.array(NETWORKS)[net_idx], fri)

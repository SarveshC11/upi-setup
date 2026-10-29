"""Evaluation metrics (owner: Person 3).

All policies are evaluated on the same payments and the same random draw `u`, so differences
between policies are not noise. Friction numbers are per 1,000 genuine payments.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from policy.engine import SIGNAL_GROUPS, make_engine
from sim.attacks import ATTACK_TYPES

TIER_CODES = ("0", "W", "1", "2", "3")
_IDX = {t: i for i, t in enumerate(TIER_CODES)}


def _codes(tiers: pd.Series) -> np.ndarray:
    codes = tiers.map(_IDX)
    if codes.isna().any():
        bad = sorted(set(tiers[codes.isna()]))
        raise ValueError(f"unknown tier codes from policy: {bad}")
    return codes.to_numpy(dtype=int)


def evaluate(policy, legit: pd.DataFrame, attacks: pd.DataFrame, assume) -> dict:
    """assume = cfg.costs (friction, abandon, p_stop). Returns a dict of metrics."""
    fr = np.array([assume["friction"][t] for t in TIER_CODES], dtype=float)
    ab = np.array([assume["abandon"][t] for t in TIER_CODES], dtype=float)
    ps = np.array([[assume["p_stop"][t][a] for a in ATTACK_TYPES] for t in TIER_CODES], dtype=float)

    lt = _codes(policy(legit))
    n = len(legit)
    out = {
        "friction": fr[lt].sum() / n * 1000,
        "extra": float((lt != _IDX["0"]).mean() * 1000),
        "abandoned": float((legit["u"].to_numpy() < ab[lt]).mean() * 1000),
        "holds": float((lt == _IDX["2"]).mean() * 1000),
        "blocks": float((lt == _IDX["3"]).mean() * 1000),
    }

    at = _codes(policy(attacks))
    ti = attacks["attack_type"].map({a: i for i, a in enumerate(ATTACK_TYPES)}).to_numpy(dtype=int)
    stopped = attacks["u"].to_numpy() < ps[at, ti]
    amount = attacks["amount"].to_numpy(dtype=float)
    total = float(amount.sum())
    prevented = float(amount[stopped].sum())
    out.update({
        "prevented": prevented / total * 100 if total else 0.0,
        "lost": total - prevented,
        "total": total,
    })
    per = {}
    for i, a in enumerate(ATTACK_TYPES):
        m = ti == i
        per[a] = {"n": int(m.sum()), "stopped": int(stopped[m].sum()),
                  "share": float(stopped[m].mean()) if m.any() else 0.0}
    out["per_type"] = per
    return out


def sweep(weights, legit, attacks, assume, shifts, make_policy=None) -> list[dict]:
    """Evaluate a policy family at each strictness shift d (thresholds are base + d).

    By default the family is the points engine with `weights`. Pass `make_policy(d)` to sweep
    another family, for example the ML baseline.
    """
    rows = []
    for d in shifts:
        policy = make_policy(d) if make_policy is not None else make_engine(weights, d)
        m = evaluate(policy, legit, attacks, assume)
        m["shift"] = d
        rows.append(m)
    return rows


def ablation(weights, shift, legit, attacks, assume) -> list[dict]:
    """Switch off one signal group at a time and report the change against the full engine."""
    base = evaluate(make_engine(weights, shift), legit, attacks, assume)
    rows = []
    for group, keys in SIGNAL_GROUPS.items():
        w2 = copy.deepcopy(dict(weights))
        for k in keys:
            w2[k] = 0
        m = evaluate(make_engine(w2, shift), legit, attacks, assume)
        rows.append({
            "group": group,
            "prevented": m["prevented"], "friction": m["friction"],
            "d_prevented": m["prevented"] - base["prevented"],
            "d_friction": m["friction"] - base["friction"],
        })
    return rows


def scale_costs(assume, friction: float = 1.0, stop: float = 1.0) -> dict:
    """Sensitivity helper. `friction` scales friction points and abandonment chances;
    `stop` scales the chance that an action stops an attack. Probabilities are capped at 1."""
    return {
        "friction": {t: v * friction for t, v in assume["friction"].items()},
        "abandon": {t: min(1.0, v * friction) for t, v in assume["abandon"].items()},
        "p_stop": {t: {a: min(1.0, p * stop) for a, p in row.items()}
                   for t, row in assume["p_stop"].items()},
    }


def best_prevented_within(curve: list[dict], budget: float) -> float:
    """Highest fraud-stopped % among sweep points whose friction does not exceed `budget`."""
    ok = [r["prevented"] for r in curve if r["friction"] <= budget + 1e-9]
    return max(ok) if ok else 0.0


def scalar_metrics(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "per_type"}

"""Evaluation metrics.

INTERIM STAND-IN (owner: Person 3). Written by Person 4 from guide section B3 so /simulate and
the parity tests work. Person 3's version (with ablation, sensitivity, plots and
run_experiment) replaces this; evaluate() and sweep() must keep these signatures.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from common.config import ATTACK_TYPES, TIERS, CostConfig
from policy.engine import DEFAULT_THRESHOLDS, SIGNAL_GROUPS, Policy, make_engine


def evaluate(policy: Policy, legit: pd.DataFrame, attacks: pd.DataFrame,
             assume: CostConfig) -> dict:
    if isinstance(assume, Mapping):
        friction = assume["friction"]
        abandon = assume["abandon"]
        p_stop = assume["p_stop"]
    else:
        friction = assume.friction.as_dict()
        abandon = assume.abandon.as_dict()
        p_stop = assume.p_stop.as_dict()

    tier_idx = {t: i for i, t in enumerate(TIERS)}
    type_idx = {t: i for i, t in enumerate(ATTACK_TYPES)}
    fr_tab = np.array([friction[t] for t in TIERS])
    ab_tab = np.array([abandon[t] for t in TIERS])
    ps_tab = np.array([[p_stop[t][a] for a in ATTACK_TYPES] for t in TIERS])

    lt = policy(legit).to_numpy()
    n = len(legit)
    per_k = 1000.0 / n if n else 0.0
    li = pd.Series(lt).map(tier_idx).to_numpy(dtype=int)
    fr = fr_tab[li]
    ab = ab_tab[li]

    at = policy(attacks).to_numpy()
    types = attacks["attack_type"].to_numpy()
    ai = pd.Series(at).map(tier_idx).to_numpy(dtype=int)
    ps = ps_tab[ai, pd.Series(types).map(type_idx).to_numpy(dtype=int)]
    stopped = attacks["u"].to_numpy() < ps
    amt = attacks["amount"].to_numpy(dtype=float)
    total = amt.sum()
    prevented = amt[stopped].sum()

    result = {
        "friction": float(fr.sum() * per_k),
        "extra": float((lt != "0").sum() * per_k),
        "abandoned": float((legit["u"].to_numpy() < ab).sum() * per_k),
        "holds": float((lt == "2").sum() * per_k),
        "blocks": float((lt == "3").sum() * per_k),
        "prevented_pct": float(100.0 * prevented / total) if total else 0.0,
        "lost": float(total - prevented),
        "per_type_stopped": {
            t: float(stopped[types == t].mean()) if (types == t).any() else 0.0
            for t in ATTACK_TYPES
        },
    }
    result["total"] = float(total)
    result["prevented"] = float(100.0 * prevented / total) if total else 0.0
    result["per_type"] = {
        t: {
            "n": int((types == t).sum()),
            "stopped": int(stopped[types == t].sum()),
            "share": result["per_type_stopped"][t],
        }
        for t in ATTACK_TYPES
    }
    return result


def sweep(weights: Mapping[str, int], legit: pd.DataFrame, attacks: pd.DataFrame,
          assume: CostConfig, shifts: Iterable[int],
          thresholds: Sequence[int] = DEFAULT_THRESHOLDS) -> list[dict]:
    out = []
    for d in shifts:
        m = evaluate(make_engine(weights, d, thresholds), legit, attacks, assume)
        out.append({"shift": int(d), **m})
    return out


def scale_costs(assume, friction: float = 1.0, stop: float = 1.0) -> dict:
    if isinstance(assume, Mapping):
        source = assume
    else:
        source = {
            "friction": assume.friction.as_dict(),
            "abandon": assume.abandon.as_dict(),
            "p_stop": assume.p_stop.as_dict(),
        }
    return {
        "friction": {t: v * friction for t, v in source["friction"].items()},
        "abandon": {t: min(1.0, v * friction) for t, v in source["abandon"].items()},
        "p_stop": {
            t: {a: min(1.0, p * stop) for a, p in row.items()}
            for t, row in source["p_stop"].items()
        },
    }


def ablation(weights, shift, legit, attacks, assume) -> list[dict]:
    base = evaluate(make_engine(weights, shift), legit, attacks, assume)
    rows = []
    for group, keys in SIGNAL_GROUPS.items():
        reduced = dict(weights)
        for key in keys:
            reduced[key] = 0
        result = evaluate(make_engine(reduced, shift), legit, attacks, assume)
        rows.append({
            "group": group,
            "prevented": result["prevented"],
            "friction": result["friction"],
            "d_prevented": result["prevented"] - base["prevented"],
            "d_friction": result["friction"] - base["friction"],
        })
    return rows


def best_prevented_within(curve: list[dict], budget: float) -> float:
    values = [row["prevented"] for row in curve if row["friction"] <= budget + 1e-9]
    return max(values) if values else 0.0


def scalar_metrics(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "per_type"}

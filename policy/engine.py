"""Scoring engine (owner: Person 2; STARTER version written so the pipeline runs).

Points are weights: there is one set of numbers. Score = sum of points of signals that are on,
capped at 100. Tiers use thresholds base + shift.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

Policy = Callable[[pd.DataFrame], pd.Series]

BASE_THRESHOLDS = (20, 50, 70)

SIGNAL_GROUPS: dict[str, list[str]] = {
    "device": ["new_device"],
    "network": ["net_mobile", "net_public"],
    "payee": ["new_payee"],
    "amount": ["amt_2_10x", "amt_over_10x"],
    "velocity": ["velocity"],
    "sim": ["sim_change"],
    "remote": ["remote"],
    "location": ["far_location"],
    "fri": ["fri_medium", "fri_high", "fri_very_high"],
}


def signal_flags(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Boolean arrays, one per weight key."""
    ratio = df["ratio"].to_numpy(dtype=float)
    net = df["network"].to_numpy()
    fri = df["fri"].to_numpy()
    return {
        "new_device": df["new_device"].to_numpy(dtype=bool),
        "net_mobile": net == "mobile",
        "net_public": net == "public",
        "new_payee": df["new_payee"].to_numpy(dtype=bool),
        "amt_2_10x": (ratio >= 2) & (ratio <= 10),
        "amt_over_10x": ratio > 10,
        "velocity": df["velocity"].to_numpy(dtype=bool),
        "sim_change": df["sim_change"].to_numpy(dtype=bool),
        "remote": df["remote"].to_numpy(dtype=bool),
        "far_location": df["far_location"].to_numpy(dtype=bool),
        "fri_medium": fri == 1,
        "fri_high": fri == 2,
        "fri_very_high": fri == 3,
    }


def score_df(df: pd.DataFrame, weights: dict) -> np.ndarray:
    """Vectorised score 0..100 for every row."""
    flags = signal_flags(df)
    total = np.zeros(len(df))
    for key, on in flags.items():
        total += on * float(weights.get(key, 0))
    return np.minimum(100, total).astype(int)


def score(tx: dict, weights: dict) -> tuple[int, list[tuple[str, int]]]:
    """Score one payment. Returns (score 0..100, [(signal, points), ...])."""
    row = pd.DataFrame([{
        "ratio": tx["ratio"] if "ratio" in tx else tx["amount"] / max(1, tx["median"]),
        "network": tx.get("network", "home"),
        "fri": tx.get("fri", 0),
        "new_device": tx.get("new_device", False),
        "new_payee": tx.get("new_payee", False),
        "velocity": tx.get("velocity", False),
        "sim_change": tx.get("sim_change", False),
        "remote": tx.get("remote", False),
        "far_location": tx.get("far_location", False),
    }])
    flags = signal_flags(row)
    parts = [(k, int(weights.get(k, 0))) for k, on in flags.items() if on[0] and weights.get(k, 0)]
    return min(100, sum(p for _, p in parts)), parts


def tier_from_score(scores: np.ndarray, shift: int = 0, base=BASE_THRESHOLDS) -> np.ndarray:
    t1, t2, t3 = (b + shift for b in base)
    return np.select([scores >= t3, scores >= t2, scores >= t1], ["3", "2", "1"], default="0")


def make_engine(weights: dict, shift: int = 0, thresholds=BASE_THRESHOLDS) -> Policy:
    """Returns a vectorised policy: DataFrame in, Series of tier codes out."""
    w = dict(weights)

    def policy(df: pd.DataFrame) -> pd.Series:
        return pd.Series(tier_from_score(score_df(df, w), shift, thresholds), index=df.index)

    return policy

"""Optional ML baseline (owner: Person 3).

A gradient-boosted classifier on the same signals. Its attack probability is turned into a
0..100 score and then into tiers with the same thresholds and strictness shift as the engine,
so it draws its own trade-off curve instead of sitting at one arbitrary point.

Caveat: it is trained on data from the same synthetic generator, so it knows the attack
signatures. Treat it as an upper-bound reference, not as a fair real-world competitor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from sim.generate import generate

BASE_THRESHOLDS = (20, 50, 70)


def features(df: pd.DataFrame) -> np.ndarray:
    net = df["network"].to_numpy()
    return np.column_stack([
        np.log(np.clip(df["ratio"].to_numpy(dtype=float), 1e-3, None)),
        df["new_device"].to_numpy(dtype=float),
        (net == "mobile").astype(float),
        (net == "public").astype(float),
        df["new_payee"].to_numpy(dtype=float),
        df["velocity"].to_numpy(dtype=float),
        df["sim_change"].to_numpy(dtype=float),
        df["remote"].to_numpy(dtype=float),
        df["far_location"].to_numpy(dtype=float),
        df["fri"].to_numpy(dtype=float),
    ])


class MLScorer:
    def __init__(self, model):
        self.model = model

    def score_df(self, df: pd.DataFrame) -> np.ndarray:
        p = self.model.predict_proba(features(df))[:, 1]
        return np.rint(100 * p).astype(int)


def train_ml(cfg, seeds) -> MLScorer:
    """Train on generated data from `seeds` (use cfg.seeds.tune, never the report seeds)."""
    frames = []
    for s in seeds:
        legit, attacks = generate(cfg, s)
        frames += [legit, attacks]
    data = pd.concat(frames, ignore_index=True)
    y = (data["kind"] == "attack").to_numpy()
    model = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, random_state=0)
    model.fit(features(data), y)
    return MLScorer(model)


def make_ml_engine(scorer: MLScorer, shift: int = 0, thresholds=BASE_THRESHOLDS):
    t1, t2, t3 = (b + shift for b in thresholds)

    def policy(df: pd.DataFrame) -> pd.Series:
        s = scorer.score_df(df)
        return pd.Series(np.select([s >= t3, s >= t2, s >= t1], ["3", "2", "1"], default="0"),
                         index=df.index)

    return policy

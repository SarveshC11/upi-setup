"""Synthetic payment generator (owner: Person 1).

Output format: docs/team_work_guide.md, section A3. Genuine payments are generated here;
attack generation lives in sim/attacks.py so the learned attacker can reuse it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sim.attacks import (
    ATTACK_TYPES,
    COLUMNS,
    NETWORKS,
    _pick,
    attack_spec,
    generate_attack_type,
    make_frame,
)
from sim.rng import make_rng, make_side_rng

__all__ = ["COLUMNS", "generate", "user_medians"]

EVASIVE_SALT = 1  # side stream for evasive draws: see sim/rng.py


def user_medians(cfg, rng) -> np.ndarray:
    """Each user's usual payment in rupees. The first draw on a seed's main stream."""
    g = cfg.generator
    med = np.exp(np.log(g.median.loc) + g.median.sigma * rng.standard_normal(cfg.sizes.users))
    return np.rint(np.clip(med, g.median.min, g.median.max))


def _network(rng, probs, n):
    idx = _pick(rng, [probs[k] for k in NETWORKS], n)
    return np.array(NETWORKS)[idx]


def generate(cfg, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (legit_df, attacks_df) in the shared payment format.

    Same seed gives identical data. Evasive mode (cfg.generator.evasive) uses a separate random
    stream, so evasive and normal runs of one seed share every other draw (paired comparison).
    """
    rng = make_rng(seed)
    ev = make_side_rng(seed, EVASIVE_SALT)
    g = cfg.generator
    n_users = cfg.sizes.users
    per = cfg.sizes.legit_per_user
    n_att = cfg.sizes.attacks_per_type
    cov = g.coverage

    med = user_medians(cfg, rng)

    # genuine payments
    L = g.legit
    n = n_users * per
    median = med[np.repeat(np.arange(n_users), per)]
    big = rng.random(n) < g.ratio.big_prob
    ratio = np.where(
        big,
        rng.uniform(g.ratio.big_low, g.ratio.big_high, n),
        np.exp(g.ratio.sigma * rng.standard_normal(n)),
    )
    flags = {
        "new_device": rng.random(n) < L.new_device,
        "new_payee": rng.random(n) < L.new_payee,
        "velocity": rng.random(n) < L.velocity,
        "far_location": rng.random(n) < L.far_location,
        "sim_change": (rng.random(n) < L.true_sim_change) & (rng.random(n) < cov.sim_feed),
        "remote": (rng.random(n) < L.true_remote) & (rng.random(n) < cov.remote),
    }
    legit = make_frame("legit", None, median, ratio, flags, _network(rng, L.network, n),
                       _pick(rng, L.fri, n))

    # attacks
    evasive = g.evasive_params if g.evasive else None
    parts = [
        generate_attack_type(t, attack_spec(cfg, t), med, n_att, rng, ev, cov, evasive)
        for t in ATTACK_TYPES
    ]
    attacks = pd.concat(parts, ignore_index=True)

    # the shared random draw is generated last, so adding features never reshuffles it
    legit["u"] = rng.random(len(legit))
    attacks["u"] = rng.random(len(attacks))
    return legit, attacks

"""Synthetic payment generator (owner: Person 1; STARTER version written so the pipeline runs).

Person 1: replace or extend this file, keeping the output format in docs/team_work_guide.md (A3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sim.attacks import ATTACK_TYPES, NETWORKS
from sim.rng import make_rng

COLUMNS = [
    "kind", "attack_type", "median", "ratio", "amount", "new_device", "network", "new_payee",
    "velocity", "sim_change", "remote", "far_location", "fri", "u",
]


def _pick(rng, probs, n):
    p = np.asarray(probs, dtype=float)
    return rng.choice(len(p), size=n, p=p / p.sum())


def _network(rng, probs, n):
    idx = _pick(rng, [probs[k] for k in NETWORKS], n)
    return np.array(NETWORKS)[idx]


def _frame(kind, attack_type, median, ratio, flags, network, fri):
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


def generate(cfg, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (legit_df, attacks_df) in the shared payment format."""
    rng = make_rng(seed)
    g = cfg.generator
    n_users = cfg.sizes.users
    per = cfg.sizes.legit_per_user
    n_att = cfg.sizes.attacks_per_type
    cov = g.coverage

    # user habits
    med = np.exp(np.log(g.median.loc) + g.median.sigma * rng.standard_normal(n_users))
    med = np.rint(np.clip(med, g.median.min, g.median.max))

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
    legit = _frame("legit", None, median, ratio, flags, _network(rng, L.network, n),
                   _pick(rng, L.fri, n))

    # attacks
    parts = []
    for t in ATTACK_TYPES:
        A = cfg.attacks[t]
        m = med[rng.integers(0, n_users, n_att)]
        r = np.maximum(1.2, np.exp(np.log(A.median_multiple) + A.sigma * rng.standard_normal(n_att)))
        net_idx = _pick(rng, [A.network[k] for k in NETWORKS], n_att)
        velocity = rng.random(n_att) < A.velocity
        fri = _pick(rng, A.fri, n_att)
        if g.evasive:
            ep = g.evasive_params
            look_normal = rng.random(n_att) < ep.look_normal_prob
            r = np.where(look_normal, 1.0 + rng.random(n_att), r)
            velocity = np.zeros(n_att, dtype=bool)
            net_idx = np.where(net_idx == 2, 1, net_idx)
            fri = np.where(rng.random(n_att) < ep.fri_zero_prob, 0, fri)
        flags = {
            "new_device": rng.random(n_att) < A.new_device,
            "new_payee": rng.random(n_att) < A.new_payee,
            "velocity": velocity,
            "far_location": rng.random(n_att) < A.far_location,
            "sim_change": (rng.random(n_att) < A.sim_change) & (rng.random(n_att) < cov.sim_feed),
            "remote": (rng.random(n_att) < A.remote) & (rng.random(n_att) < cov.remote),
        }
        parts.append(_frame("attack", t, m, r, flags, np.array(NETWORKS)[net_idx], fri))
    attacks = pd.concat(parts, ignore_index=True)

    # the shared random draw is generated last, so adding features never reshuffles it
    legit["u"] = rng.random(len(legit))
    attacks["u"] = rng.random(len(attacks))
    return legit, attacks

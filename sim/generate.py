"""Synthetic payment generator.

INTERIM STAND-IN (owner: Person 1). Written by Person 4 from guide section B1 so the service's
/simulate endpoint and the parity tests can run. Person 1's version (with sim/rng.py,
sim/attacks.py, the immutable lists and the learned attacker) replaces this file; the
interface must stay:

    generate(cfg, seed) -> (legit_df, attacks_df)   # both in the A3 format
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common.config import ATTACK_TYPES, Config
from sim.attacks import _pick, attack_spec, generate_attack_type, make_frame
from sim.rng import make_rng, make_side_rng

COLUMNS = [
    "kind", "attack_type", "median", "ratio", "amount", "new_device", "network", "new_payee",
    "velocity", "sim_change", "remote", "far_location", "fri", "u",
]
_NETS = np.array(["home", "mobile", "public"], dtype=object)


def user_medians(cfg: Config, rng: np.random.Generator) -> np.ndarray:
    """Generate the per-user median amounts used by the simulator."""
    lp = cfg.generator.legit
    return np.clip(
        np.round(rng.lognormal(np.log(lp.median_center), lp.median_sigma, cfg.sizes.n_users)),
        lp.median_min,
        lp.median_max,
    ).astype(int)


def _network(rng: np.random.Generator, mix, n: int) -> np.ndarray:
    return _NETS[rng.choice(3, size=n, p=[mix.home, mix.mobile, mix.public])]


def _frame(**cols) -> pd.DataFrame:
    df = pd.DataFrame(cols)[COLUMNS]
    df["median"] = df["median"].astype(int)
    df["amount"] = df["amount"].astype(int)
    df["fri"] = df["fri"].astype(int)
    return df


def generate(
    cfg: Config, seed: int, n_users: int | None = None, payments_per_user: int | None = None,
    attacks_per_type: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (legit_df, attacks_df), both in the A3 format. Sizes default to cfg.sizes."""
    g = cfg.generator
    lp = g.legit
    n_users = cfg.sizes.n_users if n_users is None else n_users
    per_user = cfg.sizes.payments_per_user if payments_per_user is None else payments_per_user
    n_att = cfg.sizes.attacks_per_type if attacks_per_type is None else attacks_per_type
    rng = make_rng(seed)
    ev = make_side_rng(seed, 1)

    # --- genuine payments
    user_median = user_medians(cfg, rng)
    if n_users != cfg.sizes.n_users:
        user_median = user_median[:n_users]
    n = n_users * per_user
    median = np.repeat(user_median, per_user)
    big = rng.random(n) < lp.big_payment_prob
    ratio = np.where(
        big,
        rng.uniform(lp.big_ratio_low, lp.big_ratio_high, n),
        np.exp(lp.ratio_sigma * rng.standard_normal(n)),
    )
    true_sim = rng.random(n) < lp.true_sim_change
    true_remote = rng.random(n) < lp.true_remote
    flags = {
        "new_device": rng.random(n) < lp.new_device,
        "new_payee": rng.random(n) < lp.new_payee,
        "velocity": rng.random(n) < lp.velocity,
        "far_location": rng.random(n) < lp.far_location,
        "sim_change": true_sim & (rng.random(n) < g.coverage.sim_change),
        "remote": true_remote & (rng.random(n) < g.coverage.remote),
    }
    legit_df = make_frame("legit", None, median, ratio, flags,
                          _NETS[rng.choice(3, size=n, p=[lp.network.home, lp.network.mobile,
                                                          lp.network.public])],
                          _pick(rng, lp.fri, n))

    # --- attacks
    parts = []
    for t in ATTACK_TYPES:
        parts.append(generate_attack_type(
            t, attack_spec(cfg, t), user_median, n_att, rng, ev, g.coverage,
            g.evasive_params if g.evasive else None))
    attacks_df = pd.concat(parts, ignore_index=True)
    attacks_df["u"] = rng.random(len(attacks_df))
    return legit_df, attacks_df

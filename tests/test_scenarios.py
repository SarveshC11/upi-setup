import pandas as pd

from common.config import load_config
from policy.engine import make_engine, score, tier_from_score

W = load_config().policy["weights"]


def test_quiet_payment_scores_low_and_is_pin_only():
    s, parts = score({"amount": 300, "median": 250}, W)
    assert s == 0 and parts == []


def test_breakdown_adds_up():
    s, parts = score({"amount": 45000, "median": 250, "new_payee": True, "remote": True}, W)
    assert s == 70
    assert dict(parts) == {"new_payee": 15, "amt_over_10x": 25, "remote": 30}


def test_score_is_capped_at_100():
    tx = {"amount": 90000, "median": 250, "new_device": True, "new_payee": True,
          "remote": True, "sim_change": True, "fri": 3}
    assert score(tx, W)[0] == 100


def test_tier_boundaries_and_shift():
    import numpy as np
    sc = np.array([19, 20, 49, 50, 69, 70])
    assert list(tier_from_score(sc)) == ["0", "1", "1", "2", "2", "3"]
    assert list(tier_from_score(sc, shift=10)) == ["0", "0", "1", "1", "2", "2"]


def test_engine_policy_is_vectorised_and_aligned():
    df = pd.DataFrame({"ratio": [1.0, 12.0], "network": ["home", "home"], "fri": [0, 0],
                       "new_device": [False, False], "new_payee": [False, True],
                       "velocity": [False, False], "sim_change": [False, False],
                       "remote": [False, True], "far_location": [False, False]},
                      index=[5, 9])
    out = make_engine(W)(df)
    assert list(out.index) == [5, 9] and out.iloc[0] == "0" and out.iloc[1] == "3"


# ---- Golden cases from the team guide (B2), shift d = 0. Must pass exactly. ----
import numpy as np  # noqa: E402
import pytest  # noqa: E402

GOLDEN = {
    "A chai": (dict(network="mobile", ratio=0.72), 5, "0"),
    "B rent": (dict(network="home", new_payee=True, ratio=180), 40, "1"),
    "C sim swap": (dict(new_device=True, new_payee=True, sim_change=True, network="public",
                        ratio=180), 100, "3"),
    "D screen-share": (dict(remote=True, new_payee=True, ratio=180, network="home"), 70, "3"),
    "E stolen phone": (dict(new_payee=True, velocity=True, far_location=True, network="home",
                            ratio=180), 65, "2"),
}


@pytest.mark.parametrize("name", list(GOLDEN))
def test_golden_scores_and_tiers(name):
    tx, want_score, want_tier = GOLDEN[name]
    got, _ = score(tx, W)
    assert got == want_score
    assert tier_from_score(np.array([got]))[0] == want_tier


def test_golden_c_raw_total_is_110_before_cap():
    tx, _, _ = GOLDEN["C sim swap"]
    _, parts = score(tx, W)
    assert sum(p for _, p in parts) == 110


def test_signal_groups_cover_every_weight_exactly_once():
    from policy.engine import SIGNAL_GROUPS
    keys = [k for ks in SIGNAL_GROUPS.values() for k in ks]
    assert sorted(keys) == sorted(W) and len(keys) == len(set(keys)) == 13


def test_batch_matches_single_payment_scoring():
    from policy.engine import score_df
    from sim.generate import generate
    legit, _ = generate(load_config(), 1)
    sample = legit.head(300)
    batch = score_df(sample, W)
    single = [score(r, W)[0] for r in sample.to_dict("records")]
    assert list(batch) == single


def test_engine_scores_31500_payments_fast():
    import time

    from sim.generate import generate
    legit, attacks = generate(load_config(), 1)
    df = pd.concat([legit, attacks])
    pol = make_engine(W)
    t = time.perf_counter()
    pol(df)
    assert time.perf_counter() - t < 0.2

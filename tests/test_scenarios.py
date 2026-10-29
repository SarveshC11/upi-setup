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

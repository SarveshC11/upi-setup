import pandas as pd

from common.config import load_config
from eval.metrics import evaluate

A = load_config().costs


def test_hand_computed_example():
    # 4 genuine payments with tiers 0,1,2,3 and u chosen so abandon fires only for tier 3.
    # friction = (0 + 1 + 5 + 10) / 4 * 1000 = 4000; extra = 3/4 = 750; holds = blocks = 250.
    legit = pd.DataFrame({"u": [0.99, 0.99, 0.99, 0.10]})
    tiers = pd.Series(["0", "1", "2", "3"])
    # attacks: types all 'simswap'; stop chance table is read from config, so force certainty
    assume = {**A, "p_stop": {t: {a: (1.0 if t in ("1", "3") else 0.0) for a in A["p_stop"][t]}
                              for t in A["p_stop"]}}
    attacks = pd.DataFrame(
        {
            "attack_type": ["simswap"] * 4,
            "amount": [1000.0, 1000.0, 1000.0, 7000.0],
            "u": [0.5] * 4,
        }
    )
    atiers = pd.Series(["0", "1", "2", "3"])
    pols = iter([tiers, atiers])
    m = evaluate(lambda df: next(pols), legit, attacks, assume)
    assert m["friction"] == 4000 and m["extra"] == 750
    assert m["holds"] == 250 and m["blocks"] == 250
    assert m["abandoned"] == 250  # only the tier-3 payment has u below its abandon chance
    assert round(m["prevented"], 6) == 80.0  # 1000 (tier 1) + 7000 (tier 3) of 10000
    assert m["lost"] == 2000


def test_pin_only_changes_nothing():
    legit = pd.DataFrame({"u": [0.5] * 10})
    attacks = pd.DataFrame({"attack_type": ["stolen"] * 3, "amount": [100.0] * 3, "u": [0.1] * 3})
    m = evaluate(lambda df: pd.Series(["0"] * len(df)), legit, attacks, A)
    assert m["friction"] == 0 and m["prevented"] == 0

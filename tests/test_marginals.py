"""Generator tests (owner: Person 1): format, marginals, determinism, coverage, evasive mode."""
import numpy as np
import pandas as pd
import pytest

from common.config import load_config, with_overrides
from sim.attacks import ATTACK_TYPES, COLUMNS, immutable_signals
from sim.generate import generate

CFG = load_config()


@pytest.fixture(scope="module")
def data():
    return generate(CFG, 1)


def test_format_matches_a3(data):
    for df in data:
        assert list(df.columns) == COLUMNS
        for c in ("median", "amount", "fri"):
            assert pd.api.types.is_integer_dtype(df[c])
        for c in ("new_device", "new_payee", "velocity", "sim_change", "remote", "far_location"):
            assert df[c].dtype == bool
        assert pd.api.types.is_float_dtype(df["ratio"]) and pd.api.types.is_float_dtype(df["u"])
        assert df["u"].between(0, 1, inclusive="left").all()
        assert (df["amount"] == np.maximum(1, np.rint(df["median"] * df["ratio"]))).all()
        assert set(df["network"]) <= {"home", "mobile", "public"}
        assert set(df["fri"]) <= {0, 1, 2, 3}
    legit, attacks = data
    assert (legit["kind"] == "legit").all() and legit["attack_type"].isna().all()
    assert (attacks["kind"] == "attack").all()
    assert set(attacks["attack_type"]) == set(ATTACK_TYPES)


def test_sizes(data):
    legit, attacks = data
    assert len(legit) == 30_000
    assert (attacks["attack_type"].value_counts() == 300).all()


def test_genuine_marginals(data):
    legit, _ = data
    n = len(legit)
    for col, p in [("new_device", 0.02), ("new_payee", 0.12), ("velocity", 0.03),
                   ("far_location", 0.03)]:
        assert abs(legit[col].mean() - p) < 0.01, col
    net = legit["network"].value_counts(normalize=True)
    assert abs(net["home"] - 0.45) < 0.02 and abs(net["mobile"] - 0.50) < 0.02
    assert abs(net["public"] - 0.05) < 0.01
    fri = legit["fri"].value_counts(normalize=True)
    assert abs(fri[0] - 0.975) < 0.01 and abs(fri[1] - 0.020) < 0.005
    assert abs((legit["ratio"] > 10).mean() - 0.03) < 0.01  # big one-offs; normal ratios stay < 10
    assert legit["median"].between(60, 5000).all()
    assert n == len(legit)


def test_attack_marginals_follow_config(data):
    _, attacks = data
    for t in ATTACK_TYPES:
        A, sub = CFG.attacks[t], attacks[attacks["attack_type"] == t]
        assert abs(sub["new_device"].mean() - A.new_device) < 0.06, t
        assert abs(sub["new_payee"].mean() - A.new_payee) < 0.06, t
        assert abs(sub["velocity"].mean() - A.velocity) < 0.08, t
        assert abs(sub["far_location"].mean() - A.far_location) < 0.08, t
        assert (sub["ratio"] >= 1.2 - 1e-9).all()


def test_coverage_filters_observed_signals():
    cfg = with_overrides(CFG, {"attacks": {"simswap": {"sim_change": 1.0}},
                               "sizes": {"attacks_per_type": 4000}})
    _, attacks = generate(cfg, 2)
    sim = attacks[attacks["attack_type"] == "simswap"]["sim_change"].mean()
    assert abs(sim - CFG.generator.coverage.sim_feed) < 0.02  # observed only 90% of the time
    cfg0 = with_overrides(cfg, {"generator": {"coverage": {"sim_feed": 0.0, "remote": 0.0}}})
    legit, attacks = generate(cfg0, 2)
    assert not attacks["sim_change"].any() and not attacks["remote"].any()
    assert not legit["sim_change"].any() and not legit["remote"].any()


def test_same_seed_same_data_different_seed_differs():
    a, b = generate(CFG, 5), generate(CFG, 5)
    assert a[0].equals(b[0]) and a[1].equals(b[1])
    c = generate(CFG, 6)
    assert not a[0].equals(c[0]) and not a[1].equals(c[1])


def test_evasive_mode_and_pairing():
    ev_cfg = with_overrides(CFG, {"generator": {"evasive": True}})
    l0, a0 = generate(CFG, 3)
    l1, a1 = generate(ev_cfg, 3)
    assert l0.equals(l1)                                   # genuine payments untouched
    assert not a1["velocity"].any()                        # velocity hidden
    assert (a1["network"] != "public").all()               # public network avoided
    assert abs((a1["fri"] == 0).mean() - ((a0["fri"] == 0).mean() * 0.15 + 0.85)) < 0.03
    assert abs((a1["ratio"] < 2).mean() - 0.60) < 0.07     # about 60% look like a normal amount
    # paired: signals the evasion does not touch are identical, and `u` is shared
    for col in ("median", "new_device", "new_payee", "sim_change", "remote", "far_location", "u"):
        assert a0[col].equals(a1[col]), col


def test_immutable_lists_match_the_guide():
    want = {"simswap": ["sim_change"], "screenshare": ["remote"], "collect": ["new_payee"],
            "replay": [], "stolen": ["new_payee"]}
    for t, imm in want.items():
        assert immutable_signals(CFG, t) == imm

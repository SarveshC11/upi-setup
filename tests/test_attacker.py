"""Learned attacker tests (owner: Person 1)."""
import numpy as np
import pytest

from common.config import load_config, with_overrides
from policy.engine import make_engine
from sim.attacker import (
    IDENTITY,
    PARAMS,
    _Budget,
    attack_batch,
    held_out_curve,
    learn_attacker,
    learn_shared,
    mutable_mask,
    optimise,
    outcome,
    spec_from_theta,
    worst_case_curve,
)
from sim.attacks import ATTACK_TYPES, attack_spec, immutable_signals

# CI installs without the optional `cma` package; the built-in fallback is expected there.
pytestmark = pytest.mark.filterwarnings("ignore:cma is not installed")

CFG = with_overrides(load_config(), {"sizes": {"users": 200, "legit_per_user": 10,
                                               "attacks_per_type": 100}})
SEEDS = [1, 2]


@pytest.mark.parametrize("t", ATTACK_TYPES)
def test_identity_theta_is_the_hand_written_attack(t):
    spec, base = spec_from_theta(CFG, t, IDENTITY), attack_spec(CFG, t)
    for k in ("new_device", "new_payee", "median_multiple", "sigma", "velocity", "sim_change",
              "remote", "far_location", "fri_evasion"):
        assert spec[k] == pytest.approx(base[k]), k
    for k in base["network"]:
        assert spec["network"][k] == pytest.approx(base["network"][k]), k


@pytest.mark.parametrize("t", ATTACK_TYPES)
def test_each_attacker_has_6_to_10_adjustable_parameters(t):
    assert 6 <= mutable_mask(CFG, t).sum() <= len(PARAMS) == 10


@pytest.mark.parametrize("t", ATTACK_TYPES)
def test_immutable_signals_never_move(t):
    rng = np.random.default_rng(0)
    base = attack_spec(CFG, t)
    for _ in range(50):
        spec = spec_from_theta(CFG, t, rng.random(len(PARAMS)))
        for sig in immutable_signals(CFG, t):
            assert spec[sig] == pytest.approx(base[sig]), (t, sig)
        assert sum(spec["network"].values()) == pytest.approx(1.0)
        assert all(v >= -1e-12 for v in spec["network"].values())
        assert 0 <= spec["fri_evasion"] <= 1


def test_attacker_cannot_invent_signals_the_attack_never_uses():
    spec = spec_from_theta(CFG, "screenshare", np.ones(len(PARAMS)))
    assert spec["sim_change"] == 0.0            # screenshare never involves a SIM change
    assert spec["network"]["public"] == 0.0     # nor a public network
    assert spec["remote"] == pytest.approx(CFG.attacks.screenshare.remote)  # immutable


def test_batch_is_reproducible_and_capped():
    spec = attack_spec(CFG, "simswap")
    a, b = attack_batch(CFG, "simswap", spec, 1), attack_batch(CFG, "simswap", spec, 1)
    assert a.equals(b) and not a.equals(attack_batch(CFG, "simswap", spec, 2))
    big = dict(spec, median_multiple=150.0)
    assert attack_batch(CFG, "simswap", big, 1)["amount"].max() <= CFG.attacker.max_amount


def test_budget_is_enforced():
    b = _Budget(lambda x: 1.0, 3)
    for _ in range(3):
        b(IDENTITY)
    with pytest.raises(RuntimeError):
        b(IDENTITY)


@pytest.mark.parametrize("opt", ["cma", "es"])
def test_optimiser_respects_budget_and_finds_a_better_point(opt):
    target = np.full(len(PARAMS), 0.8)
    f = lambda th: -float(np.sum((th - target) ** 2))  # noqa: E731
    res = optimise(f, np.ones(len(PARAMS), bool), tries=100, random_frac=0.3, optimizer=opt, seed=0)
    assert res["tries_used"] <= 100
    assert res["train_lost"] > f(IDENTITY)
    assert len(res["history"]) == res["tries_used"]
    assert all(
        b >= a for a, b in zip(res["history"], res["history"][1:], strict=False)
    )  # best-so-far


def test_learned_attacker_is_never_worse_than_hand_written_on_training_seeds():
    d = 0
    res = learn_attacker(CFG, "stolen", d, tries=40, train_seeds=SEEDS)
    policy = make_engine(CFG.policy["weights"], d)
    hand = outcome(CFG, policy, "stolen", attack_spec(CFG, "stolen"), SEEDS)["lost"]
    assert res["tries_used"] <= 40
    assert res["train_lost"] >= hand - 1e-6
    assert outcome(CFG, policy, "stolen", res["spec"], SEEDS)["lost"] == pytest.approx(
        res["train_lost"])


def test_learned_attacker_beats_hand_written_when_policy_is_strict():
    res = learn_attacker(CFG, "replay", -15, tries=60, train_seeds=SEEDS)
    policy = make_engine(CFG.policy["weights"], -15)
    hand = outcome(CFG, policy, "replay", attack_spec(CFG, "replay"), SEEDS)["lost"]
    assert res["train_lost"] > hand


def test_shared_strategy_and_reports_have_expected_shape():
    res = learn_shared(CFG, 0, ["simswap", "replay"], tries=30, train_seeds=SEEDS)
    assert res["theta"].shape == (len(PARAMS),) and res["tries_used"] <= 30
    kw = {"tries": 20, "train_seeds": SEEDS, "test_seeds": [101]}
    rows = worst_case_curve(CFG, shifts=[0], **kw)
    assert len(rows) == 1 and set(rows[0]["per_type"]) == set(ATTACK_TYPES)
    for k in ("shift", "friction", "hand_prevented", "evasive_prevented", "learned_prevented",
              "beats_evasive_pp"):
        assert k in rows[0]
    held = held_out_curve(CFG, shifts=[0], held_out="collect", **kw)
    assert held[0]["held_out"] == "collect" and "transfer_prevented" in held[0]
    with pytest.raises(ValueError):
        held_out_curve(CFG, shifts=[0], held_out="nope", **kw)


def test_falls_back_to_evolution_strategy_without_cma(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "cma", None)  # makes `import cma` raise ImportError
    f = lambda th: -float(np.sum((th - 0.7) ** 2))  # noqa: E731
    with pytest.warns(UserWarning, match="cma is not installed"):
        res = optimise(f, np.ones(len(PARAMS), bool), tries=60, random_frac=0.3, optimizer="cma",
                       seed=0)
    assert res["tries_used"] <= 60 and res["train_lost"] > f(IDENTITY)

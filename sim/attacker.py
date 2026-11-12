"""Learned attacker (owner: Person 1).

A search-based attacker that tries to get the most money past the policy.

Each attack type is described by up to 10 adjustable parameters in [0, 1] (see PARAMS). A vector
`theta` is turned into an attack spec by `spec_from_theta`; signals in the attack's `immutable`
list never move. The reward is the rupees that get through the policy, measured with the shared
`eval.metrics.evaluate` so the attacker and the experiment pipeline use the same rules.

Search: random search first (the hand-written attack, theta = IDENTITY, is always tried), then
CMA-ES (`cma` package) or, if `cma` is missing, a small (1+lambda) evolution strategy. Each attacker
has a hard budget of `tries` probes of the policy.

Protocol: tune on `attacker.train_seeds`, report on `attacker.test_seeds`. A shared strategy trained
on four attack types is tested on the fifth, held-out type.

Entry points for Person 3: `worst_case_curve` and `held_out_curve`.
    python -m sim.attacker --out results/attacker [--quick]
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from eval.metrics import evaluate
from policy.engine import make_engine
from sim.attacks import ATTACK_TYPES, attack_spec, generate_attack_type, immutable_signals
from sim.generate import generate, user_medians
from sim.rng import make_rng, make_side_rng

PARAMS = ("mu", "sigma", "velocity", "far_location", "net_public", "net_mobile",
          "fri_evasion", "new_device", "new_payee", "sim_remote")
_I = {p: i for i, p in enumerate(PARAMS)}
# theta that reproduces the hand-written attack. Most parameters are centred at 0.5;
# fri_evasion is a plain probability that starts at 0.
IDENTITY = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.0, 0.5, 0.5, 0.5])

# which signals each parameter controls; a parameter is frozen when all of them are immutable
_CONTROLS = {
    "mu": ["amount"], "sigma": ["amount"],
    "velocity": ["velocity"], "far_location": ["far_location"],
    "net_public": ["network"], "net_mobile": ["network"],
    "fri_evasion": ["fri"], "new_device": ["new_device"], "new_payee": ["new_payee"],
    "sim_remote": ["sim_change", "remote"],
}
MU_MAX_MULTIPLE = 150.0  # the guide's largest genuine one-off ratio
_SALT_BATCH, _SALT_EV = 17, 18


def _prob(base: float, th: float) -> float:
    """Piecewise-linear: th=0 gives 0, th=0.5 gives `base`, th=1 gives 1.
    A signal the attack never uses (base 0) stays 0: the attacker cannot invent it."""
    if base <= 0.0:
        return 0.0
    return base * 2 * th if th <= 0.5 else base + (1 - base) * (2 * th - 1)


def mutable_mask(cfg, attack_type: str) -> np.ndarray:
    """True for each parameter the attacker may change for this attack type."""
    imm = set(immutable_signals(cfg, attack_type))
    base = attack_spec(cfg, attack_type)
    mask = np.ones(len(PARAMS), dtype=bool)
    for p, signals in _CONTROLS.items():
        free = [s for s in signals if s not in imm]
        if p == "sim_remote":
            free = [s for s in free if base[s] > 0]  # nothing to hide if the attack never shows it
        mask[_I[p]] = bool(free)
    return mask


def spec_from_theta(cfg, attack_type: str, theta) -> dict:
    """Turn a parameter vector into an attack spec. Immutable signals keep their base value."""
    th = np.where(mutable_mask(cfg, attack_type), np.asarray(theta, dtype=float), IDENTITY)
    th = np.clip(th, 0.0, 1.0)
    imm = set(immutable_signals(cfg, attack_type))
    spec = attack_spec(cfg, attack_type)
    base = attack_spec(cfg, attack_type)

    spec["median_multiple"] = float(np.clip(
        base["median_multiple"] * 8.0 ** ((th[_I["mu"]] - 0.5) * 2), 1.2, MU_MAX_MULTIPLE))
    spec["sigma"] = float(np.clip(
        base["sigma"] * 2.0 ** ((th[_I["sigma"]] - 0.5) * 2), 0.05, 1.5))
    for key in ("velocity", "far_location", "new_device", "new_payee"):
        spec[key] = _prob(base[key], th[_I[key]])
    if "sim_change" not in imm:
        spec["sim_change"] = _prob(base["sim_change"], th[_I["sim_remote"]])
    if "remote" not in imm:
        spec["remote"] = _prob(base["remote"], th[_I["sim_remote"]])

    pub = _prob(base["network"]["public"], th[_I["net_public"]])
    mob0, home0 = base["network"]["mobile"], base["network"]["home"]
    frac0 = mob0 / (mob0 + home0) if mob0 + home0 > 0 else 0.0
    mobile = (1.0 - pub) * _prob(frac0, th[_I["net_mobile"]])
    spec["network"] = {"home": 1.0 - pub - mobile, "mobile": mobile, "public": pub}
    spec["fri_evasion"] = float(th[_I["fri_evasion"]])
    return spec


def _legit_stub() -> pd.DataFrame:
    """One genuine row. evaluate() wants a legit table; the attacker only reads attack metrics."""
    return pd.DataFrame([{
        "kind": "legit", "attack_type": None, "median": 400, "ratio": 1.0, "amount": 400,
        "new_device": False, "network": "home", "new_payee": False, "velocity": False,
        "sim_change": False, "remote": False, "far_location": False, "fri": 0, "u": 0.5,
    }])


def attack_batch(cfg, attack_type: str, spec: dict, seed: int, n: int | None = None,
                 evasive: bool = False) -> pd.DataFrame:
    """`n` attacks of one type from `spec`. Same (seed, type) gives the same random numbers for
    every spec, so two specs are compared on identical luck. Amounts are capped at
    cfg.attacker.max_amount (this cap is not applied inside generate())."""
    n = n or cfg.sizes.attacks_per_type
    ti = ATTACK_TYPES.index(attack_type)
    rng = make_side_rng(seed, _SALT_BATCH, ti)
    ev = make_side_rng(seed, _SALT_EV, ti)
    medians = user_medians(cfg, make_rng(seed))
    ep = cfg.generator.evasive_params if evasive else None
    df = generate_attack_type(attack_type, spec, medians, n, rng, ev, cfg.generator.coverage, ep)
    df["u"] = rng.random(n)
    # a real attacker cannot move more than the per-payment limit; applied to every attacker alike
    df["ratio"] = np.minimum(df["ratio"], cfg.attacker.max_amount / df["median"])
    df["amount"] = np.maximum(1, np.rint(df["median"] * df["ratio"])).astype(int)
    return df


def outcome(cfg, policy, attack_type, spec, seeds, evasive=False) -> dict:
    """Mean over seeds of rupees attempted and rupees that got through the policy."""
    stub, lost, total = _legit_stub(), 0.0, 0.0
    for s in seeds:
        m = evaluate(policy, stub, attack_batch(cfg, attack_type, spec, s, evasive=evasive),
                     cfg.costs)
        lost += m["lost"]
        total += m["total"]
    k = len(seeds)
    return {"lost": lost / k, "total": total / k}


# --------------------------------------------------------------------------- optimisers

class _Budget:
    """Counts probes of the policy and refuses to go over `tries`."""

    def __init__(self, f, tries):
        self.f, self.tries, self.used, self.best, self.best_x = f, tries, 0, -np.inf, None
        self.history: list[float] = []

    def __call__(self, x):
        if self.used >= self.tries:
            raise RuntimeError("attacker probe budget exceeded")
        self.used += 1
        v = float(self.f(x))
        if v > self.best:
            self.best, self.best_x = v, np.array(x, dtype=float)
        self.history.append(self.best)
        return v

    @property
    def left(self):
        return self.tries - self.used


def _evolution_strategy(obj, x0, free, rng, sigma=0.2, lam=8):
    """Evolution strategy with a 1/5-style step-size rule."""
    x, fx = x0.copy(), obj.best
    while obj.left >= lam:
        cands = []
        for _ in range(lam):
            c = x.copy()
            c[free] = np.clip(x[free] + sigma * rng.standard_normal(free.sum()), 0, 1)
            cands.append(c)
        vals = [obj(c) for c in cands]
        i = int(np.argmax(vals))
        if vals[i] > fx:
            x, fx, sigma = cands[i], vals[i], min(sigma * 1.5, 0.5)
        else:
            sigma = max(sigma * 0.8, 0.01)


def _cma(obj, x0, free, seed, sigma=0.2):
    import cma

    es = cma.CMAEvolutionStrategy(
        x0[free].tolist(), sigma,
        {"bounds": [0, 1], "seed": seed + 1, "verbose": -9, "popsize": 8})
    while obj.left >= es.popsize and not es.stop():
        xs = es.ask()
        losses = []
        for z in xs:
            full = x0.copy()
            full[free] = np.clip(z, 0, 1)
            losses.append(-obj(full))
        es.tell(xs, losses)


def optimise(f, free, tries, random_frac, optimizer, seed) -> dict:
    """Maximise f(theta) over theta in [0,1]^10 with at most `tries` calls of f.
    Only the entries where `free` is True move; the rest stay at IDENTITY."""
    free = np.asarray(free, dtype=bool)
    rng = make_side_rng(seed, 99)
    obj = _Budget(f, tries)
    obj(IDENTITY)  # the hand-written attack is always a candidate, so the result is never worse
    for _ in range(max(0, int(tries * random_frac) - 1)):
        th = IDENTITY.copy()
        th[free] = rng.random(free.sum())
        obj(th)
    if free.any():
        if optimizer == "cma":
            try:
                _cma(obj, obj.best_x, free, seed)
            except ImportError:
                warnings.warn(
                    "cma is not installed (pip install -e '.[opt]'); using the built-in "
                    "evolution strategy, so attacker numbers will differ from CMA-ES runs",
                    stacklevel=2,
                )
                _evolution_strategy(obj, obj.best_x, free, rng)
        else:
            _evolution_strategy(obj, obj.best_x, free, rng)
    return {"theta": obj.best_x, "train_lost": obj.best, "tries_used": obj.used,
            "history": obj.history}


# --------------------------------------------------------------------------- learning

def _policy(cfg, weights, shift):
    return make_engine(weights if weights is not None else cfg.policy["weights"], shift)


def learn_attacker(cfg, attack_type, shift, weights=None, tries=None, train_seeds=None,
                   optimizer=None, seed=None) -> dict:
    """Learn the best parameters for one attack type against the policy at `shift`."""
    a = cfg.attacker
    policy = _policy(cfg, weights, shift)
    train = list(train_seeds or a.train_seeds)

    def reward(theta):
        return outcome(cfg, policy, attack_type, spec_from_theta(cfg, attack_type, theta),
                       train)["lost"]

    res = optimise(reward, mutable_mask(cfg, attack_type), tries or a.tries, a.random_frac,
                   optimizer or a.optimizer, a.rng_seed if seed is None else seed)
    res["spec"] = spec_from_theta(cfg, attack_type, res["theta"])
    return res


def learn_shared(cfg, shift, train_types, weights=None, tries=None, train_seeds=None,
                 optimizer=None, seed=None) -> dict:
    """One strategy shared by several attack types (used for the held-out attack type test).
    The same theta is applied to each type's own base attack, respecting its immutable signals."""
    a = cfg.attacker
    policy = _policy(cfg, weights, shift)
    train = list(train_seeds or a.train_seeds)

    # each type counts equally: its loss is measured relative to the hand-written attack, so the
    # big-money types (simswap, replay) cannot dominate what the shared strategy learns
    ref = {t: max(1.0, outcome(cfg, policy, t, attack_spec(cfg, t), train)["lost"])
           for t in train_types}

    def reward(theta):
        return sum(outcome(cfg, policy, t, spec_from_theta(cfg, t, theta), train)["lost"] / ref[t]
                   for t in train_types)

    return optimise(reward, np.ones(len(PARAMS), dtype=bool), tries or a.tries, a.random_frac,
                    optimizer or a.optimizer, a.rng_seed if seed is None else seed)


# --------------------------------------------------------------------------- reporting

def _agg(parts: list[dict]) -> dict:
    lost = sum(p["lost"] for p in parts)
    total = sum(p["total"] for p in parts)
    return {"lost": lost, "total": total, "prevented": (1 - lost / total) * 100 if total else 0.0}


def _friction(cfg, policy, test_seeds) -> float:
    vals = [evaluate(policy, *generate(cfg, s), cfg.costs)["friction"] for s in test_seeds]
    return float(np.mean(vals))


def worst_case_curve(cfg, weights=None, shifts=None, tries=None, test_seeds=None,
                     train_seeds=None, optimizer=None, types=None, log=None) -> list[dict]:
    """Worst-case fraud loss at each strictness shift. One row per shift:

      shift, friction            engine friction per 1,000 genuine payments (test seeds)
      hand_prevented             hand-written attacks, % of attacked rupees stopped
      evasive_prevented          hand-written evasive variant
      learned_prevented          learned attacker, measured on the unseen test seeds
      hand_lost, evasive_lost, learned_lost    rupees that got through, per seed, all types
      beats_evasive_pp           evasive_prevented - learned_prevented
                                 (positive: learned is stronger)
      per_type                   the same numbers for each attack type
    """
    a = cfg.attacker
    st = a.shifts
    shifts = list(shifts) if shifts is not None else list(range(st.start, st.stop + 1, st.step))
    test = list(test_seeds or a.test_seeds)
    types = list(types or ATTACK_TYPES)
    rows = []
    for d in shifts:
        policy = _policy(cfg, weights, d)
        per, hand, evas, learned = {}, [], [], []
        for t in types:
            res = learn_attacker(cfg, t, d, weights, tries, train_seeds, optimizer)
            h = outcome(cfg, policy, t, attack_spec(cfg, t), test)
            e = outcome(cfg, policy, t, attack_spec(cfg, t), test, evasive=True)
            lr = outcome(cfg, policy, t, res["spec"], test)
            hand.append(h), evas.append(e), learned.append(lr)
            per[t] = {"hand": _agg([h]), "evasive": _agg([e]), "learned": _agg([lr]),
                      "tries_used": res["tries_used"]}
        H, E, L = _agg(hand), _agg(evas), _agg(learned)
        rows.append({
            "shift": d, "friction": _friction(cfg, policy, test),
            "hand_prevented": H["prevented"], "evasive_prevented": E["prevented"],
            "learned_prevented": L["prevented"],
            "hand_lost": H["lost"], "evasive_lost": E["lost"], "learned_lost": L["lost"],
            "beats_evasive_pp": E["prevented"] - L["prevented"], "per_type": per,
        })
        if log:
            log(f"shift {d:+d}: prevented hand {H['prevented']:.1f}%  evasive "
                f"{E['prevented']:.1f}%  learned {L['prevented']:.1f}%")
    return rows


def held_out_curve(cfg, weights=None, shifts=None, held_out=None, tries=None, test_seeds=None,
                   train_seeds=None, optimizer=None, log=None) -> list[dict]:
    """Train on four attack types and test on the fifth unseen type.

    One row per shift contains prevented percentages for the held-out type.
    """
    a = cfg.attacker
    st = a.shifts
    shifts = list(shifts) if shifts is not None else list(range(st.start, st.stop + 1, st.step))
    held = held_out or a.held_out
    if held not in ATTACK_TYPES:
        raise ValueError(f"unknown attack type: {held}")
    train_types = [t for t in ATTACK_TYPES if t != held]
    test = list(test_seeds or a.test_seeds)
    rows = []
    for d in shifts:
        policy = _policy(cfg, weights, d)
        res = learn_shared(cfg, d, train_types, weights, tries, train_seeds, optimizer)
        h = _agg([outcome(cfg, policy, held, attack_spec(cfg, held), test)])
        e = _agg([outcome(cfg, policy, held, attack_spec(cfg, held), test, evasive=True)])
        x = _agg([outcome(cfg, policy, held, spec_from_theta(cfg, held, res["theta"]), test)])
        rows.append({"shift": d, "held_out": held, "hand_prevented": h["prevented"],
                     "evasive_prevented": e["prevented"], "transfer_prevented": x["prevented"],
                     "transfer_lost": x["lost"], "hand_lost": h["lost"], "evasive_lost": e["lost"]})
        if log:
            log(f"shift {d:+d} held-out {held}: hand {h['prevented']:.1f}%  evasive "
                f"{e['prevented']:.1f}%  transfer {x['prevented']:.1f}%")
    return rows


def main(argv=None):
    from common.config import load_config, with_overrides

    ap = argparse.ArgumentParser(description="Learned attacker: worst-case loss per strictness.")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default="results/attacker")
    ap.add_argument("--quick", action="store_true", help="few shifts, small budget, smoke test")
    ap.add_argument("--tries", type=int, default=None)
    ap.add_argument("--held-out", default=None, choices=ATTACK_TYPES)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    shifts, tries, kw = None, args.tries, {}
    if args.quick:
        cfg = with_overrides(cfg, {"sizes": {"users": 200, "legit_per_user": 10,
                                             "attacks_per_type": 100}})
        shifts, tries = [-15, 0, 15], tries or 30
        kw = {"test_seeds": [101, 102], "train_seeds": [1, 2]}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = print
    curve = worst_case_curve(cfg, shifts=shifts, tries=tries, log=log, **kw)
    flat = pd.DataFrame([{k: v for k, v in r.items() if k != "per_type"} for r in curve])
    flat.to_csv(out / "worst_case.csv", index=False)
    pt = pd.DataFrame([{"shift": r["shift"], "attack_type": t, "attacker": k, **v}
                       for r in curve for t, d in r["per_type"].items()
                       for k, v in d.items() if isinstance(v, dict)])
    pt.to_csv(out / "worst_case_per_type.csv", index=False)
    held = held_out_curve(cfg, shifts=shifts, held_out=args.held_out, tries=tries, log=log, **kw)
    pd.DataFrame(held).to_csv(out / "held_out.csv", index=False)
    print(f"Wrote {out}/worst_case.csv, worst_case_per_type.csv, held_out.csv")


if __name__ == "__main__":
    main()

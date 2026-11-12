"""Weight and threshold calibration (owner: Person 2).

Replaces hand-picked weights with a multi-objective search. The policy stays a plain points table.

Variables   13 weights (integers 0..100) + 3 tier thresholds (t1 < t2 < t3, integers 1..100).
Objectives  maximise fraud value stopped (% of rupees), minimise friction per 1,000 genuine.
Method      random search to seed the population, then NSGA-II. The whole Pareto set is reported.
Protocol    tune on cfg.seeds.tune, report on cfg.seeds.report (never tuned on), and drop one
            attack type from the tuning data ("held out"), then report on it.

    python -m policy.calibrate --holdout collect --out results/calibration
    python -m policy.calibrate --quick --out results/calibration_quick     # smoke test

Writes (in --out): pareto_tune.csv, pareto_report.csv, hand_curve_report.csv, holdout.csv,
selected.json. Also writes configs/calibrated.yaml (override with --yaml).

Selection rule for the single config we ship: among Pareto points whose TUNE friction does not
exceed the hand-picked default's TUNE friction, take the one that stops the most fraud. That is
"same annoyance, more fraud stopped", a fair comparison with the hand-picked policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.config import load_config, with_overrides
from eval.metrics import evaluate
from policy.engine import SIGNAL_GROUPS, make_engine
from sim.attacks import ATTACK_TYPES
from sim.generate import generate

KEYS = [k for keys in SIGNAL_GROUPS.values() for k in keys]  # the 13 weight keys, fixed order
N_W = len(KEYS)
N_GENES = N_W + 3


# ----------------------------------------------------------------------------------------------
# Genome <-> policy
# ----------------------------------------------------------------------------------------------
def decode(g) -> tuple[dict, tuple[int, int, int]]:
    """Genome (16 ints) -> (weights dict, thresholds). Thresholds are sorted and made strictly
    increasing so that tiers 1 < 2 < 3 always exist."""
    g = np.asarray(g, dtype=int)
    w = {k: int(np.clip(g[i], 0, 100)) for i, k in enumerate(KEYS)}
    t = sorted(int(np.clip(x, 1, 100)) for x in g[N_W:])
    t[1] = max(t[1], t[0] + 1)
    t[2] = max(t[2], t[1] + 1)
    return w, (t[0], t[1], min(t[2], 100))


def encode(weights: dict, thresholds) -> np.ndarray:
    return np.array([weights[k] for k in KEYS] + list(thresholds), dtype=int)


def policy_from_genome(g):
    w, th = decode(g)
    return make_engine(w, 0, th)


# ----------------------------------------------------------------------------------------------
# Objective evaluation (uses the shared evaluate(), so numbers match Person 3's pipeline)
# ----------------------------------------------------------------------------------------------
class Problem:
    def __init__(self, cfg, seeds, holdout: str | None = None, evasive_modes=(False,)):
        """`evasive_modes` lists the attacker variants to tune on. (False,) is the normal attacker;
        (False, True) is robust mode: objectives are averaged over normal and evasive attackers."""
        self.costs = cfg.costs
        self.holdout = holdout
        self.data = []
        for ev in evasive_modes:
            cfg_v = with_overrides(cfg, {"generator": {"evasive": ev}})
            for s in seeds:
                legit, attacks = generate(cfg_v, s)
                if holdout is not None:
                    attacks = attacks[attacks["attack_type"] != holdout]
                self.data.append((legit, attacks))
        self.cache: dict[tuple, tuple[float, float]] = {}
        self.evals = 0

    def objectives(self, g) -> tuple[float, float]:
        """Returns (prevented %, friction per 1,000), averaged over the seeds."""
        w, th = decode(g)
        key = tuple(w[k] for k in KEYS) + th  # cache on the decoded policy, not raw genes
        if key not in self.cache:
            pol = make_engine(w, 0, th)
            ms = [evaluate(pol, lg, at, self.costs) for lg, at in self.data]
            self.cache[key] = (float(np.mean([m["prevented"] for m in ms])),
                               float(np.mean([m["friction"] for m in ms])))
            self.evals += 1
        return self.cache[key]

    def min_objectives(self, g) -> tuple[float, float]:
        p, f = self.objectives(g)
        return (-p, f)  # both to be minimised


# ----------------------------------------------------------------------------------------------
# NSGA-II building blocks (two objectives, both minimised)
# ----------------------------------------------------------------------------------------------
def dominates(a, b) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and (a[0] < b[0] or a[1] < b[1])


def fast_nondominated_sort(F: np.ndarray) -> list[list[int]]:
    n = len(F)
    S = [[] for _ in range(n)]
    cnt = np.zeros(n, dtype=int)
    fronts: list[list[int]] = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(F[p], F[q]):
                S[p].append(q)
            elif dominates(F[q], F[p]):
                cnt[p] += 1
        if cnt[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                cnt[q] -= 1
                if cnt[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def crowding_distance(F: np.ndarray, front: list[int]) -> dict[int, float]:
    if len(front) <= 2:
        return {i: np.inf for i in front}
    d = {i: 0.0 for i in front}
    for m in range(F.shape[1]):
        order = sorted(front, key=lambda i: F[i, m])
        d[order[0]] = d[order[-1]] = np.inf
        span = F[order[-1], m] - F[order[0], m]
        if span == 0:
            continue
        for k in range(1, len(order) - 1):
            d[order[k]] += (F[order[k + 1], m] - F[order[k - 1], m]) / span
    return d


def _rank_and_crowd(F: np.ndarray):
    rank = np.zeros(len(F), dtype=int)
    crowd = np.zeros(len(F))
    fronts = fast_nondominated_sort(F)
    for r, fr in enumerate(fronts):
        cd = crowding_distance(F, fr)
        for i in fr:
            rank[i] = r
            crowd[i] = cd[i]
    return rank, crowd, fronts


def _tournament(rng, rank, crowd) -> int:
    a, b = rng.integers(0, len(rank), 2)
    if rank[a] != rank[b]:
        return int(a if rank[a] < rank[b] else b)
    return int(a if crowd[a] >= crowd[b] else b)


def crossover_mutate(rng, p1, p2, p_mut: float, step: float) -> np.ndarray:
    """Uniform crossover with some blending, then integer gaussian mutation."""
    mask = rng.random(N_GENES) < 0.5
    child = np.where(mask, p1, p2).astype(float)
    blend = rng.random(N_GENES) < 0.3
    child[blend] = (p1[blend] + p2[blend]) / 2
    mut = rng.random(N_GENES) < p_mut
    child[mut] += rng.normal(0, step, mut.sum())
    return np.clip(np.rint(child), 0, 100).astype(int)


def random_genomes(rng, n: int) -> np.ndarray:
    g = rng.integers(0, 101, size=(n, N_GENES))
    sparse = rng.random((n, N_W)) < 0.25  # real policies leave some signals at zero
    g[:, :N_W][sparse] = 0
    g[:, N_W:] = np.sort(rng.integers(5, 95, size=(n, 3)), axis=1)
    return g


def nsga2(problem: Problem, init: np.ndarray, pop_size: int, generations: int, seed: int,
          log=print) -> np.ndarray:
    rng = np.random.default_rng(seed)
    P = np.array(list(init)[:pop_size])
    if len(P) < pop_size:
        P = np.vstack([P, random_genomes(rng, pop_size - len(P))])
    F = np.array([problem.min_objectives(g) for g in P])
    for gen in range(generations):
        rank, crowd, _ = _rank_and_crowd(F)
        kids = []
        while len(kids) < pop_size:
            i, j = _tournament(rng, rank, crowd), _tournament(rng, rank, crowd)
            kids.append(crossover_mutate(rng, P[i], P[j], p_mut=0.15, step=8.0))
        K = np.array(kids)
        FK = np.array([problem.min_objectives(g) for g in K])
        R, FR = np.vstack([P, K]), np.vstack([F, FK])
        _, _, fronts = _rank_and_crowd(FR)
        keep: list[int] = []
        for fr in fronts:
            if len(keep) + len(fr) <= pop_size:
                keep += fr
            else:
                cd = crowding_distance(FR, fr)
                keep += sorted(fr, key=lambda i: -cd[i])[: pop_size - len(keep)]
                break
        P, F = R[keep], FR[keep]
        if (gen + 1) % 10 == 0 or gen == generations - 1:
            log(f"  generation {gen + 1}/{generations}: pareto size "
                f"{len(fast_nondominated_sort(F)[0])}, {problem.evals} unique evaluations")
    return P[fast_nondominated_sort(F)[0]]


# ----------------------------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------------------------
def pareto_table(problem: Problem, genomes: np.ndarray) -> pd.DataFrame:
    rows = []
    for g in genomes:
        w, th = decode(g)
        p, f = problem.objectives(g)
        rows.append({"prevented": p, "friction": f, "t1": th[0], "t2": th[1], "t3": th[2], **w})
    return pd.DataFrame(rows).drop_duplicates().sort_values("friction").reset_index(drop=True)


def nondominated(df: pd.DataFrame) -> pd.DataFrame:
    vals = df[["prevented", "friction"]].to_numpy()
    keep = [i for i, (p, f) in enumerate(vals)
            if not any(q >= p and h <= f and (q > p or h < f)
                       for j, (q, h) in enumerate(vals) if j != i)]
    return df.iloc[keep].sort_values("friction").reset_index(drop=True)


def select_point(front: pd.DataFrame, friction_budget: float) -> pd.Series:
    """Most fraud stopped among points that do not exceed the friction budget."""
    ok = front[front["friction"] <= friction_budget + 1e-9]
    pool = ok if len(ok) else front
    return pool.sort_values(["prevented", "friction"], ascending=[False, True]).iloc[0]


def row_to_policy(r: pd.Series):
    w = {k: int(r[k]) for k in KEYS}
    th = (int(r["t1"]), int(r["t2"]), int(r["t3"]))
    return make_engine(w, 0, th), w, th


def report_on(cfg, seeds, policies: dict, holdout: str | None,
              evasive: bool = False) -> pd.DataFrame:
    """Mean over seeds of prevented and friction for each named policy, overall and (if given)
    on the held-out attack type alone. Also reports the share of attacks stopped (by count)
    per type, because the rupee-weighted number can hide a policy that only catches big amounts."""
    cfg = with_overrides(cfg, {"generator": {"evasive": evasive}})
    data = [generate(cfg, s) for s in seeds]
    out = []
    for name, pol in policies.items():
        allm = [evaluate(pol, lg, at, cfg.costs) for lg, at in data]
        row = {"policy": name,
               "prevented": float(np.mean([m["prevented"] for m in allm])),
               "friction": float(np.mean([m["friction"] for m in allm])),
               "extra": float(np.mean([m["extra"] for m in allm]))}
        for t in ATTACK_TYPES:
            row[f"stopped_{t}"] = float(np.mean([m["per_type"][t]["share"] for m in allm]) * 100)
        if holdout:
            hold = [evaluate(pol, lg, at[at["attack_type"] == holdout], cfg.costs)
                    for lg, at in data]
            row[f"prevented_{holdout}_heldout"] = float(np.mean([m["prevented"] for m in hold]))
        out.append(row)
    return pd.DataFrame(out)


def write_yaml(path: Path, weights: dict, thresholds) -> None:
    doc = {"policy": {"weights": {k: int(v) for k, v in weights.items()},
                      "base_thresholds": [int(t) for t in thresholds], "shift": 0}}
    header = ("# Written by policy/calibrate.py. Load with load_config('configs/calibrated.yaml').\n"
              "# Thresholds are in base_thresholds; shift stays 0 so the slider still works.\n")
    path.write_text(header + yaml.safe_dump(doc, sort_keys=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default="results/calibration")
    ap.add_argument("--yaml", default="configs/calibrated.yaml")
    ap.add_argument("--holdout", default="collect", choices=list(ATTACK_TYPES) + ["none"])
    ap.add_argument("--random", type=int, default=400, help="random-search samples")
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--gens", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0, help="seed for the optimiser itself")
    ap.add_argument("--robust", action="store_true",
                    help="tune on normal AND evasive attackers (objectives averaged)")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    holdout = None if args.holdout == "none" else args.holdout
    tune_seeds, report_seeds = list(cfg.seeds.tune), list(cfg.seeds.report)
    if args.quick:
        tune_seeds, report_seeds = tune_seeds[:2], report_seeds[:2]
        args.random, args.pop, args.gens = 60, 24, 8
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    print(f"tune seeds {tune_seeds}; report seeds {report_seeds}; held-out type: {holdout}")
    prob = Problem(cfg, tune_seeds, holdout, (False, True) if args.robust else (False,))
    hand_w, hand_th = dict(cfg.policy["weights"]), tuple(cfg.policy["base_thresholds"])
    hand = encode(hand_w, hand_th)
    hand_p, hand_f = prob.objectives(hand)
    print(f"hand-picked on tune seeds: prevented {hand_p:.1f}%, friction {hand_f:.0f}")

    # 1. random search; the best of it (plus the hand-picked point) starts the population
    print(f"random search ({args.random} samples) ...")
    rs = np.vstack([hand[None, :], random_genomes(rng, args.random)])
    F = np.array([prob.min_objectives(g) for g in rs])
    order = [i for fr in fast_nondominated_sort(F) for i in fr][: args.pop]
    jitter = np.array([crossover_mutate(rng, hand, hand, 0.4, 6.0) for _ in range(args.pop // 3)])
    init = np.vstack([rs[order], jitter])

    # 2. NSGA-II
    print("NSGA-II ...")
    front = nsga2(prob, init, args.pop, args.gens, args.seed + 1)
    tune_df = nondominated(pareto_table(prob, np.vstack([front, hand[None, :]])))
    tune_df.to_csv(out / "pareto_tune.csv", index=False)

    # 3. choose one config by the same-friction rule; report on seeds never tuned on
    chosen = select_point(tune_df, hand_f)
    cal_pol, cal_w, cal_th = row_to_policy(chosen)
    hand_pol = make_engine(hand_w, 0, hand_th)

    pareto_pols = {f"pareto_{i}": row_to_policy(r)[0] for i, r in tune_df.iterrows()}
    sh = cfg.experiment.shifts
    shifts = list(range(sh.start, sh.stop + 1, sh.step))
    hand_curve_pols = {f"shift_{d}": make_engine(hand_w, d, hand_th) for d in shifts}
    final_pols = {"hand_picked": hand_pol, "calibrated": cal_pol}
    rep_all, curve_all, hold_all = [], [], []
    for variant, ev in (("normal", False), ("evasive", True)):
        rep = report_on(cfg, report_seeds, pareto_pols, holdout, ev)
        rep = pd.concat([tune_df[["t1", "t2", "t3"] + KEYS].reset_index(drop=True), rep], axis=1)
        rep.insert(0, "variant", variant)
        rep_all.append(rep)
        curve = report_on(cfg, report_seeds, hand_curve_pols, holdout, ev)
        curve.insert(1, "shift", shifts)
        curve.insert(0, "variant", variant)
        curve_all.append(curve)
        hold = report_on(cfg, report_seeds, final_pols, holdout, ev)
        hold.insert(0, "variant", variant)
        hold_all.append(hold)
    pd.concat(rep_all).to_csv(out / "pareto_report.csv", index=False)
    pd.concat(curve_all).to_csv(out / "hand_curve_report.csv", index=False)
    hold = pd.concat(hold_all)
    hold.to_csv(out / "holdout.csv", index=False)

    write_yaml(Path(args.yaml), cal_w, cal_th)
    info = {"holdout": holdout, "tune_seeds": tune_seeds, "report_seeds": report_seeds,
            "friction_budget_from_hand_picked_tune": hand_f,
            "calibrated_weights": cal_w, "calibrated_thresholds": list(cal_th),
            "robust": args.robust, "unique_evaluations": prob.evals}
    (out / "selected.json").write_text(json.dumps(info, indent=2))

    pd.set_option("display.width", 200)
    print("\nReport seeds (never tuned on):")
    show = ["variant", "policy", "prevented", "friction", "extra",
            f"prevented_{holdout}_heldout" if holdout else "prevented"]
    print(hold[show].round(1).to_string(index=False))
    print(hold[["variant", "policy"] + [f"stopped_{t}" for t in ATTACK_TYPES]]
          .round(1).to_string(index=False))
    print(f"\nwrote {args.yaml} and tables to {out}/")


if __name__ == "__main__":
    main()

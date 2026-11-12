"""Run the whole experiment from one config (owner: Person 3).

    python -m eval.run_experiment --config configs/default.yaml --out results/default
    python -m eval.run_experiment --config configs/default.yaml --out results/quick --quick

Produces tables (CSV) and figures (PNG) in the output folder. Nothing is made by hand.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import yaml

from baselines import get_baselines
from baselines.ml_baseline import make_ml_engine, train_ml
from common.config import load_config, with_overrides
from eval import plots
from eval.metrics import (
    ablation,
    best_prevented_within,
    evaluate,
    scalar_metrics,
    scale_costs,
    sweep,
)
from policy.engine import make_engine
from sim.generate import generate

ML_NAME = "ml_baseline"


def _mean_std(rows: list[dict], by: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if c not in by and pd.api.types.is_numeric_dtype(df[c])]
    g = df.groupby(by, sort=False)[num].agg(["mean", "std"])
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    return g.fillna(0.0).reset_index()


def _curve_df(rows: list[dict], policy: str) -> pd.DataFrame:
    df = _mean_std([{**scalar_metrics(r), "policy": policy} for r in rows], ["policy", "shift"])
    df["strictness"] = -df["shift"]
    return df.sort_values("shift").reset_index(drop=True)


def run_variant(cfg, seeds, evasive, ml, do_ablation, do_sens, log):
    cfgv = with_overrides(cfg, {"generator": {"evasive": evasive}})
    w, costs = cfg.policy.weights, cfg.costs
    sh = cfg.experiment.shifts
    shifts = list(range(sh.start, sh.stop + 1, sh.step))
    scales = cfg.experiment.sensitivity_scales
    base_pols = get_baselines(cfgv)
    engine = make_engine(w, cfg.policy.shift)

    point_rows, per_type_rows, curve_rows, ml_rows, abl_rows = [], [], [], [], []
    sens = {}  # (kind, scale) -> {"curve": [...], "base": [...]}
    for seed in seeds:
        legit, attacks = generate(cfgv, seed)
        pols = {**base_pols, "engine": engine}
        if ml is not None:
            pols[ML_NAME] = make_ml_engine(ml, cfg.policy.shift)
        for name, pol in pols.items():
            m = evaluate(pol, legit, attacks, costs)
            point_rows.append({**scalar_metrics(m), "policy": name, "seed": seed})
            for a, v in m["per_type"].items():
                per_type_rows.append({"policy": name, "attack_type": a, "share": v["share"],
                                      "seed": seed})
        curve_rows.append(sweep(w, legit, attacks, costs, shifts))
        if ml is not None:
            ml_rows.append(sweep(w, legit, attacks, costs, shifts,
                                 make_policy=lambda d: make_ml_engine(ml, d)))
        if do_ablation:
            abl_rows += ablation(w, cfg.policy.shift, legit, attacks, costs)
        if do_sens:
            for kind in ("friction", "stop"):
                for s in scales:
                    kw = {kind: s}
                    a2 = scale_costs(costs, **kw)
                    entry = sens.setdefault((kind, s), {"curve": [], "base": []})
                    entry["curve"].append(sweep(w, legit, attacks, a2, shifts))
                    for name, pol in base_pols.items():
                        m = evaluate(pol, legit, attacks, a2)
                        entry["base"].append({**scalar_metrics(m), "policy": name, "seed": seed})
        log(f"  seed {seed} done")

    flat = lambda rr: [r for rows in rr for r in rows]  # noqa: E731
    res = {
        "summary": _mean_std(point_rows, ["policy"]),
        "per_type": _mean_std(per_type_rows, ["policy", "attack_type"]),
        "curve": _curve_df(flat(curve_rows), "engine"),
    }
    res["per_type"] = res["per_type"].rename(columns={"share_mean": "share_mean",
                                                      "share_std": "share_std"})
    if ml is not None:
        res["ml_curve"] = _curve_df(flat(ml_rows), ML_NAME)
    if do_ablation:
        res["ablation"] = _mean_std(abl_rows, ["group"])
    if do_sens:
        res["sens"] = {}
        for key, e in sens.items():
            res["sens"][key] = (_curve_df(flat(e["curve"]), "engine"),
                                _mean_std(e["base"], ["policy"]).set_index("policy"))
    return res


def verdicts(curve: pd.DataFrame, summary: pd.DataFrame, include_ml: bool = False) -> pd.DataFrame:
    """For each baseline: the best engine result at no more friction, against the baseline itself.

    PIN only is skipped: it has zero friction and zero protection, so it is the floor, not a rival.
    The ML baseline (include_ml=True) is a reference, not a fair rival, because it was trained on
    data from the same generator.
    """
    rows = []
    cur = [{"friction": r.friction_mean, "prevented": r.prevented_mean} for r in curve.itertuples()]
    for r in summary.itertuples():
        if r.policy in ("engine", "pin_only") or (r.policy == ML_NAME and not include_ml):
            continue
        best = best_prevented_within(cur, r.friction_mean)
        rows.append({"baseline": r.policy, "baseline_friction": r.friction_mean,
                     "baseline_prevented": r.prevented_mean,
                     "engine_prevented_same_friction": best,
                     "engine_wins": best > r.prevented_mean,
                     "is_reference": r.policy == ML_NAME})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default="results/default")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--quick", action="store_true", help="small sizes and 2 seeds, for smoke tests")
    ap.add_argument("--no-ml", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    seeds = args.seeds or list(cfg.seeds.report)
    if args.quick:
        cfg = with_overrides(cfg, {"sizes": {"users": 200, "attacks_per_type": 60}})
        seeds = seeds[:2]
    out = Path(args.out)
    (out / "plots").mkdir(parents=True, exist_ok=True)
    log = lambda s: print(s, flush=True)  # noqa: E731
    t0 = time.time()

    ml = None
    if cfg.baselines.ml_enabled and not args.no_ml:
        log("training ML baseline on tune seeds ...")
        ml = train_ml(cfg, list(cfg.seeds.tune)[: (2 if args.quick else None)])

    (out / "config_used.yaml").write_text(yaml.safe_dump(cfg.to_dict(), sort_keys=False))
    all_res = {}
    for variant, evasive in (("normal", False), ("evasive", True)):
        log(f"variant: {variant}")
        full = variant == "normal"
        all_res[variant] = run_variant(cfg, seeds, evasive, ml, do_ablation=full, do_sens=full,
                                       log=log)

    for variant, r in all_res.items():
        r["summary"].to_csv(out / f"summary_{variant}.csv", index=False)
        r["per_type"].to_csv(out / f"per_type_{variant}.csv", index=False)
        curve = r["curve"]
        if "ml_curve" in r:
            curve = pd.concat([curve, r["ml_curve"]], ignore_index=True)
        curve.to_csv(out / f"sweep_{variant}.csv", index=False)
        verdicts(r["curve"], r["summary"], include_ml=True).to_csv(
            out / f"verdicts_{variant}.csv", index=False
        )
        base = r["summary"].set_index("policy")
        title = ("Fraud stopped against friction" if variant == "normal"
                 else "Fraud stopped against friction, attackers try to look normal")
        plots.plot_tradeoff(r["curve"], base, out / "plots" / f"tradeoff_{variant}.png", title,
                            ml_curve=r.get("ml_curve"), default_shift=cfg.policy.shift)
        plots.plot_per_type(r["per_type"], out / "plots" / f"per_type_{variant}.png")

    n = all_res["normal"]
    n["ablation"].to_csv(out / "ablation.csv", index=False)
    plots.plot_ablation(n["ablation"], out / "plots" / "ablation.png")
    plots.plot_sensitivity(n["sens"], out / "plots" / "sensitivity.png")

    srows = []
    for (kind, scale), (curve, base) in n["sens"].items():
        v = verdicts(curve, base.reset_index())
        v.insert(0, "scale", scale)
        v.insert(0, "assumption", kind)
        srows.append(v)
    sens_df = pd.concat(srows, ignore_index=True)
    sens_df.to_csv(out / "sensitivity.csv", index=False)

    wins = sens_df.groupby(["assumption", "scale"])["engine_wins"].all().reset_index()
    info = {
        "seeds": seeds,
        "seconds": round(time.time() - t0, 1),
        "ml_baseline": ml is not None,
        "engine_beats_every_baseline_in_all_sensitivity_cases": bool(
            sens_df["engine_wins"].all()
        ),
    }
    (out / "run_info.json").write_text(json.dumps(info, indent=2))

    pd.set_option("display.width", 200)
    cols = ["policy", "prevented_mean", "friction_mean", "extra_mean", "abandoned_mean"]
    print("\nNormal attackers (mean over seeds):")
    print(n["summary"][cols].round(1).to_string(index=False))
    print("\nEvasive attackers:")
    print(all_res["evasive"]["summary"][cols].round(1).to_string(index=False))
    print("\nSensitivity, does the engine beat every baseline at equal friction?")
    print(wins.to_string(index=False))
    print(f"\nWrote results to {out} in {info['seconds']} s")


if __name__ == "__main__":
    main()

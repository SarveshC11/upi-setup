"""Baselines (owner: Person 3)."""
from __future__ import annotations

from baselines.ml_baseline import MLScorer, make_ml_engine
from baselines.simple import always_strict, fri_only, make_amount_rule, pin_only


def get_baselines(cfg, ml_model: MLScorer | None = None) -> dict:
    """Returns {name: Policy}. Adds 'ml_baseline' (at the default shift) when a model is given."""
    out = {
        "pin_only": pin_only,
        "always_strict": always_strict,
        "amount_rule": make_amount_rule(cfg.baselines.amount_rule_limit),
        "fri_only": fri_only,
    }
    if ml_model is not None:
        out["ml_baseline"] = make_ml_engine(ml_model, cfg.policy.shift)
    return out

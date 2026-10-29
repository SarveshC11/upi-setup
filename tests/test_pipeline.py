import json
import shutil
import subprocess
import sys

import pytest

from common.config import ConfigError, load_config, with_overrides
from sim.generate import generate


def test_config_rejects_unknown_keys():
    with pytest.raises(ConfigError):
        load_config(overrides={"policy": {"bogus": 1}})


def test_generator_is_deterministic_and_shared_u():
    cfg = with_overrides(load_config(), {"sizes": {"users": 50, "legit_per_user": 10,
                                                   "attacks_per_type": 20}})
    l1, a1 = generate(cfg, 3)
    l2, a2 = generate(cfg, 3)
    assert l1.equals(l2) and a1.equals(a2)
    assert l1["u"].between(0, 1).all() and a1["u"].between(0, 1).all()
    assert set(a1["attack_type"]) == {"simswap", "screenshare", "collect", "replay", "stolen"}


def test_quick_run_writes_outputs(tmp_path):
    out = tmp_path / "r"
    subprocess.run([sys.executable, "-m", "eval.run_experiment", "--out", str(out), "--quick",
                    "--no-ml"], check=True)
    assert (out / "summary_normal.csv").exists() and (out / "plots").is_dir()
    info = json.loads((out / "run_info.json").read_text())
    assert info["seeds"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_parity_with_js_reference():
    """Python port should land within ~3 points of the JS reference averaged over seeds."""
    from baselines.simple import always_strict, fri_only, make_amount_rule
    from eval.metrics import evaluate
    from policy.engine import make_engine

    cfg = load_config()
    seeds = [7, 8, 9, 10, 11]
    js = [json.loads(subprocess.run(["node", "tools/run_reference.js", str(s)], capture_output=True,
                                    text=True, check=True).stdout) for s in seeds]
    pol = {"engine": make_engine(cfg.policy["weights"]), "always_strict": always_strict,
           "amount_rule": make_amount_rule(10000), "fri_only": fri_only}
    for name, p in pol.items():
        py = [evaluate(p, *generate(cfg, s), cfg.costs)["prevented"] for s in seeds]
        ref = [j[name]["prevented"] for j in js]
        assert abs(sum(py) / len(py) - sum(ref) / len(ref)) < 3.0, name

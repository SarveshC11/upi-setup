import numpy as np
import pandas as pd

from common.config import load_config
from policy import calibrate as cal
from policy.engine import SIGNAL_GROUPS


def test_decode_always_gives_strictly_increasing_thresholds():
    rng = np.random.default_rng(0)
    for _ in range(200):
        _, th = cal.decode(rng.integers(0, 101, cal.N_GENES))
        assert 1 <= th[0] < th[1] < th[2] <= 100


def test_encode_decode_round_trip_on_default_policy():
    cfg = load_config()
    w, th = cfg.policy["weights"], tuple(cfg.policy["base_thresholds"])
    w2, th2 = cal.decode(cal.encode(w, th))
    assert w2 == dict(w) and th2 == th


def test_genome_keys_match_signal_groups():
    assert sorted(cal.KEYS) == sorted(k for ks in SIGNAL_GROUPS.values() for k in ks)


def test_nondominated_sort_on_a_tiny_example():
    # columns: (-prevented, friction), both minimised. Point 3 is dominated by point 0.
    F = np.array([[-80.0, 100.0], [-60.0, 20.0], [-90.0, 300.0], [-70.0, 150.0]])
    assert sorted(cal.fast_nondominated_sort(F)[0]) == [0, 1, 2]


def test_nondominated_filter_drops_dominated_rows():
    df = pd.DataFrame({"prevented": [80, 70, 60], "friction": [100, 150, 20]})
    assert list(cal.nondominated(df)["friction"]) == [20, 100]


def test_select_point_respects_friction_budget():
    f = pd.DataFrame({"prevented": [60, 80, 90], "friction": [20, 100, 300]})
    assert cal.select_point(f, 120)["prevented"] == 80


def test_quick_calibration_writes_a_loadable_config(tmp_path):
    y = tmp_path / "cal.yaml"
    cal.main(["--quick", "--out", str(tmp_path / "o"), "--yaml", str(y)])
    cfg = load_config(y)  # must pass the shared loader's key and type checks
    assert len(cfg.policy["base_thresholds"]) == 3
    assert set(cfg.policy["weights"]) == set(cal.KEYS)
    assert (tmp_path / "o" / "holdout.csv").exists()

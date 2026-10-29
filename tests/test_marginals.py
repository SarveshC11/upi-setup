from common.config import load_config
from sim.generate import generate


def test_genuine_marginals_are_sane():
    legit, _ = generate(load_config(), 1)
    assert 0.08 < legit["new_payee"].mean() < 0.16
    assert legit["network"].value_counts(normalize=True).idxmax() in ("home", "mobile")
    assert (legit["amount"] > 0).all()

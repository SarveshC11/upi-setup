"""Random number helpers (owner: Person 1)."""
import numpy as np


def make_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)

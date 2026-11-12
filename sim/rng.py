"""Random number helpers (owner: Person 1).

One numpy Generator per seed. Streams that must not disturb the main one (evasive draws,
learned-attacker batches) get their own Generator derived from the same seed.
"""
import numpy as np


def make_rng(seed: int) -> np.random.Generator:
    """Main stream for a seed. Genuine payments, attack signals and `u` all come from here."""
    return np.random.default_rng(seed)


def make_side_rng(seed: int, *salt: int) -> np.random.Generator:
    """Independent stream for (seed, salt...) that does not shift the main stream."""
    return np.random.default_rng([seed, *salt])

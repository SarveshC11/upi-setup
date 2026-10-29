"""Comparison rules (owner: Person 3). Each is a Policy: DataFrame in, Series of tier codes out."""
from __future__ import annotations

import numpy as np
import pandas as pd


def pin_only(df: pd.DataFrame) -> pd.Series:
    """Never adds any check. The UPI PIN is always required anyway."""
    return pd.Series("0", index=df.index)


def always_strict(df: pd.DataFrame) -> pd.Series:
    """OTP or biometric on every payment."""
    return pd.Series("1", index=df.index)


def make_amount_rule(limit: float = 10000):
    """Step-up check when the amount is above a fixed limit."""

    def policy(df: pd.DataFrame) -> pd.Series:
        return pd.Series(np.where(df["amount"].to_numpy() > limit, "1", "0"), index=df.index)

    return policy


def fri_only(df: pd.DataFrame) -> pd.Series:
    """Models what is deployed today: block 'very high' payee numbers, warn on 'medium' and 'high'."""
    fri = df["fri"].to_numpy()
    return pd.Series(np.select([fri == 3, fri >= 1], ["3", "W"], default="0"), index=df.index)

"""Attribution models.

Per-touch (rule-based) models give every touchpoint of a conversion a credit,
and the credits for one conversion always add up to 1:

    first_touch       100% to the first touch
    last_touch        100% to the last touch
    last_non_direct   100% to the last touch that is not Direct (Direct only if nothing else)
    linear            split evenly across all touches
    time_decay        weighted by 0.5 ** (days before conversion / half-life)
    position_based    40% first, 40% last, 20% shared by the middle (U-shaped)

The data-driven Markov model is in ``markov.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DIRECT_CHANNELS


def _prepare(touches: pd.DataFrame) -> pd.DataFrame:
    df = touches.sort_values(["conversion_id", "touch_ts_ist"], kind="mergesort").reset_index(drop=True)
    g = df.groupby("conversion_id", sort=False)
    df["pos"] = g.cumcount()
    df["n"] = g["channel"].transform("size")
    return df


def first_touch(df: pd.DataFrame, **_) -> pd.Series:
    return (df["pos"] == 0).astype(float)


def last_touch(df: pd.DataFrame, **_) -> pd.Series:
    return (df["pos"] == df["n"] - 1).astype(float)


def last_non_direct(df: pd.DataFrame, **_) -> pd.Series:
    nd_pos = df["pos"].where(~df["channel"].isin(DIRECT_CHANNELS), -1)
    target = nd_pos.groupby(df["conversion_id"], sort=False).transform("max")
    target = target.where(target >= 0, df["n"] - 1)  # all-direct journeys: last touch
    return (df["pos"] == target).astype(float)


def linear(df: pd.DataFrame, **_) -> pd.Series:
    return 1.0 / df["n"]


def time_decay(df: pd.DataFrame, half_life_days: float = 7.0, **_) -> pd.Series:
    age_days = (
        pd.to_datetime(df["order_ts_ist"]) - pd.to_datetime(df["touch_ts_ist"])
    ).dt.total_seconds() / 86_400
    weight = np.power(0.5, age_days.clip(lower=0) / half_life_days)
    return weight / weight.groupby(df["conversion_id"], sort=False).transform("sum")


def position_based(df: pd.DataFrame, **_) -> pd.Series:
    n, pos = df["n"], df["pos"]
    middle = 0.2 / (n - 2).where(n > 2, 1)
    credit = np.select(
        [n == 1, n == 2, (pos == 0) | (pos == n - 1)],
        [1.0, 0.5, 0.4],
        default=middle,
    )
    return pd.Series(credit, index=df.index, dtype=float)


MODELS = {
    "first_touch": first_touch,
    "last_touch": last_touch,
    "last_non_direct": last_non_direct,
    "linear": linear,
    "time_decay": time_decay,
    "position_based": position_based,
}


def touch_credits(touches: pd.DataFrame, model: str, half_life_days: float = 7.0) -> pd.DataFrame:
    """Return one row per touch with ``credit`` (sums to 1 per conversion) and revenue credit."""
    if model not in MODELS:
        raise ValueError(f"Unknown model {model!r}. Choose from {sorted(MODELS)}")
    df = _prepare(touches)
    df["credit"] = MODELS[model](df, half_life_days=half_life_days).to_numpy()
    df["revenue_credit"] = df["credit"] * df["revenue"]
    df["new_customer_credit"] = df["credit"] * df["is_new"]
    df["model"] = model
    return df


def summarise(credits: pd.DataFrame) -> pd.DataFrame:
    """Channel totals: attributed orders, new customers and revenue."""
    out = (
        credits.groupby(["model", "channel"], as_index=False)
        .agg(orders=("credit", "sum"),
             new_customers=("new_customer_credit", "sum"),
             revenue=("revenue_credit", "sum"))
    )
    return out

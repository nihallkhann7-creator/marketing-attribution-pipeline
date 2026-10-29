"""Data-driven attribution with a first-order Markov chain and removal effects.

Every journey becomes a path  start -> channel -> ... -> (conversion | null).
From all paths we estimate transition probabilities between states, then:

    P(conversion)            probability of reaching "conversion" from "start"
    P(conversion | remove c) the same, after sending every transition into c to "null"
    removal_effect(c)        1 - P(conversion | remove c) / P(conversion)

Each channel's share of conversions is its removal effect divided by the sum of
all removal effects. Unlike rule-based models this needs non-converting journeys,
because a channel that shows up a lot in paths that never convert should earn less.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

START, CONVERSION, NULL = "(start)", "(conversion)", "(null)"


def _transitions(paths: pd.DataFrame, path_col: str, end_state: str) -> pd.DataFrame:
    """(from, to) pairs for each path: start -> touches... -> end_state."""
    df = paths.sort_values([path_col, "touch_ts_ist"], kind="mergesort")
    nxt = df.groupby(path_col, sort=False)["channel"].shift(-1).fillna(end_state)
    first = df.groupby(path_col, sort=False)["channel"].first()
    inner = pd.DataFrame({"from": df["channel"].to_numpy(), "to": nxt.to_numpy()})
    starts = pd.DataFrame({"from": START, "to": first.to_numpy()})
    return pd.concat([starts, inner], ignore_index=True)


def transition_matrix(conversion_touches: pd.DataFrame, null_touches: pd.DataFrame) -> pd.DataFrame:
    pairs = pd.concat(
        [
            _transitions(conversion_touches, "conversion_id", CONVERSION),
            _transitions(null_touches, "path_id", NULL),
        ],
        ignore_index=True,
    )
    counts = pairs.value_counts(["from", "to"]).unstack(fill_value=0)
    channels = sorted((set(counts.index) | set(counts.columns)) - {START, CONVERSION, NULL})
    states = [START, *channels, CONVERSION, NULL]
    counts = counts.reindex(index=states, columns=states, fill_value=0).astype(float)
    counts.loc[CONVERSION, CONVERSION] = 1.0
    counts.loc[NULL, NULL] = 1.0
    return counts.div(counts.sum(axis=1).replace(0, 1), axis=0)


def conversion_probability(P: pd.DataFrame) -> float:
    """Probability of absorbing in CONVERSION when starting from START."""
    transient = [s for s in P.index if s not in (CONVERSION, NULL)]
    Q = P.loc[transient, transient].to_numpy()
    R = P.loc[transient, [CONVERSION]].to_numpy()
    absorb = np.linalg.solve(np.eye(len(transient)) - Q, R)
    return float(absorb[transient.index(START), 0])


def removal_effects(P: pd.DataFrame) -> pd.Series:
    base = conversion_probability(P)
    channels = [s for s in P.index if s not in (START, CONVERSION, NULL)]
    effects = {}
    for channel in channels:
        removed = P.copy()
        removed[NULL] += removed[channel]   # anything that would enter the channel drops off
        removed[channel] = 0.0
        removed.loc[channel] = 0.0
        removed.loc[channel, NULL] = 1.0
        effects[channel] = 1.0 - conversion_probability(removed) / base if base > 0 else 0.0
    return pd.Series(effects, name="removal_effect").clip(lower=0)


def shares(conversion_touches: pd.DataFrame, null_touches: pd.DataFrame) -> pd.Series:
    effects = removal_effects(transition_matrix(conversion_touches, null_touches))
    total = effects.sum()
    return effects / total if total > 0 else effects


def summarise(conversion_touches: pd.DataFrame, null_touches: pd.DataFrame) -> pd.DataFrame:
    """Channel totals under the Markov model.

    Orders and revenue are split by the removal-effect shares of all conversions.
    New customers are split by shares estimated from first-order journeys only.
    """
    conv = conversion_touches.drop_duplicates("conversion_id")
    share_all = shares(conversion_touches, null_touches)
    new_ids = conv.loc[conv["is_new"] == 1, "conversion_id"]
    share_new = shares(conversion_touches[conversion_touches["conversion_id"].isin(new_ids)], null_touches)

    channels = sorted(set(share_all.index) | set(share_new.index))
    out = pd.DataFrame({"channel": channels})
    out["orders"] = out["channel"].map(share_all).fillna(0) * len(conv)
    out["revenue"] = out["channel"].map(share_all).fillna(0) * conv["revenue"].sum()
    out["new_customers"] = out["channel"].map(share_new).fillna(0) * int(conv["is_new"].sum())
    out.insert(0, "model", "markov")
    return out[["model", "channel", "orders", "new_customers", "revenue"]]

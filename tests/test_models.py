import pandas as pd
import pytest

from mta import models


def journeys(*paths, is_new=1, revenue=1000.0):
    """Build touches: each path is a list of (channel, days_before_order)."""
    rows = []
    for i, path in enumerate(paths):
        order_ts = pd.Timestamp("2026-07-31 20:00:00")
        for channel, days_before in path:
            rows.append({
                "conversion_id": f"C{i}",
                "order_ts_ist": str(order_ts),
                "touch_ts_ist": str(order_ts - pd.Timedelta(days=days_before)),
                "channel": channel,
                "revenue": revenue,
                "is_new": is_new,
            })
    return pd.DataFrame(rows)


def credit_map(df, model, **kw):
    out = models.touch_credits(df, model, **kw)
    return out.groupby("channel")["credit"].sum().to_dict()


THREE_TOUCH = [("Meta Prospecting", 10), ("Google Search Generic", 4), ("Direct", 0)]


@pytest.mark.parametrize("model", list(models.MODELS))
def test_credits_sum_to_one_per_conversion(model):
    df = journeys(THREE_TOUCH, [("Email", 1)], [("Organic Search", 3), ("Direct", 0)])
    out = models.touch_credits(df, model)
    assert out.groupby("conversion_id")["credit"].sum().round(9).eq(1).all()


def test_first_and_last_touch():
    df = journeys(THREE_TOUCH)
    assert credit_map(df, "first_touch") == {"Direct": 0, "Google Search Generic": 0, "Meta Prospecting": 1}
    assert credit_map(df, "last_touch")["Direct"] == 1


def test_last_non_direct_skips_direct():
    df = journeys(THREE_TOUCH)
    assert credit_map(df, "last_non_direct")["Google Search Generic"] == 1


def test_last_non_direct_falls_back_to_direct_when_nothing_else():
    df = journeys([("Direct", 3), ("Direct", 0)])
    out = models.touch_credits(df, "last_non_direct")
    assert out["credit"].tolist() == [0.0, 1.0]


def test_linear_splits_evenly():
    credits = credit_map(journeys(THREE_TOUCH), "linear")
    assert all(v == pytest.approx(1 / 3) for v in credits.values())


def test_position_based_u_shape():
    df = journeys([("A", 9), ("B", 6), ("C", 3), ("D", 0)])
    credits = credit_map(df, "position_based")
    assert credits == pytest.approx({"A": 0.4, "B": 0.1, "C": 0.1, "D": 0.4})


def test_position_based_two_touches_is_fifty_fifty():
    assert credit_map(journeys([("A", 2), ("B", 0)]), "position_based") == {"A": 0.5, "B": 0.5}


def test_time_decay_halves_every_half_life():
    df = journeys([("Old", 7), ("New", 0)])
    credits = credit_map(df, "time_decay", half_life_days=7)
    assert credits["New"] / credits["Old"] == pytest.approx(2.0)


def test_revenue_and_new_customer_credit_follow_credit():
    df = journeys([("A", 1), ("B", 0)], revenue=800.0, is_new=1)
    out = models.touch_credits(df, "linear")
    assert out["revenue_credit"].sum() == pytest.approx(800.0)
    assert out["new_customer_credit"].sum() == pytest.approx(1.0)


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        models.touch_credits(journeys(THREE_TOUCH), "magic")

import pandas as pd
import pytest

from mta import markov


def paths(rows, id_col):
    out = []
    for path_id, channels in rows:
        for i, ch in enumerate(channels):
            out.append({id_col: path_id, "touch_ts_ist": f"2026-07-0{i + 1} 10:00:00", "channel": ch,
                        "revenue": 1000.0, "is_new": 1})
    return pd.DataFrame(out)


def test_single_channel_gets_all_credit():
    conv = paths([("c1", ["A"]), ("c2", ["A"])], "conversion_id")
    null = paths([("n1", ["A"])], "path_id")
    assert markov.shares(conv, null).to_dict() == {"A": pytest.approx(1.0)}


def test_channel_only_in_non_converting_paths_gets_nothing():
    conv = paths([("c1", ["A"]), ("c2", ["A", "A"])], "conversion_id")
    null = paths([("n1", ["B"]), ("n2", ["B"])], "path_id")
    s = markov.shares(conv, null)
    assert s["A"] == pytest.approx(1.0)
    assert s["B"] == pytest.approx(0.0)


def test_essential_channels_share_equally():
    # Every conversion needs both A and B, so removing either kills all conversions
    conv = paths([("c1", ["A", "B"]), ("c2", ["A", "B"])], "conversion_id")
    null = paths([("n1", ["A"])], "path_id")
    s = markov.shares(conv, null)
    assert s["A"] == pytest.approx(0.5)
    assert s["B"] == pytest.approx(0.5)


def test_summary_reconciles_to_totals():
    conv = paths([("c1", ["A", "B"]), ("c2", ["B"]), ("c3", ["A", "C", "B"])], "conversion_id")
    null = paths([("n1", ["C"]), ("n2", ["A", "C"])], "path_id")
    summary = markov.summarise(conv, null)
    assert summary["orders"].sum() == pytest.approx(3)
    assert summary["revenue"].sum() == pytest.approx(3000)
    assert summary["new_customers"].sum() == pytest.approx(3)


def test_conversion_probability_matches_hand_calculation():
    # start -> A always; A converts 1 time in 4
    conv = paths([("c1", ["A"])], "conversion_id")
    null = paths([("n1", ["A"]), ("n2", ["A"]), ("n3", ["A"])], "path_id")
    P = markov.transition_matrix(conv, null)
    assert markov.conversion_probability(P) == pytest.approx(0.25)

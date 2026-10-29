"""End-to-end: run the whole pipeline on a small synthetic dataset, twice."""

import sqlite3

import pandas as pd
import pytest

from mta.config import ALL_MODELS, Settings
from mta.pipeline import run

TABLES = ["raw_sessions", "raw_orders", "raw_ad_spend", "stg_orders", "mart_conversion_touchpoints"]


@pytest.fixture(scope="module")
def settings(tmp_path_factory):
    base = tmp_path_factory.mktemp("run")
    return Settings(data_dir=base / "data", output_dir=base / "output")


@pytest.fixture(scope="module")
def first_run(settings):
    return run(settings, regenerate=True, users=4_000, days=30, seed=7, log=lambda *_: None)


def counts(settings):
    with sqlite3.connect(settings.db_path) as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


def test_quality_gates_pass(first_run):
    checks = first_run["checks"]
    assert not (checks["status"] == "FAIL").any(), checks.to_string()


def test_rerun_is_idempotent(settings, first_run):
    before = counts(settings)
    run(settings, regenerate=False, log=lambda *_: None)  # same raw files loaded again
    assert counts(settings) == before


def test_restated_spend_rows_keep_latest_value(settings, first_run):
    raw = pd.read_csv(settings.raw_dir / "raw_ad_spend.csv")
    latest = raw.drop_duplicates(["date", "platform", "campaign_id"], keep="last")
    with sqlite3.connect(settings.db_path) as conn:
        stored = conn.execute("SELECT ROUND(SUM(spend), 2) FROM raw_ad_spend").fetchone()[0]
    assert stored == pytest.approx(latest["spend"].sum(), abs=0.05)


def test_every_model_reports(settings, first_run):
    perf = pd.read_csv(settings.output_dir / "channel_performance.csv")
    assert set(perf["model"]) == set(ALL_MODELS)
    assert (settings.output_dir / "report.md").read_text().startswith("# Attribution report")
    assert (settings.output_dir / "model_comparison.png").stat().st_size > 10_000


def test_lookback_never_credits_touches_before_previous_order(settings, first_run):
    with sqlite3.connect(settings.db_path) as conn:
        bad = conn.execute(
            """SELECT COUNT(*) FROM mart_conversion_touchpoints t
               JOIN stg_orders o ON o.order_id = t.conversion_id
               WHERE t.session_id IS NOT NULL
                 AND (t.touch_ts_ist > o.order_ts_ist
                      OR t.touch_ts_ist < datetime(o.order_ts_ist, '-30 days')
                      OR (o.prev_order_ts_ist IS NOT NULL AND t.touch_ts_ist <= o.prev_order_ts_ist))"""
        ).fetchone()[0]
    assert bad == 0

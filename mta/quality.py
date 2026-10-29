"""Data-quality gates. A FAIL stops the pipeline; a WARN is reported and the run continues."""

from __future__ import annotations

import sqlite3

import pandas as pd

from .config import PER_TOUCH_MODELS

TOLERANCE = 1e-6


def _scalar(conn: sqlite3.Connection, sql: str) -> float:
    return conn.execute(sql).fetchone()[0] or 0


def run_checks(conn: sqlite3.Connection, load_stats: dict | None = None) -> pd.DataFrame:
    results: list[dict] = []

    def add(check: str, ok: bool, detail: str, warn_only: bool = False) -> None:
        status = "PASS" if ok else ("WARN" if warn_only else "FAIL")
        results.append({"check": check, "status": status, "detail": detail})

    # 1. Upserts collapse duplicate keys
    if load_stats:
        for table, s in load_stats.items():
            rows = _scalar(conn, f"SELECT COUNT(*) FROM {table}")
            dupes = s["rows_read"] - s["distinct_keys"]
            add(f"{table}: one row per key", rows == s["distinct_keys"],
                f"{s['rows_read']:,} rows read, {dupes:,} duplicate keys, {rows:,} rows stored")

    # 2. Every order reaches the attribution mart
    orders = _scalar(conn, "SELECT COUNT(*) FROM stg_orders")
    conv = _scalar(conn, "SELECT COUNT(DISTINCT conversion_id) FROM mart_conversion_touchpoints")
    add("Every order has a conversion path", orders == conv, f"{orders:,} orders, {conv:,} paths")

    # 3. Spend reconciles from raw to mart
    raw_spend = _scalar(conn, "SELECT SUM(spend) FROM raw_ad_spend")
    mart_spend = _scalar(conn, "SELECT SUM(spend) FROM mart_daily_channel_spend")
    add("Spend reconciles raw → mart", abs(raw_spend - mart_spend) < 1, f"raw ₹{raw_spend:,.2f}, mart ₹{mart_spend:,.2f}")

    # 4. Unmapped campaigns (data issue to fix in the taxonomy, not a pipeline failure)
    unmapped_sessions = _scalar(conn, "SELECT COUNT(*) FROM stg_sessions WHERE channel = 'Unmapped'")
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT campaign_norm FROM stg_sessions WHERE channel = 'Unmapped' LIMIT 5")]
    add("No unmapped sessions", unmapped_sessions == 0,
        f"{unmapped_sessions:,} sessions unmapped" + (f" (e.g. {', '.join(names)})" if names else ""),
        warn_only=True)
    unmapped_spend = _scalar(conn, "SELECT SUM(spend) FROM stg_ad_spend WHERE channel = 'Unmapped'")
    add("No unmapped spend", unmapped_spend == 0, f"₹{unmapped_spend:,.2f} unmapped")

    # 5. Per-touch credits sum to exactly 1 per conversion, for every model
    table_exists = _scalar(conn, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'attribution_touch_credits'")
    if table_exists:
        worst = conn.execute(
            """SELECT model, MAX(ABS(total - 1)) FROM (
                   SELECT model, conversion_id, SUM(credit) AS total
                   FROM attribution_touch_credits GROUP BY model, conversion_id)
               GROUP BY model"""
        ).fetchall()
        bad = [m for m, err in worst if err > TOLERANCE]
        add("Credits sum to 1 per conversion", not bad and len(worst) == len(PER_TOUCH_MODELS),
            f"{len(worst)} models checked" + (f"; failing: {', '.join(bad)}" if bad else ""))

        # 6. Every model hands out exactly the total orders and revenue
        totals = conn.execute("SELECT COUNT(*), SUM(revenue) FROM stg_orders").fetchone()
        by_model = conn.execute(
            "SELECT model, SUM(orders), SUM(revenue) FROM attribution_channel_summary GROUP BY model").fetchall()
        off = [m for m, o, r in by_model if abs(o - totals[0]) > 1e-3 or abs(r - totals[1]) > 1e-2]
        add("All models reconcile to total orders & revenue", not off,
            f"{len(by_model)} models vs {totals[0]:,} orders / ₹{totals[1]:,.0f}" + (f"; off: {off}" if off else ""))

    # 7. Timezone: no IST date before the data starts
    min_raw = _scalar(conn, "SELECT MIN(date(session_start_utc, '+330 minutes')) FROM raw_sessions")
    min_stg = _scalar(conn, "SELECT MIN(session_date_ist) FROM stg_sessions")
    add("Session dates converted to IST", min_raw == min_stg, f"first IST date {min_stg}")

    return pd.DataFrame(results)

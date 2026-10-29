"""Load raw files into SQLite with idempotent upserts, then build staging and marts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import SQL_DIR, Settings
from .taxonomy import Taxonomy, default_taxonomy, normalise

RAW_TABLES = {
    # table: (csv file, key columns, value columns)
    "raw_sessions": ("raw_sessions.csv", ["session_id"],
                     ["user_id", "session_start_utc", "source", "medium", "campaign", "device"]),
    "raw_orders": ("raw_orders.csv", ["order_id"], ["user_id", "order_ts_utc", "revenue"]),
    "raw_ad_spend": ("raw_ad_spend.csv", ["date", "platform", "campaign_id"],
                     ["campaign_name", "impressions", "clicks", "spend"]),
}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def run_sql_file(conn: sqlite3.Connection, name: str, **params: object) -> None:
    sql = (SQL_DIR / name).read_text()
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", str(value))
    conn.executescript(sql)


def upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame,
           keys: list[str], values: list[str]) -> int:
    """INSERT ... ON CONFLICT DO UPDATE. Rows later in ``df`` win for the same key."""
    cols = keys + values + ["loaded_at"]
    df = df.assign(loaded_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in values + ["loaded_at"])
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}"
    )
    conn.executemany(sql, df[cols].itertuples(index=False, name=None))
    return len(df)


def _read_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in ("revenue", "spend"):
        if col in df:
            df[col] = df[col].astype(float)
    for col in ("impressions", "clicks"):
        if col in df:
            df[col] = df[col].astype(int)
    return df


def load_raw(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, dict[str, int]]:
    """Upsert every raw CSV. Returns rows read and distinct keys per table."""
    run_sql_file(conn, "01_schema.sql")
    stats = {}
    with conn:
        for table, (filename, keys, values) in RAW_TABLES.items():
            df = _read_raw(raw_dir / filename)
            upsert(conn, table, df, keys, values)
            stats[table] = {"rows_read": len(df), "distinct_keys": int(df[keys].drop_duplicates().shape[0])}
    return stats


def build_channel_maps(conn: sqlite3.Connection, taxonomy: Taxonomy | None = None) -> dict[str, int]:
    """Resolve every distinct UTM triple and spend campaign to a channel and upsert the maps."""
    taxonomy = taxonomy or default_taxonomy()

    utm = pd.read_sql("SELECT DISTINCT source, medium, campaign FROM raw_sessions", conn)
    resolved = [taxonomy.resolve(r.source, r.medium, r.campaign) for r in utm.itertuples(index=False)]
    utm["campaign_norm"] = utm["campaign"].map(normalise)
    utm["channel"] = [ch for ch, _ in resolved]
    utm["is_paid"] = [int(p) for _, p in resolved]

    spend = pd.read_sql("SELECT DISTINCT platform, campaign_name FROM raw_ad_spend", conn)
    resolved = [taxonomy.resolve_spend(r.platform, r.campaign_name) for r in spend.itertuples(index=False)]
    spend["campaign_norm"] = spend["campaign_name"].map(normalise)
    spend["channel"] = [ch for ch, _ in resolved]
    spend["is_paid"] = [int(p) for _, p in resolved]

    with conn:
        for table, df, keys in (
            ("dim_utm_map", utm, ["source", "medium", "campaign"]),
            ("dim_spend_map", spend, ["platform", "campaign_name"]),
        ):
            values = ["campaign_norm", "channel", "is_paid"]
            cols = keys + values
            conn.executemany(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
                f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET "
                + ", ".join(f"{c} = excluded.{c}" for c in values),
                df[cols].itertuples(index=False, name=None),
            )
    return {"utm_triples": len(utm), "spend_campaigns": len(spend)}


def build_models_input(conn: sqlite3.Connection, settings: Settings) -> None:
    run_sql_file(conn, "02_staging.sql")
    run_sql_file(conn, "03_marts.sql", lookback_days=int(settings.lookback_days))
    conn.commit()


def run_etl(settings: Settings) -> dict:
    conn = connect(settings.db_path)
    try:
        stats = {"load": load_raw(conn, settings.raw_dir)}
        stats["maps"] = build_channel_maps(conn)
        build_models_input(conn, settings)
        return stats
    finally:
        conn.close()

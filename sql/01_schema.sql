-- Raw layer: loaded with upserts on natural keys, never deleted.
-- Re-running a load with the same or restated files leaves one row per key,
-- and the most recent value wins.

CREATE TABLE IF NOT EXISTS raw_sessions (
    session_id         TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL,
    session_start_utc  TEXT NOT NULL,
    source             TEXT,
    medium             TEXT,
    campaign           TEXT,
    device             TEXT,
    loaded_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_orders (
    order_id      TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    order_ts_utc  TEXT NOT NULL,
    revenue       REAL NOT NULL,
    loaded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_ad_spend (
    date           TEXT NOT NULL,   -- ad accounts report in IST
    platform       TEXT NOT NULL,
    campaign_id    TEXT NOT NULL,
    campaign_name  TEXT NOT NULL,
    impressions    INTEGER,
    clicks         INTEGER,
    spend          REAL NOT NULL,
    loaded_at      TEXT NOT NULL,
    PRIMARY KEY (date, platform, campaign_id)
);

-- Mapping tables, filled by the Python taxonomy resolver
CREATE TABLE IF NOT EXISTS dim_utm_map (
    source         TEXT NOT NULL,
    medium         TEXT NOT NULL,
    campaign       TEXT NOT NULL,
    campaign_norm  TEXT NOT NULL,
    channel        TEXT NOT NULL,
    is_paid        INTEGER NOT NULL,
    PRIMARY KEY (source, medium, campaign)
);

CREATE TABLE IF NOT EXISTS dim_spend_map (
    platform       TEXT NOT NULL,
    campaign_name  TEXT NOT NULL,
    campaign_norm  TEXT NOT NULL,
    channel        TEXT NOT NULL,
    is_paid        INTEGER NOT NULL,
    PRIMARY KEY (platform, campaign_name)
);

CREATE INDEX IF NOT EXISTS ix_raw_sessions_user ON raw_sessions (user_id, session_start_utc);
CREATE INDEX IF NOT EXISTS ix_raw_orders_user ON raw_orders (user_id, order_ts_utc);

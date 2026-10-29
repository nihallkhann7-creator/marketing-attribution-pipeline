-- Staging layer: cleaned, typed, mapped to channels, converted to IST.
-- Derived tables are rebuilt from the raw layer on every run, so they are deterministic.

DROP TABLE IF EXISTS stg_sessions;
CREATE TABLE stg_sessions AS
SELECT
    s.session_id,
    s.user_id,
    datetime(s.session_start_utc, '+330 minutes')   AS session_ts_ist,
    date(s.session_start_utc, '+330 minutes')       AS session_date_ist,
    COALESCE(m.channel, 'Unmapped')                 AS channel,
    COALESCE(m.is_paid, 0)                          AS is_paid,
    m.campaign_norm,
    s.device
FROM raw_sessions s
LEFT JOIN dim_utm_map m
       ON m.source = s.source
      AND m.medium = s.medium
      AND m.campaign = s.campaign;

CREATE INDEX ix_stg_sessions_user ON stg_sessions (user_id, session_ts_ist);


DROP TABLE IF EXISTS stg_orders;
CREATE TABLE stg_orders AS
WITH o AS (
    SELECT
        order_id,
        user_id,
        datetime(order_ts_utc, '+330 minutes') AS order_ts_ist,
        date(order_ts_utc, '+330 minutes')     AS order_date_ist,
        revenue
    FROM raw_orders
)
SELECT
    order_id,
    user_id,
    order_ts_ist,
    order_date_ist,
    revenue,
    ROW_NUMBER() OVER w                 AS order_number,
    LAG(order_ts_ist) OVER w            AS prev_order_ts_ist
FROM o
WINDOW w AS (PARTITION BY user_id ORDER BY order_ts_ist, order_id);

CREATE INDEX ix_stg_orders_user ON stg_orders (user_id, order_ts_ist);


DROP TABLE IF EXISTS stg_ad_spend;
CREATE TABLE stg_ad_spend AS
SELECT
    a.date                              AS spend_date,
    a.platform,
    a.campaign_id,
    a.campaign_name,
    COALESCE(m.channel, 'Unmapped')     AS channel,
    a.impressions,
    a.clicks,
    a.spend
FROM raw_ad_spend a
LEFT JOIN dim_spend_map m
       ON m.platform = a.platform
      AND m.campaign_name = a.campaign_name;

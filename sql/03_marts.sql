-- Mart layer: model-ready tables.
-- {lookback_days} is filled in by the pipeline (default 30).

-- Every order with the touchpoints that led to it:
--   * touches up to the order time, within the lookback window,
--   * and after the customer's previous order, so no touch is credited twice.
-- Orders with no tracked touch get a single synthetic "Direct (untracked)" touch.
DROP TABLE IF EXISTS mart_conversion_touchpoints;
CREATE TABLE mart_conversion_touchpoints AS
SELECT
    o.order_id                                          AS conversion_id,
    o.user_id,
    o.order_ts_ist,
    o.order_date_ist,
    o.revenue,
    CASE WHEN o.order_number = 1 THEN 1 ELSE 0 END      AS is_new,
    s.session_id,
    COALESCE(s.session_ts_ist, o.order_ts_ist)          AS touch_ts_ist,
    COALESCE(s.channel, 'Direct (untracked)')           AS channel
FROM stg_orders o
LEFT JOIN stg_sessions s
       ON s.user_id = o.user_id
      AND s.session_ts_ist <= o.order_ts_ist
      AND s.session_ts_ist >= datetime(o.order_ts_ist, '-{lookback_days} days')
      AND (o.prev_order_ts_ist IS NULL OR s.session_ts_ist > o.prev_order_ts_ist);


-- Journeys that did not end in an order (needed by the Markov model):
-- users who never bought, plus touches after a customer's latest order.
DROP TABLE IF EXISTS mart_null_paths;
CREATE TABLE mart_null_paths AS
WITH last_order AS (
    SELECT user_id, MAX(order_ts_ist) AS last_order_ts
    FROM stg_orders
    GROUP BY user_id
)
SELECT
    'null:' || s.user_id    AS path_id,
    s.session_ts_ist        AS touch_ts_ist,
    s.channel
FROM stg_sessions s
LEFT JOIN last_order lo ON lo.user_id = s.user_id
WHERE lo.user_id IS NULL
   OR s.session_ts_ist > lo.last_order_ts;


DROP TABLE IF EXISTS mart_daily_channel_spend;
CREATE TABLE mart_daily_channel_spend AS
SELECT
    spend_date,
    channel,
    SUM(impressions)    AS impressions,
    SUM(clicks)         AS clicks,
    ROUND(SUM(spend), 2) AS spend
FROM stg_ad_spend
GROUP BY spend_date, channel;


DROP TABLE IF EXISTS mart_daily_orders;
CREATE TABLE mart_daily_orders AS
SELECT
    order_date_ist                                      AS order_date,
    COUNT(*)                                            AS orders,
    SUM(CASE WHEN order_number = 1 THEN 1 ELSE 0 END)   AS new_customers,
    ROUND(SUM(revenue), 2)                              AS revenue
FROM stg_orders
GROUP BY order_date_ist;

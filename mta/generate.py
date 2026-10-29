"""Synthetic data generator for "Brewline", a fictional D2C coffee brand in India.

The data is designed to look like real marketing exports, including their flaws:

* user journeys that cross several channels before a first order, plus repeat orders
* UTM values with inconsistent case, stray whitespace and hyphen/underscore drift
* one campaign renamed mid-period (same campaign_id, new name)
* ad-spend rows re-pulled with restated numbers (duplicate keys; the later pull wins)
* a handful of sessions tagged with a test campaign that maps to no channel
* raw timestamps stored in UTC, while reporting is done in IST

Nothing here comes from a real company. Every number is drawn from distributions
defined below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

IST_OFFSET = timedelta(hours=5, minutes=30)


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    weight: float


@dataclass(frozen=True)
class ChannelSpec:
    platform: str | None          # ad platform in the spend export (None = no spend)
    source: str                   # utm_source
    medium: str                   # utm_medium
    campaigns: tuple[Campaign, ...]
    cpc: float                    # average cost per click, INR
    ctr: float                    # click-through rate, for impressions
    p_convert: float              # per-touch conversion probability


CHANNELS: dict[str, ChannelSpec] = {
    "Google Search Brand": ChannelSpec(
        "Google Ads", "google", "cpc",
        (Campaign("G-1001", "GS_Brand_Exact", 0.7), Campaign("G-1002", "GS_Brand_Phrase", 0.3)),
        cpc=13.0, ctr=0.18, p_convert=0.085,
    ),
    "Google Search Generic": ChannelSpec(
        "Google Ads", "google", "cpc",
        (Campaign("G-2001", "GS_Generic_Coffee_Beans", 0.5),
         Campaign("G-2002", "GS_Generic_Cold_Brew", 0.3),
         Campaign("G-2003", "GS_Competitor_Terms", 0.2)),
        cpc=42.0, ctr=0.05, p_convert=0.032,
    ),
    "Google PMax": ChannelSpec(
        "Google Ads", "google", "cpc",
        (Campaign("G-3001", "PMax_Bestsellers", 0.6), Campaign("G-3002", "PMax_New_Arrivals", 0.4)),
        cpc=24.0, ctr=0.02, p_convert=0.038,
    ),
    "Meta Prospecting": ChannelSpec(
        "Meta Ads", "facebook", "paid_social",
        (Campaign("M-4001", "META_Prospecting_LAL", 0.55),
         Campaign("M-4002", "META_Prospecting_Interest_Coffee", 0.45)),
        cpc=19.0, ctr=0.011, p_convert=0.011,
    ),
    "Meta Retargeting": ChannelSpec(
        "Meta Ads", "facebook", "paid_social",
        (Campaign("M-5001", "META_Retargeting_ATC_7d", 0.6),
         Campaign("M-5002", "META_Retargeting_Viewers_30d", 0.4)),
        cpc=15.0, ctr=0.016, p_convert=0.065,
    ),
    "Apple Search Ads": ChannelSpec(
        "Apple Search Ads", "apple", "cpc",
        (Campaign("A-6001", "ASA_Brand", 0.5), Campaign("A-6002", "ASA_Generic", 0.5)),
        cpc=30.0, ctr=0.07, p_convert=0.045,
    ),
    "Affiliate": ChannelSpec(
        "Affiliate Network", "partner", "affiliate",
        (Campaign("F-7001", "AFF_Partner_Coupons", 0.6), Campaign("F-7002", "AFF_Partner_Content", 0.4)),
        cpc=17.0, ctr=0.03, p_convert=0.05,
    ),
    "Email": ChannelSpec(
        None, "newsletter", "email",
        (Campaign("E-8001", "EM_Weekly_Newsletter", 0.6), Campaign("E-8002", "EM_Winback_30d", 0.4)),
        cpc=0.0, ctr=0.0, p_convert=0.055,
    ),
    "Organic Search": ChannelSpec(None, "google", "organic", (Campaign("", "", 1.0),), 0.0, 0.0, 0.028),
    "Referral": ChannelSpec(None, "blog.example.com", "referral", (Campaign("", "", 1.0),), 0.0, 0.0, 0.03),
    "Direct": ChannelSpec(None, "(direct)", "(none)", (Campaign("", "", 1.0),), 0.0, 0.0, 0.055),
}

# Where journeys start: upper-funnel channels dominate
FIRST_TOUCH = {
    "Meta Prospecting": 0.24, "Google Search Generic": 0.17, "Organic Search": 0.15,
    "Google PMax": 0.10, "Affiliate": 0.06, "Apple Search Ads": 0.05, "Referral": 0.05,
    "Direct": 0.07, "Google Search Brand": 0.06, "Meta Retargeting": 0.02, "Email": 0.03,
}
# Where returning visitors come back from: lower-funnel channels dominate
RETURN_TOUCH = {
    "Meta Retargeting": 0.19, "Google Search Brand": 0.20, "Direct": 0.19, "Email": 0.12,
    "Organic Search": 0.09, "Google PMax": 0.08, "Apple Search Ads": 0.04,
    "Google Search Generic": 0.05, "Meta Prospecting": 0.03, "Affiliate": 0.01,
}
# Repeat purchases are driven by owned and brand channels
REPEAT_TOUCH = {
    "Email": 0.35, "Direct": 0.30, "Google Search Brand": 0.15,
    "Meta Retargeting": 0.12, "Organic Search": 0.08,
}

RENAMED_CAMPAIGN_ID = "M-4001"
RENAMED_TO = "META | Prospecting | Lookalike 1%"
TEST_CAMPAIGN = "test_campaign_do_not_use"


def _pick(rng: np.random.Generator, weights: dict[str, float]) -> str:
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return keys[rng.choice(len(keys), p=p / p.sum())]


def _messy(value: str, rng: np.random.Generator) -> str:
    """Return one of the inconsistent spellings real UTMs end up with."""
    if not value:
        return value
    variant = rng.integers(0, 6)
    return [value, value.lower(), value + " ", value.upper(), value.replace("_", "-"), " " + value][variant]


def _session_time(day: date, rng: np.random.Generator) -> datetime:
    """A local (IST) timestamp, weighted towards the evening."""
    hours = np.arange(24)
    profile = np.array([1, 0.6, 0.4, 0.3, 0.3, 0.5, 1, 2, 3, 3.5, 4, 4, 4, 4, 4, 4, 4.5,
                        5, 6, 7, 8, 8, 6, 3], dtype=float)
    hour = int(rng.choice(hours, p=profile / profile.sum()))
    return datetime.combine(day, datetime.min.time()) + timedelta(
        hours=hour, minutes=int(rng.integers(0, 60)), seconds=int(rng.integers(0, 60))
    )


def generate(
    out_dir: Path,
    *,
    users: int = 30_000,
    days: int = 60,
    start: date = date(2026, 7, 1),
    seed: int = 42,
) -> dict[str, int]:
    """Write raw_sessions.csv, raw_orders.csv and raw_ad_spend.csv to ``out_dir``."""
    rng = np.random.default_rng(seed)
    end = start + timedelta(days=days)  # exclusive
    rename_day = start + timedelta(days=days // 2)

    sessions: list[dict] = []
    orders: list[dict] = []

    def add_session(user_id: str, ts_ist: datetime, channel: str) -> None:
        spec = CHANNELS[channel]
        camp = spec.campaigns[rng.choice(len(spec.campaigns), p=[c.weight for c in spec.campaigns])]
        name = camp.name
        if camp.campaign_id == RENAMED_CAMPAIGN_ID and ts_ist.date() >= rename_day:
            name = RENAMED_TO
        if spec.platform and rng.random() < 0.004:
            name = TEST_CAMPAIGN
        medium = spec.medium
        if medium == "cpc" and rng.random() < 0.1:
            medium = rng.choice(["CPC", "paid"])
        sessions.append({
            "session_id": f"S{len(sessions) + 1:07d}",
            "user_id": user_id,
            "session_start_utc": (ts_ist - IST_OFFSET).strftime("%Y-%m-%d %H:%M:%S"),
            "source": spec.source if rng.random() > 0.15 else spec.source.title(),
            "medium": medium,
            "campaign": _messy(name, rng),
            "campaign_id": camp.campaign_id,  # dropped before writing; used for spend
            "channel_truth": channel,          # dropped before writing
            "device": "mobile" if rng.random() < 0.72 else "desktop",
        })

    def add_order(user_id: str, ts_ist: datetime, repeat: bool) -> None:
        mean = 1100 if repeat else 950
        revenue = float(np.round(rng.lognormal(np.log(mean) - 0.08, 0.4), 0))
        orders.append({
            "order_id": f"ORD-{len(orders) + 100001}",
            "user_id": user_id,
            "order_ts_utc": (ts_ist - IST_OFFSET).strftime("%Y-%m-%d %H:%M:%S"),
            "revenue": revenue,
        })

    def journey(user_id: str, day: date, touch_dist: dict[str, float], max_touches: int,
                boost: float, repeat: bool) -> datetime | None:
        """Simulate touches until conversion or drop-off. Returns order time if converted."""
        ts = _session_time(day, rng)
        dist = touch_dist
        for i in range(max_touches):
            if ts.date() >= end:
                return None
            channel = _pick(rng, dist)
            add_session(user_id, ts, channel)
            p = min(0.6, CHANNELS[channel].p_convert * boost * (1 + 0.15 * i))
            if rng.random() < p:
                order_ts = ts + timedelta(minutes=int(rng.integers(3, 40)))
                add_order(user_id, order_ts, repeat)
                return order_ts
            if rng.random() > 0.62:
                return None
            gap = timedelta(days=float(rng.exponential(2.5)), hours=float(rng.uniform(0, 6)))
            ts = ts + gap
            dist = RETURN_TOUCH if not repeat else REPEAT_TOUCH
        return None

    for n in range(users):
        user_id = f"U{n + 1:06d}"
        first_day = start + timedelta(days=int(rng.integers(0, days)))
        converted_at = journey(user_id, first_day, FIRST_TOUCH, 8, 1.0, repeat=False)
        # Converted customers may come back for more
        while converted_at is not None and rng.random() < 0.42:
            next_day = (converted_at + timedelta(days=int(rng.integers(6, 25)))).date()
            converted_at = journey(user_id, next_day, REPEAT_TOUCH, 3, 1.6, repeat=True)

    sessions_df = pd.DataFrame(sessions)
    orders_df = pd.DataFrame(orders)
    spend_df = _build_spend(sessions_df, rng, rename_day)

    out_dir.mkdir(parents=True, exist_ok=True)
    sessions_df.drop(columns=["campaign_id", "channel_truth"]).to_csv(out_dir / "raw_sessions.csv", index=False)
    orders_df.to_csv(out_dir / "raw_orders.csv", index=False)
    spend_df.to_csv(out_dir / "raw_ad_spend.csv", index=False)
    return {"sessions": len(sessions_df), "orders": len(orders_df), "spend_rows": len(spend_df)}


def _build_spend(sessions: pd.DataFrame, rng: np.random.Generator, rename_day: date) -> pd.DataFrame:
    """Daily campaign spend, derived from tracked paid clicks plus untracked ones."""
    paid = sessions[sessions["channel_truth"].map(lambda c: CHANNELS[c].platform is not None)].copy()
    paid["date"] = (pd.to_datetime(paid["session_start_utc"]) + IST_OFFSET).dt.date
    daily = paid.groupby(["date", "channel_truth", "campaign_id"]).size().reset_index(name="tracked")

    rows = []
    names = {c.campaign_id: c.name for spec in CHANNELS.values() for c in spec.campaigns}
    for r in daily.itertuples(index=False):
        spec = CHANNELS[r.channel_truth]
        clicks = int(round(r.tracked / 0.85 * rng.uniform(0.95, 1.05)))  # ~15% of clicks never land
        spend = round(clicks * spec.cpc * float(rng.lognormal(0, 0.08)), 2)
        name = names[r.campaign_id]
        if r.campaign_id == RENAMED_CAMPAIGN_ID and r.date >= rename_day:
            name = RENAMED_TO
        rows.append({
            "date": r.date.isoformat(),
            "platform": spec.platform,
            "campaign_id": r.campaign_id,
            "campaign_name": name,
            "impressions": int(clicks / spec.ctr) if spec.ctr else 0,
            "clicks": clicks,
            "spend": spend,
        })
    spend = pd.DataFrame(rows).sort_values(["date", "platform", "campaign_id"]).reset_index(drop=True)

    # Re-pulled rows with restated spend, appended later in the file (later row wins)
    restated = spend.sample(frac=0.03, random_state=int(rng.integers(0, 1_000_000))).copy()
    restated["spend"] = (restated["spend"] * 1.02).round(2)
    return pd.concat([spend, restated], ignore_index=True)

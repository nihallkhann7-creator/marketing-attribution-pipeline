"""Turn attribution results into channel performance tables, a chart and a Markdown report."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import markov, models  # noqa: E402
from .config import ALL_MODELS, PER_TOUCH_MODELS, Settings  # noqa: E402

MODEL_LABELS = {
    "first_touch": "First touch",
    "last_touch": "Last touch",
    "last_non_direct": "Last non-direct",
    "linear": "Linear",
    "time_decay": "Time decay",
    "position_based": "Position based",
    "markov": "Markov",
}


def attribute(conn: sqlite3.Connection, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every model. Returns (per-touch credits, channel summary for all models)."""
    touches = pd.read_sql("SELECT * FROM mart_conversion_touchpoints", conn)
    nulls = pd.read_sql("SELECT * FROM mart_null_paths", conn)

    credits = pd.concat(
        [models.touch_credits(touches, m, settings.time_decay_half_life_days) for m in PER_TOUCH_MODELS],
        ignore_index=True,
    )
    summary = pd.concat([models.summarise(credits), markov.summarise(touches, nulls)], ignore_index=True)

    credits.to_sql("attribution_touch_credits", conn, if_exists="replace", index=False)
    summary.to_sql("attribution_channel_summary", conn, if_exists="replace", index=False)
    return credits, summary


def channel_performance(conn: sqlite3.Connection, summary: pd.DataFrame) -> pd.DataFrame:
    spend = pd.read_sql("SELECT channel, SUM(spend) AS spend FROM mart_daily_channel_spend GROUP BY channel", conn)
    perf = summary.merge(spend, on="channel", how="left")
    perf["spend"] = perf["spend"].fillna(0.0)
    paid = perf["spend"] > 0
    perf["cac"] = np.where(paid & (perf["new_customers"] > 0), perf["spend"] / perf["new_customers"], np.nan)
    perf["roas"] = np.where(paid, perf["revenue"] / perf["spend"].where(paid, 1), np.nan)
    perf = perf.sort_values(["model", "spend", "revenue"], ascending=[True, False, False])
    return perf[["model", "channel", "spend", "orders", "new_customers", "revenue", "cac", "roas"]]


def daily_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        """
        WITH spend AS (
            SELECT spend_date AS d, SUM(spend) AS spend FROM mart_daily_channel_spend GROUP BY spend_date
        )
        SELECT o.order_date AS date,
               ROUND(COALESCE(s.spend, 0), 2) AS spend,
               o.orders, o.new_customers, o.revenue,
               ROUND(COALESCE(s.spend, 0) / NULLIF(o.new_customers, 0), 2) AS blended_cac,
               ROUND(o.revenue / NULLIF(s.spend, 0), 2) AS blended_roas
        FROM mart_daily_orders o
        LEFT JOIN spend s ON s.d = o.order_date
        ORDER BY o.order_date
        """,
        conn,
    )


def _fmt_inr(x: float) -> str:
    if pd.isna(x):
        return "—"
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


def _md_table(df: pd.DataFrame, numeric: bool = True) -> str:
    cols = list(df.columns)
    align = ["---" if i == 0 or not numeric else "---:" for i in range(len(cols))]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(align) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def comparison_table(perf: pd.DataFrame, metric: str) -> pd.DataFrame:
    pivot = perf.pivot_table(index="channel", columns="model", values=metric, aggfunc="sum").fillna(0)
    pivot = pivot[[m for m in ALL_MODELS if m in pivot.columns]]
    return pivot.sort_values("last_touch", ascending=False)


def chart(pivot: pd.DataFrame, path: Path) -> None:
    models_shown = ["last_touch", "first_touch", "position_based", "markov"]
    data = pivot[models_shown]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    y = np.arange(len(data))
    h = 0.2
    colours = ["#4C6EF5", "#F59F00", "#12B886", "#E64980"]
    for i, (model, colour) in enumerate(zip(models_shown, colours)):
        ax.barh(y + (i - 1.5) * h, data[model], height=h, label=MODEL_LABELS[model], color=colour)
    ax.set_yticks(y, data.index)
    ax.invert_yaxis()
    ax.set_xlabel("Attributed new customers")
    ax.set_title("Same customers, different stories: new-customer credit by attribution model")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def insights(perf: pd.DataFrame) -> list[str]:
    """A few plain-English findings, computed from the results rather than written by hand."""
    out = []
    pivot = comparison_table(perf, "new_customers")
    paid = perf.loc[perf["spend"] > 0, "channel"].unique()
    p = pivot.loc[pivot.index.isin(paid)]
    change = ((p["markov"] - p["last_touch"]) / p["last_touch"].replace(0, np.nan)).dropna()
    if not change.empty:
        up, down = change.idxmax(), change.idxmin()
        out.append(
            f"**{up}** gains the most when moving from last-touch to Markov "
            f"({p.loc[up, 'last_touch']:.0f} → {p.loc[up, 'markov']:.0f} new customers, {change[up]:+.0%}). "
            "Last-click undervalues channels that open journeys."
        )
        out.append(
            f"**{down}** loses the most ({p.loc[down, 'last_touch']:.0f} → {p.loc[down, 'markov']:.0f}, "
            f"{change[down]:+.0%}): it often closes journeys that other channels started."
        )
    cac = perf[(perf["spend"] > 0)].pivot_table(index="channel", columns="model", values="cac")
    if {"last_touch", "markov"} <= set(cac.columns):
        spread = (cac[["last_touch", "markov"]].max(axis=1) / cac[["last_touch", "markov"]].min(axis=1)).dropna()
        if not spread.empty:
            ch = spread.idxmax()
            out.append(
                f"CAC for **{ch}** ranges from {_fmt_inr(cac.loc[ch, ['last_touch', 'markov']].min())} to "
                f"{_fmt_inr(cac.loc[ch, ['last_touch', 'markov']].max())} depending on the model. "
                "Budget decisions on this channel are the most model-sensitive."
            )
    return out


def write_report(conn: sqlite3.Connection, settings: Settings, summary: pd.DataFrame,
                 quality: pd.DataFrame | None = None) -> dict[str, Path]:
    out = settings.output_dir
    out.mkdir(parents=True, exist_ok=True)

    perf = channel_performance(conn, summary)
    daily = daily_summary(conn)
    pivot_new = comparison_table(perf, "new_customers")

    perf.round(2).to_csv(out / "channel_performance.csv", index=False)
    daily.to_csv(out / "daily_summary.csv", index=False)
    pivot_new.round(1).to_csv(out / "model_comparison_new_customers.csv")
    chart(pivot_new, out / "model_comparison.png")

    totals = daily[["spend", "orders", "new_customers", "revenue"]].sum()
    lines = [
        "# Attribution report: Brewline (synthetic data)",
        "",
        f"Period **{daily['date'].min()} to {daily['date'].max()}** (IST) · "
        f"lookback window **{settings.lookback_days} days** · "
        f"time-decay half-life **{settings.time_decay_half_life_days:g} days**",
        "",
        "## Headline",
        "",
        _md_table(pd.DataFrame([{
            "Spend": _fmt_inr(totals["spend"]),
            "Orders": f"{totals['orders']:,.0f}",
            "New customers": f"{totals['new_customers']:,.0f}",
            "Revenue": _fmt_inr(totals["revenue"]),
            "Blended CAC": _fmt_inr(totals["spend"] / totals["new_customers"]),
            "Blended ROAS": f"{totals['revenue'] / totals['spend']:.2f}x",
        }])),
        "",
        "## What the models disagree on",
        "",
        *[f"- {line}" for line in insights(perf)],
        "",
        "![Model comparison](model_comparison.png)",
        "",
        "## New customers by channel and model",
        "",
        _md_table(pivot_new.rename(columns=MODEL_LABELS).round(0).astype(int).reset_index()),
        "",
        "## CAC by paid channel and model",
        "",
    ]
    cac = perf[perf["spend"] > 0].pivot_table(index="channel", columns="model", values="cac")
    cac = cac[[m for m in ALL_MODELS if m in cac.columns]].rename(columns=MODEL_LABELS)
    lines.append(_md_table(cac.map(_fmt_inr).reset_index()))
    lines += ["", "## ROAS by paid channel and model", ""]
    roas = perf[perf["spend"] > 0].pivot_table(index="channel", columns="model", values="roas")
    roas = roas[[m for m in ALL_MODELS if m in roas.columns]].rename(columns=MODEL_LABELS)
    lines.append(_md_table(roas.map(lambda v: f"{v:.2f}x").reset_index()))
    if quality is not None:
        lines += ["", "## Data-quality checks", "", _md_table(quality, numeric=False)]
    lines.append("")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return {"report": out / "report.md", "chart": out / "model_comparison.png"}

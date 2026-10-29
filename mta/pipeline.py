"""End-to-end run: generate → load → stage → attribute → check → report."""

from __future__ import annotations

import time
from datetime import date

import pandas as pd

from . import etl, generate, quality, reports
from .config import Settings


class QualityGateError(RuntimeError):
    pass


def run(settings: Settings, *, regenerate: bool = False, users: int = 50_000, days: int = 60,
        start: date = date(2026, 7, 1), seed: int = 42, log=print) -> dict:
    timings: dict[str, float] = {}

    def step(name, fn, *args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        timings[name] = time.perf_counter() - t0
        log(f"  ✓ {name:<10} {timings[name]:6.2f}s")
        return result

    raw_present = all((settings.raw_dir / f).exists() for f, _, _ in etl.RAW_TABLES.values())
    if regenerate or not raw_present:
        gen = step("generate", generate.generate, settings.raw_dir, users=users, days=days, start=start, seed=seed)
        log(f"    {gen['sessions']:,} sessions · {gen['orders']:,} orders · {gen['spend_rows']:,} spend rows")

    etl_stats = step("load", etl.run_etl, settings)
    conn = etl.connect(settings.db_path)
    try:
        _, summary = step("attribute", reports.attribute, conn, settings)
        checks = step("checks", quality.run_checks, conn, etl_stats["load"])
        files = step("report", reports.write_report, conn, settings, summary, checks)
    finally:
        conn.close()

    checks.to_csv(settings.output_dir / "quality_checks.csv", index=False)
    with pd.option_context("display.max_colwidth", 90, "display.width", 160):
        log("\n" + checks.to_string(index=False))
    if (checks["status"] == "FAIL").any():
        raise QualityGateError("One or more data-quality checks failed; see output/quality_checks.csv")
    return {"etl": etl_stats, "checks": checks, "files": files, "timings": timings}

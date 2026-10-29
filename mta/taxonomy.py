"""Rule-based channel resolver driven by config/taxonomy.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import TAXONOMY_PATH

_SEPARATORS = re.compile(r"[\s\-|]+")
_UNDERSCORES = re.compile(r"_+")


def normalise(value: object) -> str:
    """Lower-case, trim, and collapse spaces / hyphens / pipes into single underscores.

    >>> normalise("  META | Prospecting | Lookalike 1% ")
    'meta_prospecting_lookalike_1%'
    """
    if value is None or (isinstance(value, float) and value != value):  # None or NaN
        return ""
    text = _SEPARATORS.sub("_", str(value).strip().lower())
    return _UNDERSCORES.sub("_", text).strip("_")


@dataclass(frozen=True)
class Rule:
    channel: str
    paid: bool
    source: re.Pattern | None
    medium: re.Pattern | None
    campaign: re.Pattern | None

    def matches(self, source: str, medium: str, campaign: str) -> bool:
        return all(
            pattern is None or pattern.search(value)
            for pattern, value in ((self.source, source), (self.medium, medium), (self.campaign, campaign))
        )


class Taxonomy:
    def __init__(self, path: Path = TAXONOMY_PATH):
        cfg = yaml.safe_load(Path(path).read_text())
        self.platform_sources: dict[str, str] = cfg["platform_sources"]
        self.rules = [
            Rule(
                channel=r["channel"],
                paid=bool(r["paid"]),
                source=re.compile(r["source"]) if "source" in r else None,
                medium=re.compile(r["medium"]) if "medium" in r else None,
                campaign=re.compile(r["campaign"]) if "campaign" in r else None,
            )
            for r in cfg["rules"]
        ]
        self.fallback = (cfg["fallback"]["channel"], bool(cfg["fallback"]["paid"]))

    def resolve(self, source: object, medium: object, campaign: object) -> tuple[str, bool]:
        """Return (channel, is_paid) for one UTM triple. First matching rule wins."""
        s, m, c = normalise(source), normalise(medium), normalise(campaign)
        for rule in self.rules:
            if rule.matches(s, m, c):
                return rule.channel, rule.paid
        return self.fallback

    def resolve_spend(self, platform: str, campaign_name: object) -> tuple[str, bool]:
        """Resolve an ad-platform spend row, using the platform's UTM source and medium."""
        source = self.platform_sources.get(platform, platform)
        medium = "affiliate" if source == "partner" else "cpc"
        return self.resolve(source, medium, campaign_name)


@lru_cache(maxsize=1)
def default_taxonomy() -> Taxonomy:
    return Taxonomy()

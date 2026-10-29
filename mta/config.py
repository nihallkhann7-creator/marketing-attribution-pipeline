"""Shared settings and paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
TAXONOMY_PATH = ROOT / "config" / "taxonomy.yaml"

# Channels that should never win "last non-direct" credit
DIRECT_CHANNELS = frozenset({"Direct", "Direct (untracked)"})

PER_TOUCH_MODELS = (
    "first_touch",
    "last_touch",
    "last_non_direct",
    "linear",
    "time_decay",
    "position_based",
)
ALL_MODELS = PER_TOUCH_MODELS + ("markov",)


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: ROOT / "data")
    output_dir: Path = field(default_factory=lambda: ROOT / "output")
    lookback_days: int = 30
    time_decay_half_life_days: float = 7.0

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "warehouse.db"

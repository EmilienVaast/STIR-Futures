from __future__ import annotations

import os
from pathlib import Path
from datetime import date

import pandas as pd


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------


def resolve_data_dir() -> Path:
    env_path = os.getenv("STIR_DATA_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        path = Path(__file__).resolve().parents[1] / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Rate data fetch window
# ---------------------------------------------------------------------------

DATA_START_DATE = "2024-12-01"


# ---------------------------------------------------------------------------
# Fed Funds target range (starting point for scenarios)
# ---------------------------------------------------------------------------

FED_FUNDS_LOWER = 3.50
FED_FUNDS_UPPER = 3.75
FED_FUNDS_MIDPOINT = (FED_FUNDS_LOWER + FED_FUNDS_UPPER) / 2.0


# ---------------------------------------------------------------------------
# FOMC meeting end dates (decision day) for 2026
# ---------------------------------------------------------------------------

FOMC_END_DATES_2026 = [
    pd.Timestamp("2026-01-28"),
    pd.Timestamp("2026-03-18"),
    pd.Timestamp("2026-04-29"),
    pd.Timestamp("2026-06-17"),
    pd.Timestamp("2026-07-29"),
    pd.Timestamp("2026-09-16"),
    pd.Timestamp("2026-10-28"),
    pd.Timestamp("2026-12-09"),
]


# ---------------------------------------------------------------------------
# Scenario assumptions
# ---------------------------------------------------------------------------

CUT_INDICES = {0, 2, 4, 6}  # which FOMC meetings have a cut (0-indexed)
CUT_SIZE_BPS = 25
EFFECTIVE_LAG_DAYS = 1  # rate change effective day after FOMC decision


# ---------------------------------------------------------------------------
# SOFR spread assumptions (over EFFR)
# ---------------------------------------------------------------------------

BASE_SPREAD_BPS = 3.0
JUMP_BPS = 10.0  # extra spread on mid-month and month-end


# ---------------------------------------------------------------------------
# Official Barchart prices for 2025 (used for model validation)
# ---------------------------------------------------------------------------

OFFICIAL_SR3_2025 = [
    95.6390, 95.6455, 95.6577, 95.6588, 95.6511,
    95.6240, 95.6788, 95.7690, 95.9134, 96.0764,
]

OFFICIAL_SR1_2025 = [
    95.6825, 95.6575, 95.6710, 95.6570, 95.6950, 95.6850,
    95.6650, 95.6525, 95.7030, 95.8075, 96.0025, 96.2180,
]

OFFICIAL_ZQ_2025 = {
    "ZQF5": 95.6725,
    "ZQG5": 95.6700, "ZQH5": 95.6700, "ZQJ5": 95.6700, "ZQK5": 95.6700,
    "ZQM5": 95.6700, "ZQN5": 95.6700, "ZQQ5": 95.6700,
    "ZQU5": 95.7750,
    "ZQV5": 95.9125,
    "ZQX5": 96.1225,
    "ZQZ5": 96.2790,
}

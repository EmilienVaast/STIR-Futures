"""
ZQ (30-Day Fed Funds Futures) Pricing Module
=============================================

CME 30-Day Federal Funds futures (ZQ) settle at the arithmetic average of
daily EFFR rates over the contract month. Settlement price = 100 - avg_EFFR.

References:
    - CME Group: 30-Day Federal Funds Futures Contract Specs
    - Arithmetic averaging methodology (same as SR1)

Sections:
    1. Core Settlement Logic
    2. Historical Table Builders (2025)
    3. Expected/Forward Table Builders (2026)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import pandas as pd
import QuantLib as ql

from stir_futures.config import CME_MONTH_CODES
from stir_futures.rounding import round_half_up
from stir_futures.calendars import last_business_day_of_month

if TYPE_CHECKING:
    from typing import Optional


# =============================================================================
# SECTION 1: Core Settlement Logic
# =============================================================================


def zq_final_settlement_from_effr(
    effr_df: pd.DataFrame,
    year: int,
    month: int,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[pd.Timestamp]]:
    """
    Compute ZQ final settlement price from historical EFFR rates.

    The ZQ contract settles at the arithmetic average of daily EFFR rates
    over all calendar days in the contract month. Weekend/holiday rates are
    forward-filled from the previous business day's fixing.

    Args:
        effr_df: DataFrame with columns ['effectiveDate', 'rate'].
        year: Contract year (e.g., 2025).
        month: Contract month (1-12).

    Returns:
        Tuple of (avg_raw, avg_rounded, settlement_price, first_missing_date).
        Returns (None, None, None, missing_date) if data is incomplete.

    Example:
        >>> raw, rnd, settle, _ = zq_final_settlement_from_effr(effr_df, 2025, 6)
        >>> print(f"ZQM5 settles at {settle:.4f}")
    """
    start = pd.Timestamp(year=year, month=month, day=1)
    end = (start + pd.offsets.MonthEnd(1)).normalize()
    cal_days = pd.date_range(start, end, freq="D")

    # Forward-fill rates to cover weekends and holidays
    rates = effr_df.set_index("effectiveDate")["rate"].sort_index()
    daily_rate = rates.reindex(cal_days, method="ffill")

    if daily_rate.isna().any():
        missing = daily_rate[daily_rate.isna()].index
        return None, None, None, missing[0]

    avg_raw = float(daily_rate.mean())
    avg_rnd = round_half_up(avg_raw, 3)  # CME rounds to 0.001%
    settle = round_half_up(100.0 - avg_rnd, 4)  # Price to 0.0001

    return avg_raw, avg_rnd, settle, None


def _format_diff_bps(model: Optional[float], official: Optional[float]) -> str:
    """Format difference in basis points between model and official price."""
    if model is None or not isinstance(official, (float, int)):
        return "N/A"
    return f"{abs(model - official) * 100.0:.2f}"


# =============================================================================
# SECTION 2: Historical Table Builders (2025)
# =============================================================================


def build_zq_2025_table(
    effr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_prices: dict[str, float],
) -> pd.DataFrame:
    """
    Build a summary table of all 2025 ZQ contract settlements.

    Generates a DataFrame comparing model-calculated settlements against
    official CME/Barchart prices for expired contracts.

    Args:
        effr_df: Historical EFFR rates with ['effectiveDate', 'rate'].
        asof: Reference date for determining expiry status.
        cal: QuantLib business day calendar.
        official_prices: Mapping of contract codes (e.g., "ZQF5") to official prices.

    Returns:
        DataFrame with columns: Contract, Contract Month, Ref Start, Ref End,
        Last Trading Day, Status, Avg EFFR (raw/rnd %), Model Settle,
        Official-Barchart, Diff (bps).
    """
    YEAR = 2025
    rows = []

    for month in range(1, 13):
        code = f"ZQ{CME_MONTH_CODES[month]}5"
        month_start = pd.Timestamp(year=YEAR, month=month, day=1)
        month_end = (month_start + pd.offsets.MonthEnd(1)).normalize()
        ltd = last_business_day_of_month(YEAR, month, cal=cal)

        avg_raw, avg_rnd, model_settle, _ = zq_final_settlement_from_effr(effr_df, YEAR, month)
        official = official_prices.get(code)

        row = {
            "Contract": code,
            "Contract Month": month_start.strftime("%b %Y"),
            "Ref Start": month_start.date().isoformat(),
            "Ref End": month_end.date().isoformat(),
            "Last Trading Day": ltd.date().isoformat(),
            "Official-Barchart": f"{official:.4f}" if isinstance(official, (float, int)) else "—",
        }

        if model_settle is None:
            row.update({
                "Status": "No Data",
                "Avg EFFR (raw %)": "—",
                "Avg EFFR (rnd %)": "—",
                "Model Settle": "No Data",
                "Diff (bps)": "N/A",
            })
        else:
            row.update({
                "Status": "Expired" if ltd < asof else "Not expired",
                "Avg EFFR (raw %)": f"{avg_raw:.6f}",
                "Avg EFFR (rnd %)": f"{avg_rnd:.3f}",
                "Model Settle": f"{model_settle:.4f}",
                "Diff (bps)": _format_diff_bps(model_settle, official),
            })

        rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# SECTION 3: Expected/Forward Table Builders (2026)
# =============================================================================


def build_expected_zq_2026_table(
    mid_path_2026: pd.Series,
    start_mid: float,
    cal: ql.Calendar,
) -> pd.DataFrame:
    """
    Build expected ZQ settlements for all 2026 contracts.

    Projects settlement prices based on an EFFR path derived from the Fed
    Funds target rate midpoint and FOMC meeting schedule.

    Args:
        mid_path_2026: Daily EFFR path projection indexed by date (full year).
        start_mid: Starting midpoint rate (%) for display in output.
        cal: QuantLib business day calendar.

    Returns:
        DataFrame with expected settlement prices for 2026 ZQ contracts.

    Note:
        The mid_path_2026 should incorporate expected FOMC rate decisions
        as step functions at each meeting date.
    """
    YEAR = 2026
    rows = []

    for month in range(1, 13):
        code = f"ZQ{CME_MONTH_CODES[month]}26"
        month_start = pd.Timestamp(year=YEAR, month=month, day=1)
        month_end = (month_start + pd.offsets.MonthEnd(1)).normalize()
        ltd = last_business_day_of_month(YEAR, month, cal=cal)

        cal_days = pd.date_range(month_start, month_end, freq="D")
        avg_raw = float(mid_path_2026.reindex(cal_days).mean())
        avg_rnd = round_half_up(avg_raw, 3)
        price = round_half_up(100.0 - avg_rnd, 4)

        rows.append({
            "Contract": code,
            "Contract Month": month_start.strftime("%b %Y"),
            "Ref Start": month_start.date().isoformat(),
            "Ref End": month_end.date().isoformat(),
            "Last Trading Day": ltd.date().isoformat(),
            "Status": "Expected",
            "Start Midpoint (%)": f"{start_mid:.3f}",
            "Avg EFFR (raw %)": f"{avg_raw:.6f}",
            "Avg EFFR (rnd %)": f"{avg_rnd:.3f}",
            "Expected Price": f"{price:.4f}",
        })

    return pd.DataFrame(rows)

"""
SR1 (One-Month SOFR Futures) Pricing Module
============================================

CME One-Month SOFR futures (SR1) settle at the arithmetic average of daily
SOFR rates over the contract month. Final settlement price = 100 - avg_SOFR.

References:
    - CME Group: One-Month SOFR Futures Contract Specs
    - Arithmetic averaging (not compounded like SR3)

Sections:
    1. Core Settlement Logic
    2. Historical Table Builders (2025)
    3. Expected/Forward Table Builders (2026)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import QuantLib as ql

from stir_futures.config import CME_MONTH_CODES
from stir_futures.rounding import round_half_up
from stir_futures.calendars import month_start_end, last_business_day_of_month
from stir_futures.scenarios import build_expected_sofr_daily_for_month

if TYPE_CHECKING:
    from typing import Optional


# =============================================================================
# SECTION 1: Core Settlement Logic
# =============================================================================


def sr1_final_settlement_from_sofr(
    sofr_df: pd.DataFrame,
    delivery_year: int,
    delivery_month: int,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute SR1 final settlement price from historical SOFR rates.

    The SR1 contract settles at the arithmetic average of daily SOFR rates
    over all calendar days in the delivery month. Weekend/holiday rates are
    forward-filled from the previous business day's fixing.

    Args:
        sofr_df: DataFrame with columns ['effectiveDate', 'rate'].
        delivery_year: Contract delivery year (e.g., 2025).
        delivery_month: Contract delivery month (1-12).

    Returns:
        Tuple of (settlement_price, avg_raw, avg_rounded).
        Returns (None, None, None) if data is incomplete.

    Example:
        >>> settle, raw, rnd = sr1_final_settlement_from_sofr(sofr_df, 2025, 6)
        >>> print(f"SR1M5 settles at {settle:.4f}")
    """
    month_start, month_end = month_start_end(delivery_year, delivery_month)
    cal_days = pd.date_range(month_start, month_end, freq="D")

    # Forward-fill rates to cover weekends and holidays
    rates = sofr_df.set_index("effectiveDate")["rate"].sort_index()
    daily_rates = rates.reindex(cal_days, method="ffill")

    if daily_rates.isna().any():
        return None, None, None

    avg_raw = float(daily_rates.mean())
    avg_rnd = round_half_up(avg_raw, 3)  # CME rounds to 0.001%
    settle = round_half_up(100.0 - avg_rnd, 3)

    return settle, avg_raw, avg_rnd


def _format_diff_bps(model: Optional[float], official: Optional[float]) -> str:
    """Format difference in basis points between model and official price."""
    if model is None or not isinstance(official, (float, int)):
        return "N/A"
    return f"{abs(model - official) * 100.0:.2f}"


# =============================================================================
# SECTION 2: Historical Table Builders (2025)
# =============================================================================


def build_sr1_2025_table(
    sofr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_map: dict[str, float],
) -> pd.DataFrame:
    """
    Build a summary table of all 2025 SR1 contract settlements.

    Generates a DataFrame comparing model-calculated settlements against
    official CME/Barchart prices for expired contracts, and marks active
    contracts as "Not expired".

    Args:
        sofr_df: Historical SOFR rates with ['effectiveDate', 'rate'].
        asof: Reference date for determining expiry status.
        cal: QuantLib business day calendar (typically US Government).
        official_map: Mapping of contract codes (e.g., "SR1F5") to official prices.

    Returns:
        DataFrame with columns: Contract, Contract Month, Ref Start, Ref End,
        Last Trading Day, Status, Avg SOFR (raw/rnd %), Model Settle,
        Official-Barchart, Diff (bps).
    """
    YEAR = 2025
    rows = []

    for month in range(1, 13):
        code = f"SR1{CME_MONTH_CODES[month]}5"
        month_label = pd.Timestamp(YEAR, month, 1).strftime("%b %Y")
        ref_start, ref_end = month_start_end(YEAR, month)
        ltd = last_business_day_of_month(YEAR, month, cal=cal)

        expired = ltd < asof
        official = official_map.get(code)

        row = {
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start": str(ref_start.date()),
            "Ref End": str(ref_end.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": "Expired" if expired else "Not expired",
            "Official-Barchart": f"{official:.4f}" if isinstance(official, (float, int)) else "—",
        }

        if not expired:
            row.update({
                "Avg SOFR (raw %)": "—",
                "Avg SOFR (rnd %)": "—",
                "Model Settle": "Not expired",
                "Diff (bps)": "N/A",
            })
        else:
            settle, avg_raw, avg_rnd = sr1_final_settlement_from_sofr(sofr_df, YEAR, month)
            if settle is None:
                row.update({
                    "Avg SOFR (raw %)": "—",
                    "Avg SOFR (rnd %)": "—",
                    "Model Settle": "No Data",
                    "Diff (bps)": "N/A",
                })
            else:
                row.update({
                    "Avg SOFR (raw %)": f"{avg_raw:.5f}",
                    "Avg SOFR (rnd %)": f"{avg_rnd:.3f}",
                    "Model Settle": f"{settle:.4f}",
                    "Diff (bps)": _format_diff_bps(settle, official),
                })

        rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# SECTION 3: Expected/Forward Table Builders (2026)
# =============================================================================


def build_sr1_2026_expected_table(
    effr_path_2026: pd.Series,
    cal: ql.Calendar,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> pd.DataFrame:
    """
    Build expected SR1 settlements for 2026 using projected EFFR path.

    Projects SOFR from EFFR using spread assumptions (base spread + month-end
    jump effects), then computes arithmetic average settlement prices.

    Args:
        effr_path_2026: Daily EFFR path projection indexed by date.
        cal: QuantLib business day calendar.
        base_spread_bps: Base SOFR-EFFR spread in basis points (default: 3.0).
        jump_bps: Additional spread on month-end/mid-month dates (default: 10.0).

    Returns:
        DataFrame with expected settlement prices and rate details.

    Note:
        Jump days occur mid-month (typically 15th) and on last business day,
        reflecting typical repo market dynamics around reserve maintenance.
    """
    YEAR = 2026
    rows = []

    for month in range(1, 13):
        code = f"SR1{CME_MONTH_CODES[month]}6"
        month_label = pd.Timestamp(YEAR, month, 1).strftime("%b %Y")
        ref_start, ref_end = month_start_end(YEAR, month)
        ltd = last_business_day_of_month(YEAR, month, cal=cal)

        # Build projected daily SOFR for the month
        sofr_daily = build_expected_sofr_daily_for_month(
            effr_daily_path=effr_path_2026,
            year=YEAR,
            month=month,
            cal=cal,
            base_spread_bps=base_spread_bps,
            jump_bps=jump_bps,
        )

        avg_raw = float(sofr_daily.mean())
        avg_rnd = round_half_up(avg_raw, 3)
        price = round_half_up(100.0 - avg_rnd, 3)

        # Find jump days for display
        mid_jump_candidates = sofr_daily.index[sofr_daily.index.day.isin([15, 16, 17])]
        mid_jump_day = mid_jump_candidates.min().date().isoformat() if len(mid_jump_candidates) > 0 else "—"

        rows.append({
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start": str(ref_start.date()),
            "Ref End": str(ref_end.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": "Expected",
            "Mid-month jump day": mid_jump_day,
            "Last BD jump day": ltd.date().isoformat(),
            "Avg SOFR (raw %)": f"{avg_raw:.6f}",
            "Avg SOFR (rnd %)": f"{avg_rnd:.3f}",
            "Expected Settle": f"{price:.4f}",
        })

    return pd.DataFrame(rows)

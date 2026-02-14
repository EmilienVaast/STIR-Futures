"""
SR3 (Three-Month SOFR Futures) Pricing Module
==============================================

CME Three-Month SOFR futures (SR3) settle at the compounded average of daily
SOFR rates over the reference quarter (IMM-to-IMM period). This uses the
standard compounding formula: R = (Product((1 + ri*di/360)) - 1) * 360/D * 100

References:
    - CME Group: Three-Month SOFR Futures Contract Specs
    - ISDA SOFR Compounding methodology

Sections:
    1. Reference Period Utilities
    2. Core Settlement Logic
    3. Historical Table Builders (2025)
    4. Expected/Forward Table Builders (2026)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd
import QuantLib as ql

from stir_futures.rounding import round_half_up
from stir_futures.config import CME_MONTH_CODES
from stir_futures.calendars import third_wednesday, add_months
from stir_futures.scenarios import expected_sofr_on_date

if TYPE_CHECKING:
    pass  # Future type hints


# =============================================================================
# SECTION 1: Reference Period Utilities
# =============================================================================


def sr3_reference_quarter(
    contract_year: int,
    contract_month: int,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Compute the IMM-to-IMM reference quarter for an SR3 contract.

    SR3 contracts reference the period from the 3rd Wednesday of the contract
    month (inclusive) to the 3rd Wednesday three months forward (exclusive).

    Args:
        contract_year: Contract year (e.g., 2025).
        contract_month: Contract delivery month (1-12, must be IMM: 3,6,9,12).

    Returns:
        Tuple of (start_date_inclusive, end_date_exclusive).

    Example:
        >>> start, end = sr3_reference_quarter(2025, 3)  # SR3H5
        >>> print(f"Mar-25 quarter: {start.date()} to {end.date()}")
    """
    start_incl = third_wednesday(contract_year, contract_month)
    end_year, end_month = add_months(contract_year, contract_month, 3)
    end_excl = third_wednesday(end_year, end_month)
    return start_incl, end_excl


def sr3_last_trading_day(
    contract_year: int,
    contract_month: int,
    cal: ql.Calendar,
) -> pd.Timestamp:
    """
    Determine the last trading day for an SR3 contract.

    SR3 contracts stop trading on the business day preceding the 3rd Wednesday
    of the delivery month (i.e., the IMM date three months forward).

    Args:
        contract_year: Contract year.
        contract_month: Contract month (IMM month).
        cal: QuantLib calendar for business day determination.

    Returns:
        Last trading day as pd.Timestamp.
    """
    deliv_year, deliv_month = add_months(contract_year, contract_month, 3)
    imm_deliv = third_wednesday(deliv_year, deliv_month)

    d = ql.Date(imm_deliv.day, imm_deliv.month, imm_deliv.year) - 1
    while not cal.isBusinessDay(d):
        d -= 1
    return pd.Timestamp(d.year(), d.month(), d.dayOfMonth())


def _get_business_days_in_range(
    start: pd.Timestamp,
    end: pd.Timestamp,
    cal: ql.Calendar,
) -> pd.DatetimeIndex:
    """
    Return business days in [start, end) using a QuantLib calendar.

    This is a helper function used by SR3 compounding calculations.
    """
    bdays = []
    current = start.normalize()
    end_norm = end.normalize()

    while current < end_norm:
        qld = ql.Date(current.day, current.month, current.year)
        if cal.isBusinessDay(qld):
            bdays.append(current)
        current += pd.Timedelta(days=1)

    return pd.DatetimeIndex(bdays)


# =============================================================================
# SECTION 2: Core Settlement Logic
# =============================================================================


def _compute_compounded_rate(
    rates: pd.Series,
    bdays: pd.DatetimeIndex,
    end_date: pd.Timestamp,
) -> float:
    """
    Compute compounded rate from daily fixings using CME methodology.

    Formula: R = (Product(1 + ri * di / 360) - 1) * 360 / D * 100
    where di = days until next fixing, D = total days in period.

    Args:
        rates: Daily SOFR rates indexed by date (in percent).
        bdays: Business days in the reference period.
        end_date: End date (exclusive) of the period.

    Returns:
        Compounded rate as a percentage (not price).
    """
    next_days = bdays[1:].append(pd.DatetimeIndex([end_date.normalize()]))
    di = (next_days.values - bdays.values).astype("timedelta64[D]").astype(int)
    D = int(di.sum())

    factors = 1.0 + (di / 360.0) * (rates.values / 100.0)
    accrual = np.prod(factors) - 1.0

    return accrual * (360.0 / D) * 100.0


def sr3_settlement_from_sofr(
    sofr_df: pd.DataFrame,
    contract_year: int,
    contract_month: int,
    cal: ql.Calendar,
) -> Optional[float]:
    """
    Compute SR3 final settlement from historical SOFR rates.

    Uses daily compounding over the reference quarter (IMM-to-IMM).
    Settlement price = 100 - R, where R is the compounded rate.

    Args:
        sofr_df: DataFrame with ['effectiveDate', 'rate'] columns.
        contract_year: Contract year.
        contract_month: Contract month (IMM month: 3, 6, 9, or 12).
        cal: QuantLib calendar for business day determination.

    Returns:
        Settlement price rounded to 4 decimal places, or None if data incomplete.

    Example:
        >>> settle = sr3_settlement_from_sofr(sofr_df, 2025, 3, cal)  # SR3H5
        >>> print(f"SR3H5 settles at {settle:.4f}")
    """
    start_incl, end_excl = sr3_reference_quarter(contract_year, contract_month)
    bdays = _get_business_days_in_range(start_incl, end_excl, cal)

    rates_df = sofr_df.set_index("effectiveDate").sort_index()
    rates = rates_df.reindex(bdays)["rate"]

    if rates.isna().any():
        return None

    R_raw = _compute_compounded_rate(rates, bdays, end_excl)
    R_percent = round_half_up(R_raw, 4)

    return 100.0 - R_percent


def _format_diff_bps(model: Optional[float], official: float) -> str:
    """Format difference in basis points between model and official price."""
    if model is None or official == 0.0:
        return "N/A"
    return f"{abs(model - official) * 100.0:.2f}"


# =============================================================================
# SECTION 3: Historical Table Builders (2025)
# =============================================================================


def build_sr3_2025_table(
    sofr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_map: dict[str, float],
) -> pd.DataFrame:
    """
    Build a summary table of all 2025 SR3 contract settlements.

    Generates a DataFrame comparing model-calculated compounded settlements
    against official CME/Barchart prices for expired contracts.

    Args:
        sofr_df: Historical SOFR rates with ['effectiveDate', 'rate'].
        asof: Reference date for determining expiry status.
        cal: QuantLib business day calendar.
        official_map: Mapping of contract codes (e.g., "SR3H5") to official prices.

    Returns:
        DataFrame with columns: Contract, Contract Month, Ref Start (incl),
        Ref End (excl), Last Trading Day, Status, Model, Official-Barchart, Diff (bps).
    """
    YEAR = 2025
    rows = []

    for month in range(1, 13):
        code = f"SR3{CME_MONTH_CODES[month]}5"
        month_label = pd.Timestamp(YEAR, month, 1).strftime("%b %Y")
        start_incl, end_excl = sr3_reference_quarter(YEAR, month)
        ltd = sr3_last_trading_day(YEAR, month, cal=cal)

        expired = ltd < asof
        official = official_map.get(code, 0.0)

        row = {
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start (incl)": str(start_incl.date()),
            "Ref End (excl)": str(end_excl.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": "Expired" if expired else "Not expired",
            "Official-Barchart": f"{official:.4f}" if official != 0.0 else "—",
        }

        if not expired:
            row.update({"Model": "Not expired", "Diff (bps)": "N/A"})
        else:
            model_val = sr3_settlement_from_sofr(sofr_df, YEAR, month, cal=cal)
            if model_val is None:
                row.update({"Model": "No Data", "Diff (bps)": "N/A"})
            else:
                row.update({
                    "Model": f"{model_val:.4f}",
                    "Diff (bps)": _format_diff_bps(model_val, official),
                })

        rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# SECTION 4: Expected/Forward Table Builders (2026)
# =============================================================================


def sr3_expected_settlement(
    contract_year: int,
    contract_month: int,
    cal: ql.Calendar,
    effr_path: pd.Series,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> Optional[float]:
    """
    Compute expected SR3 settlement from projected EFFR path.

    Projects SOFR from EFFR using spread assumptions, then compounds
    over the reference quarter to produce an expected settlement price.

    Args:
        contract_year: Contract year.
        contract_month: Contract month (IMM month: 3, 6, 9, or 12).
        cal: QuantLib calendar for business day determination.
        effr_path: Daily EFFR path projection indexed by date.
        base_spread_bps: Base SOFR-EFFR spread in basis points (default: 3.0).
        jump_bps: Additional spread on month-end dates (default: 10.0).

    Returns:
        Expected settlement price, or None if EFFR path doesn't cover the period.
    """
    start_incl, end_excl = sr3_reference_quarter(contract_year, contract_month)
    bdays = _get_business_days_in_range(start_incl, end_excl, cal)

    # Validate EFFR path coverage
    if bdays.min() < effr_path.index.min() or end_excl.normalize() > effr_path.index.max():
        return None

    # Build projected SOFR rates with spread adjustments
    rates = pd.Series(
        [expected_sofr_on_date(d, effr_path, cal, base_spread_bps, jump_bps) for d in bdays],
        index=bdays,
    )

    R_raw = _compute_compounded_rate(rates, bdays, end_excl)
    R_percent = round_half_up(R_raw, 4)

    return 100.0 - R_percent


def build_sr3_2026_expected_table(
    cal: ql.Calendar,
    effr_path_extended: pd.Series,
) -> pd.DataFrame:
    """
    Build expected SR3 settlements for all 2026 contracts.

    Args:
        cal: QuantLib business day calendar.
        effr_path_extended: Daily EFFR projection that covers through ~Mar 2027
            (needed for Dec 2026 contract which settles in Mar 2027).

    Returns:
        DataFrame with expected settlement prices for 2026 SR3 contracts.
    """
    YEAR = 2026
    rows = []

    for month in range(1, 13):
        code = f"SR3{CME_MONTH_CODES[month]}6"
        month_label = pd.Timestamp(YEAR, month, 1).strftime("%b %Y")
        start_incl, end_excl = sr3_reference_quarter(YEAR, month)
        ltd = sr3_last_trading_day(YEAR, month, cal=cal)

        model_val = sr3_expected_settlement(YEAR, month, cal=cal, effr_path=effr_path_extended)
        model_str = f"{model_val:.4f}" if isinstance(model_val, (float, int)) else "No Data"

        rows.append({
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start (incl)": str(start_incl.date()),
            "Ref End (excl)": str(end_excl.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": "Expected",
            "Expected Settle": model_str,
        })

    return pd.DataFrame(rows)

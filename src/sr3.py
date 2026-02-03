import pandas as pd
import QuantLib as ql
from typing import Optional
from .rounding import round_half_up
from .constants import CME_MONTH_CODES
from .dates_calendars import third_wednesday, add_months
from .scenarios import expected_sofr_on_date

def sr3_reference_quarter(contract_year: int, contract_month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_incl = third_wednesday(contract_year, contract_month)
    end_year, end_month = add_months(contract_year, contract_month, 3)
    end_excl = third_wednesday(end_year, end_month)
    return start_incl, end_excl

def sr3_last_trading_day(contract_year: int, contract_month: int, cal: ql.Calendar) -> pd.Timestamp:
    deliv_year, deliv_month = add_months(contract_year, contract_month, 3)
    imm_deliv = third_wednesday(deliv_year, deliv_month)

    d = ql.Date(imm_deliv.day, imm_deliv.month, imm_deliv.year) - 1
    while not cal.isBusinessDay(d):
        d = d - 1
    return pd.Timestamp(d.year(), d.month(), d.dayOfMonth())

def sr3_settlement_from_sofr(sofr_df: pd.DataFrame, contract_year: int, contract_month: int, cal: ql.Calendar) -> Optional[float]:
    start_incl, end_excl = sr3_reference_quarter(contract_year, contract_month)
    s = sofr_df.set_index("effectiveDate").sort_index()

    current = start_incl
    bdays = []
    while current < end_excl:
        qld = ql.Date(current.day, current.month, current.year)
        if cal.isBusinessDay(qld):
            bdays.append(current)
        current += pd.Timedelta(days=1)
    bdays = pd.DatetimeIndex(bdays)

    rates = s.reindex(bdays)["rate"]
    if rates.isna().any():
        return None

    next_days = bdays[1:].append(pd.DatetimeIndex([end_excl]))
    di = (next_days.values - bdays.values).astype("timedelta64[D]").astype(int)
    D = int(di.sum())

    factors = 1.0 + (di / 360.0) * (rates.values / 100.0)
    accrual = factors.prod() - 1.0
    R_raw = accrual * (360.0 / D) * 100.0

    R_percent = round_half_up(R_raw, 4)  # 0.0001
    return 100.0 - R_percent

def build_sr3_2025_table(
    sofr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_map: dict[str, float],
) -> pd.DataFrame:
    YEAR = 2025
    rows = []

    for m in range(1, 13):
        code = f"SR3{CME_MONTH_CODES[m]}5"
        month_label = pd.Timestamp(YEAR, m, 1).strftime("%b %Y")

        start_incl, end_excl = sr3_reference_quarter(YEAR, m)
        ltd = sr3_last_trading_day(YEAR, m, cal=cal)

        expired = ltd < asof
        status = "Expired" if expired else "Not expired"

        official = official_map.get(code, 0.0)

        if not expired:
            model_str = "Not expired"
            diff_str = "N/A"
        else:
            model_val = sr3_settlement_from_sofr(sofr_df, YEAR, m, cal=cal)
            if model_val is None:
                model_str = "No Data"
                diff_str = "N/A"
            else:
                model_str = f"{model_val:.4f}"
                if official != 0.0:
                    diff_str = f"{abs(model_val - official) * 100.0:.2f}"
                else:
                    diff_str = "N/A"

        rows.append({
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start (incl)": str(start_incl.date()),
            "Ref End (excl)": str(end_excl.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": status,
            "Model": model_str,
            "Official-Barchart": (f"{official:.4f}" if official != 0.0 else "—"),
            "Diff (bps)": diff_str,
        })

    return pd.DataFrame(rows)

def sr3_expected_settlement(
    contract_year: int,
    contract_month: int,
    cal: ql.Calendar,
    effr_path: pd.Series,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> Optional[float]:
    start_incl, end_excl = sr3_reference_quarter(contract_year, contract_month)

    current = start_incl
    bdays = []
    while current < end_excl:
        qld = ql.Date(current.day, current.month, current.year)
        if cal.isBusinessDay(qld):
            bdays.append(current.normalize())
        current += pd.Timedelta(days=1)
    bdays = pd.DatetimeIndex(bdays)

    if bdays.min() < effr_path.index.min() or end_excl.normalize() > effr_path.index.max():
        return None

    rates = pd.Series(
        [expected_sofr_on_date(d, effr_path, cal, base_spread_bps, jump_bps) for d in bdays],
        index=bdays
    )

    next_days = bdays[1:].append(pd.DatetimeIndex([end_excl.normalize()]))
    di = (next_days.values - bdays.values).astype("timedelta64[D]").astype(int)
    D = int(di.sum())

    factors = 1.0 + (di / 360.0) * (rates.values / 100.0)
    accrual = factors.prod() - 1.0
    R_raw = accrual * (360.0 / D) * 100.0

    R_percent = round_half_up(R_raw, 4)
    return 100.0 - R_percent

def build_sr3_2026_expected_table(
    cal: ql.Calendar,
    effr_path_extended: pd.Series,   # must cover through ~Mar 2027
) -> pd.DataFrame:
    YEAR = 2026
    rows = []

    for m in range(1, 13):
        code = f"SR3{CME_MONTH_CODES[m]}6"
        month_label = pd.Timestamp(YEAR, m, 1).strftime("%b %Y")

        start_incl, end_excl = sr3_reference_quarter(YEAR, m)
        ltd = sr3_last_trading_day(YEAR, m, cal=cal)

        model_val = sr3_expected_settlement(YEAR, m, cal=cal, effr_path=effr_path_extended)
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

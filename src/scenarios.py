import pandas as pd
import QuantLib as ql
from .dates_calendars import last_business_day_of_month, midmonth_jump_day

def build_expected_midpoint_path(
    start_mid: float,
    fomc_end_dates: list[pd.Timestamp],
    cut_indices: set[int],
    cut_size_bps: int,
    date_start: pd.Timestamp,
    date_end: pd.Timestamp,
    effective_lag_days: int = 1,
) -> pd.Series:
    days = pd.date_range(date_start, date_end, freq="D")

    eff_dates: list[tuple[int, pd.Timestamp]] = []
    for i, d in enumerate(fomc_end_dates):
        eff_dates.append((i, (d + pd.Timedelta(days=effective_lag_days)).normalize()))
    eff_dates.sort(key=lambda x: x[1])

    current = start_mid
    out = pd.Series(index=days, dtype=float)
    j = 0

    for day in days:
        while j < len(eff_dates) and day == eff_dates[j][1]:
            idx = eff_dates[j][0]
            if idx in cut_indices:
                current -= cut_size_bps / 100.0
            j += 1
        out.loc[day] = current

    return out

def build_expected_sofr_daily_for_month(
    effr_daily_path: pd.Series,
    year: int,
    month: int,
    cal: ql.Calendar,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> pd.Series:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = (start + pd.offsets.MonthEnd(1)).normalize()
    days = pd.date_range(start, end, freq="D")

    sofr = effr_daily_path.reindex(days).copy()
    sofr = sofr + (base_spread_bps / 100.0)

    d_mid = midmonth_jump_day(year, month).normalize()
    d_lbd = last_business_day_of_month(year, month, cal=cal).normalize()

    jump = jump_bps / 100.0
    for d in {d_mid, d_lbd}:
        if d in sofr.index:
            sofr.loc[d] = sofr.loc[d] + jump

    return sofr

def expected_sofr_on_date(
    d: pd.Timestamp,
    effr_path: pd.Series,
    cal: ql.Calendar,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> float:
    d = d.normalize()
    effr = float(effr_path.loc[d])
    sofr = effr + (base_spread_bps / 100.0)

    y, m = d.year, d.month
    d_mid = midmonth_jump_day(y, m).normalize()
    d_lbd = last_business_day_of_month(y, m, cal=cal).normalize()

    if d == d_mid or d == d_lbd:
        sofr += (jump_bps / 100.0)

    return sofr

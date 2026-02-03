import pandas as pd
import QuantLib as ql
from typing import Optional


_US_GOVT_BOND_CAL = ql.UnitedStates(ql.UnitedStates.GovernmentBond)

def us_govt_bond_calendar() -> ql.Calendar:
    return _US_GOVT_BOND_CAL

def third_wednesday(year: int, month: int) -> pd.Timestamp:
    first_day = pd.Timestamp(year=year, month=month, day=1)
    days_until_wed = (2 - first_day.weekday()) % 7  # Wed=2
    return first_day + pd.Timedelta(days=days_until_wed + 14)

def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    m = month + n
    y = year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return y, m

def month_start_end(year: int, month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = (start + pd.offsets.MonthEnd(1)).normalize()
    return start, end

def last_business_day_of_month(year: int, month: int, cal: Optional[ql.Calendar] = None) -> pd.Timestamp:
    if cal is None:
        cal = _US_GOVT_BOND_CAL
    last_cal_day = (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(1)).normalize()
    d = last_cal_day
    while True:
        qd = ql.Date(d.day, d.month, d.year)
        if cal.isBusinessDay(qd):
            return d
        d -= pd.Timedelta(days=1)

def midmonth_jump_day(year: int, month: int) -> pd.Timestamp:
    """
    Your rule:
      - 15th unless weekend
      - if Sat -> 17th
      - if Sun -> 16th
    """
    d15 = pd.Timestamp(year=year, month=month, day=15)
    wd = d15.weekday()  # Mon=0 ... Sun=6
    if wd == 5:
        return d15 + pd.Timedelta(days=2)  # 17th
    if wd == 6:
        return d15 + pd.Timedelta(days=1)  # 16th
    return d15

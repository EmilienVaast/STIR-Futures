import pandas as pd
import QuantLib as ql
from typing import Optional, Tuple
from stir_futures.constants import CME_MONTH_CODES
from stir_futures.rounding import round_half_up
from stir_futures.calendars import last_business_day_of_month


def zq_final_settlement_from_effr(
    effr_df: pd.DataFrame,
    year: int,
    month: int,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[pd.Timestamp]]:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = (start + pd.offsets.MonthEnd(1)).normalize()
    cal_days = pd.date_range(start, end, freq="D")

    s = effr_df.set_index("effectiveDate")["rate"].sort_index()
    daily_rate = s.reindex(cal_days, method="ffill")

    if daily_rate.isna().any():
        missing = daily_rate[daily_rate.isna()].index
        return None, None, None, missing[0]

    avg_raw = float(daily_rate.mean())
    avg_rnd = round_half_up(avg_raw, 3)          # 0.001%

    settle = 100.0 - avg_rnd
    settle_4dp = round_half_up(settle, 4)        # keep as your code did (0.0001)

    return avg_raw, avg_rnd, settle_4dp, None


def build_zq_2025_table(
    effr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_prices: dict[str, float],
) -> pd.DataFrame:
    rows = []
    YEAR = 2025

    for m in range(1, 13):
        code = f"ZQ{CME_MONTH_CODES[m]}5"
        month_start = pd.Timestamp(year=YEAR, month=m, day=1)
        month_end = (month_start + pd.offsets.MonthEnd(1)).normalize()
        ltd = last_business_day_of_month(YEAR, m, cal=cal)

        avg_raw, avg_rnd, model_settle, _ = zq_final_settlement_from_effr(effr_df, YEAR, m)

        if model_settle is None:
            status = "No Data"
            model_str = "No Data"
            avg_raw_str = "—"
            avg_rnd_str = "—"
        else:
            status = "Expired" if ltd < asof else "Not expired"
            model_str = f"{model_settle:.4f}"
            avg_raw_str = f"{avg_raw:.6f}"
            avg_rnd_str = f"{avg_rnd:.3f}"

        off = official_prices.get(code, None)
        official_str = f"{off:.4f}" if isinstance(off, (float, int)) else "—"
        diff_str = "N/A"
        if isinstance(off, (float, int)) and model_settle is not None:
            diff_str = f"{abs(model_settle - off) * 100.0:.2f}"

        rows.append({
            "Contract": code,
            "Contract Month": month_start.strftime("%b %Y"),
            "Ref Start": month_start.date().isoformat(),
            "Ref End": month_end.date().isoformat(),
            "Last Trading Day": ltd.date().isoformat(),
            "Status": status,
            "Avg EFFR (raw %)": avg_raw_str,
            "Avg EFFR (rnd %)": avg_rnd_str,
            "Model Settle": model_str,
            "Official-Barchart": official_str,
            "Diff (bps)": diff_str,
        })

    return pd.DataFrame(rows)


def build_expected_zq_2026_table(
    mid_path_2026: pd.Series,
    start_mid: float,
    cal: ql.Calendar,
) -> pd.DataFrame:
    rows = []
    YEAR = 2026

    for m in range(1, 13):
        code = f"ZQ{CME_MONTH_CODES[m]}26"
        month_start = pd.Timestamp(year=YEAR, month=m, day=1)
        month_end = (month_start + pd.offsets.MonthEnd(1)).normalize()
        ltd = last_business_day_of_month(YEAR, m, cal=cal)

        cal_days = pd.date_range(month_start, month_end, freq="D")
        avg_raw = float(mid_path_2026.reindex(cal_days).mean())
        avg_rnd = round_half_up(avg_raw, 3)

        price = 100.0 - avg_rnd
        price_4dp = round_half_up(price, 4)

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
            "Expected Price": f"{price_4dp:.4f}",
        })

    return pd.DataFrame(rows)

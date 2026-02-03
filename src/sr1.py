import pandas as pd
import QuantLib as ql
from typing import Optional
from .constants import CME_MONTH_CODES
from .rounding import round_half_up
from .dates_calendars import month_start_end, last_business_day_of_month
from .scenarios import build_expected_sofr_daily_for_month

def sr1_final_settlement_from_sofr(sofr_df: pd.DataFrame, delivery_year: int, delivery_month: int):
    month_start, month_end = month_start_end(delivery_year, delivery_month)
    cal_days = pd.date_range(month_start, month_end, freq="D")

    s = sofr_df.set_index("effectiveDate")["rate"].sort_index()
    daily_rates = s.reindex(cal_days, method="ffill")
    if daily_rates.isna().any():
        return None, None, None

    avg_raw = float(daily_rates.mean())
    avg_rnd = round_half_up(avg_raw, 3)        # 0.001%
    settle = 100.0 - avg_rnd
    settle = round_half_up(settle, 3)          # price to 0.001

    return settle, avg_raw, avg_rnd

def build_sr1_2025_table(
    sofr_df: pd.DataFrame,
    asof: pd.Timestamp,
    cal: ql.Calendar,
    official_map: dict[str, float],
) -> pd.DataFrame:
    YEAR = 2025
    rows = []

    for m in range(1, 13):
        code = f"SR1{CME_MONTH_CODES[m]}5"
        month_label = pd.Timestamp(YEAR, m, 1).strftime("%b %Y")

        ref_start, ref_end = month_start_end(YEAR, m)
        ltd = last_business_day_of_month(YEAR, m, cal=cal)

        expired = ltd < asof
        status = "Expired" if expired else "Not expired"

        official = official_map.get(code, None)

        if not expired:
            rows.append({
                "Contract": code,
                "Contract Month": month_label,
                "Ref Start": str(ref_start.date()),
                "Ref End": str(ref_end.date()),
                "Last Trading Day": str(ltd.date()),
                "Status": status,
                "Avg SOFR (raw %)": "—",
                "Avg SOFR (rnd %)": "—",
                "Model Settle": "Not expired",
                "Official-Barchart": f"{official:.4f}" if isinstance(official, (float, int)) else "—",
                "Diff (bps)": "N/A"
            })
            continue

        settle, avg_raw, avg_rnd = sr1_final_settlement_from_sofr(sofr_df, YEAR, m)
        if settle is None:
            model_str, avg_raw_str, avg_rnd_str, diff_str = "No Data", "—", "—", "N/A"
        else:
            model_str = f"{settle:.4f}"
            avg_raw_str = f"{avg_raw:.5f}"
            avg_rnd_str = f"{avg_rnd:.3f}"
            diff_str = f"{abs(settle - official) * 100.0:.2f}" if isinstance(official, (float, int)) else "N/A"

        rows.append({
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start": str(ref_start.date()),
            "Ref End": str(ref_end.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": status,
            "Avg SOFR (raw %)": avg_raw_str,
            "Avg SOFR (rnd %)": avg_rnd_str,
            "Model Settle": model_str,
            "Official-Barchart": f"{official:.4f}" if isinstance(official, (float, int)) else "—",
            "Diff (bps)": diff_str
        })

    return pd.DataFrame(rows)

def build_sr1_2026_expected_table(
    effr_path_2026: pd.Series,
    cal: ql.Calendar,
    base_spread_bps: float = 3.0,
    jump_bps: float = 10.0,
) -> pd.DataFrame:
    YEAR = 2026
    rows = []

    for m in range(1, 13):
        code = f"SR1{CME_MONTH_CODES[m]}6"
        month_label = pd.Timestamp(YEAR, m, 1).strftime("%b %Y")
        ref_start, ref_end = month_start_end(YEAR, m)
        ltd = last_business_day_of_month(YEAR, m, cal=cal)

        sofr_daily = build_expected_sofr_daily_for_month(
            effr_daily_path=effr_path_2026,
            year=YEAR,
            month=m,
            cal=cal,
            base_spread_bps=base_spread_bps,
            jump_bps=jump_bps,
        )

        avg_raw = float(sofr_daily.mean())
        avg_rnd = round_half_up(avg_raw, 3)
        price = 100.0 - avg_rnd
        price = round_half_up(price, 3)

        rows.append({
            "Contract": code,
            "Contract Month": month_label,
            "Ref Start": str(ref_start.date()),
            "Ref End": str(ref_end.date()),
            "Last Trading Day": str(ltd.date()),
            "Status": "Expected",
            "Mid-month jump day": sofr_daily.index[sofr_daily.index.day.isin([15,16,17])].min().date().isoformat(),  # display-only
            "Last BD jump day": last_business_day_of_month(YEAR, m, cal=cal).date().isoformat(),
            "Avg SOFR (raw %)": f"{avg_raw:.6f}",
            "Avg SOFR (rnd %)": f"{avg_rnd:.3f}",
            "Expected Settle": f"{price:.4f}",
        })

    return pd.DataFrame(rows)

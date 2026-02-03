import pandas as pd
import requests
from typing import Optional

def _get_nyfed_ref_rate(
    url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["refRates"])
    df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
    df["rate"] = pd.to_numeric(df["percentRate"], errors="coerce")

    return (
        df[["effectiveDate", "rate"]]
        .dropna()
        .sort_values("effectiveDate")
        .reset_index(drop=True)
    )

def get_sofr(start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    return _get_nyfed_ref_rate(
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json",
        start_date,
        end_date,
    )

def get_effr(start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    return _get_nyfed_ref_rate(
        "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json",
        start_date,
        end_date,
    )

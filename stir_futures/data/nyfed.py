import pandas as pd
import requests
from typing import Optional

SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"


def fetch_ref_rate(
    url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timeout: int = 30,
) -> pd.DataFrame:
    params: dict[str, str] = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date

    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    df = pd.DataFrame(payload.get("refRates", []))
    if df.empty:
        return pd.DataFrame(columns=["effectiveDate", "rate"])

    df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
    df["rate"] = pd.to_numeric(df["percentRate"], errors="coerce")

    return (
        df[["effectiveDate", "rate"]]
        .dropna()
        .sort_values("effectiveDate")
        .reset_index(drop=True)
    )


def fetch_sofr(start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    return fetch_ref_rate(SOFR_URL, start_date, end_date)


def fetch_effr(start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    return fetch_ref_rate(EFFR_URL, start_date, end_date)

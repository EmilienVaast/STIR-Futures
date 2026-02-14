from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from stir_futures.config import resolve_data_dir
from stir_futures.data.nyfed import EFFR_URL, SOFR_URL, fetch_ref_rate


def _cache_path(name: str, data_dir: Path) -> Path:
    return data_dir / f"{name.lower()}.parquet"


def _normalize_rates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["effectiveDate", "rate"])
    out = df.copy()
    out["effectiveDate"] = pd.to_datetime(out["effectiveDate"])
    out["rate"] = pd.to_numeric(out["rate"], errors="coerce")
    return out[["effectiveDate", "rate"]].dropna().sort_values("effectiveDate").reset_index(drop=True)


def load_cached_rates(name: str, data_dir: Optional[Path] = None) -> Optional[pd.DataFrame]:
    data_dir = resolve_data_dir() if data_dir is None else data_dir
    path = _cache_path(name, data_dir)
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    return _normalize_rates(df)


def save_cached_rates(name: str, df: pd.DataFrame, data_dir: Optional[Path] = None) -> Path:
    data_dir = resolve_data_dir() if data_dir is None else data_dir
    path = _cache_path(name, data_dir)
    out = _normalize_rates(df)
    out.to_parquet(path, index=False)
    return path


def _covers_range(df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]) -> bool:
    if df.empty:
        return False
    if start_date is None and end_date is None:
        return True
    min_dt = df["effectiveDate"].min()
    max_dt = df["effectiveDate"].max()
    if start_date is not None and pd.Timestamp(start_date) < min_dt:
        return False
    if end_date is not None and pd.Timestamp(end_date) > max_dt:
        return False
    return True


def _merge_rates(existing: Optional[pd.DataFrame], new_df: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return _normalize_rates(new_df)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["effectiveDate"], keep="last")
    return _normalize_rates(combined)


def get_cached_ref_rate(
    name: str,
    url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    refresh: bool = False,
) -> pd.DataFrame:
    data_dir = resolve_data_dir() if data_dir is None else data_dir
    cached = None if refresh else load_cached_rates(name, data_dir=data_dir)

    if cached is None or not _covers_range(cached, start_date, end_date):
        fetched = fetch_ref_rate(url, start_date=start_date, end_date=end_date)
        merged = _merge_rates(cached, fetched)
        save_cached_rates(name, merged, data_dir=data_dir)
        cached = merged

    if start_date is None and end_date is None:
        return cached

    s = cached.set_index("effectiveDate").sort_index()
    if start_date is not None:
        s = s.loc[pd.Timestamp(start_date) :]
    if end_date is not None:
        s = s.loc[: pd.Timestamp(end_date)]
    return s.reset_index()


def get_sofr(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    refresh: bool = False,
) -> pd.DataFrame:
    return get_cached_ref_rate(
        name="sofr",
        url=SOFR_URL,
        start_date=start_date,
        end_date=end_date,
        data_dir=data_dir,
        refresh=refresh,
    )


def get_effr(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
    refresh: bool = False,
) -> pd.DataFrame:
    return get_cached_ref_rate(
        name="effr",
        url=EFFR_URL,
        start_date=start_date,
        end_date=end_date,
        data_dir=data_dir,
        refresh=refresh,
    )

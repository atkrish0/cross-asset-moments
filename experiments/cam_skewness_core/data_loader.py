"""Data ingestion and quality helpers for cross-asset skewness strategy."""

from __future__ import annotations

import datetime as dt
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

LOADER_VERSION = "yf_loader_v4_2026_03_18"

BASE_COLS = ["Date", "Ticker", "close", "open", "NextOpen", "LogReturn"]
ALL_COLS = BASE_COLS + ["AssetClass"]



def clean_yf(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize Yahoo output into canonical schema."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=BASE_COLS)

    df = raw.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    if "Date" not in df.columns or "Open" not in df.columns:
        return pd.DataFrame(columns=BASE_COLS)

    close_col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
    if close_col is None:
        return pd.DataFrame(columns=BASE_COLS)

    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["Ticker"] = ticker
    df["close"] = pd.to_numeric(df[close_col], errors="coerce")
    df["open"] = pd.to_numeric(df["Open"], errors="coerce")

    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    df["NextOpen"] = df["open"].shift(-1)
    df["LogReturn"] = np.log(df["close"] / df["close"].shift(1))

    return df[BASE_COLS].dropna(subset=["close", "open"]).reset_index(drop=True)



def load_ticker_yf(ticker: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    raw = yf.download(
        ticker,
        start=start_date.date(),
        end=end_date.date(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    return clean_yf(raw, ticker)



def load_universe_yf(
    universe_spec: Sequence[Tuple[str, Sequence[str]]],
    history_days: int,
    end_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load all tickers in the universe and return data + failure diagnostics."""
    if end_date is None:
        end_date = pd.Timestamp(dt.datetime.now().date()) + pd.Timedelta(days=1)
    start_date = end_date - pd.Timedelta(days=history_days)

    frames: List[pd.DataFrame] = []
    failures: List[tuple[str, str, str]] = []

    for asset_class, tickers in universe_spec:
        for ticker in sorted(set(tickers)):
            try:
                df = load_ticker_yf(ticker, start_date, end_date)
                if df.empty:
                    failures.append((asset_class, ticker, "empty or missing required columns"))
                    continue
                df["AssetClass"] = asset_class
                frames.append(df)
            except Exception as exc:  # pragma: no cover - notebook operational safety
                failures.append((asset_class, ticker, str(exc)))

    if frames:
        all_data = pd.concat(frames, ignore_index=True)
        all_data = all_data.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    else:
        all_data = pd.DataFrame(columns=ALL_COLS)

    failures_df = pd.DataFrame(failures, columns=["AssetClass", "Ticker", "Error"])
    return all_data, failures_df



def universe_summary(universe_spec: Sequence[Tuple[str, Sequence[str]]]) -> pd.DataFrame:
    """Summarize ticker counts by asset class."""
    rows = []
    for asset_class, tickers in universe_spec:
        rows.append(
            {
                "AssetClass": asset_class,
                "TickersListed": len(tickers),
                "TickersUnique": len(set(tickers)),
                "Duplicates": len(tickers) - len(set(tickers)),
            }
        )
    return pd.DataFrame(rows).sort_values("AssetClass").reset_index(drop=True)



def data_quality_summary(all_data: pd.DataFrame) -> pd.DataFrame:
    """Ticker-level history coverage and missingness summary."""
    if all_data.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "AssetClass",
                "StartDate",
                "EndDate",
                "Obs",
                "MissingReturnPct",
            ]
        )

    out = (
        all_data.groupby(["Ticker", "AssetClass"], as_index=False)
        .agg(
            StartDate=("Date", "min"),
            EndDate=("Date", "max"),
            Obs=("Date", "count"),
            MissingReturnPct=("LogReturn", lambda s: 100.0 * s.isna().mean()),
        )
        .sort_values(["AssetClass", "Ticker"])
        .reset_index(drop=True)
    )
    return out

"""Signal engineering for cross-asset skewness strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd



def add_skew_features(df: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Build rolling skew signal per ticker."""
    required = {"Date", "Ticker", "LogReturn"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Input df missing required columns: {sorted(missing)}")

    if df.empty:
        out = df.copy()
        out["Avg"] = np.nan
        out["Dev"] = np.nan
        out["SkewDay"] = np.nan
        out["Skew"] = np.nan
        return out

    out = df.copy().sort_values(["Ticker", "Date"]).reset_index(drop=True)
    grp = out.groupby("Ticker", sort=False)["LogReturn"]

    out["Avg"] = grp.transform(lambda s: s.rolling(window=lookback, min_periods=lookback).mean())
    out["Dev"] = grp.transform(lambda s: s.rolling(window=lookback, min_periods=lookback).std())

    z = (out["LogReturn"] - out["Avg"]) / out["Dev"]
    out["SkewDay"] = z**3
    out["Skew"] = out.groupby("Ticker", sort=False)["SkewDay"].transform(
        lambda s: s.rolling(window=lookback, min_periods=lookback).mean()
    )

    return out.dropna(subset=["Skew"]).reset_index(drop=True)



def skew_distribution_by_class(all_data: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional distribution diagnostics for skew by asset class."""
    return (
        all_data.groupby("AssetClass")["Skew"]
        .agg(["count", "mean", "std", "min", "median", "max"])
        .reset_index()
        .sort_values("AssetClass")
        .reset_index(drop=True)
    )



def build_monthly_signal_table(all_data: pd.DataFrame) -> pd.DataFrame:
    """Create monthly end-of-month skew snapshot and next trading day activation date."""
    bt = all_data.copy().sort_values(["Ticker", "Date"]).reset_index(drop=True)
    bt["Month"] = bt["Date"].dt.to_period("M").dt.to_timestamp()
    bt["NextDay"] = bt.groupby("Ticker")["Date"].shift(-1)
    bt["NextDay"] = bt["NextDay"].fillna(bt["Date"] + pd.offsets.BDay(1))

    monthly_vals = (
        bt.groupby(["Month", "AssetClass", "Ticker"], as_index=False)
        .agg(Date=("Date", "last"), NextDate=("NextDay", "last"), EOMSkew=("Skew", "last"))
    )
    return monthly_vals



def add_rank_weights(monthly_vals: pd.DataFrame) -> pd.DataFrame:
    """Add centered rank weights and normalized long-short weights by date and asset class."""
    out = monthly_vals.copy()
    out["SkewWeightRaw"] = out.groupby(["Date", "AssetClass"])["EOMSkew"].transform(
        lambda s: s.rank(ascending=False, method="average") - ((len(s) + 1) / 2)
    )

    def normalize_raw_weights(s: pd.Series) -> pd.Series:
        denom = s.abs().sum() / 2
        if denom == 0 or pd.isna(denom):
            return pd.Series(np.zeros(len(s)), index=s.index)
        return s / denom

    out["SkewWeight"] = out.groupby(["Date", "AssetClass"])["SkewWeightRaw"].transform(normalize_raw_weights)
    return out

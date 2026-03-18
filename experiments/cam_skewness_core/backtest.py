"""Backtest assembly and portfolio return construction."""

from __future__ import annotations

import numpy as np
import pandas as pd



def apply_monthly_weights_to_daily(all_data: pd.DataFrame, monthly_vals: pd.DataFrame) -> pd.DataFrame:
    """Activate monthly weights on next trading day and forward-fill within ticker."""
    bt = all_data.copy().sort_values(["Ticker", "Date"]).reset_index(drop=True)
    weightings = monthly_vals[["NextDate", "Ticker", "SkewWeight"]].rename(columns={"NextDate": "Date"})

    out = bt.merge(weightings, on=["Date", "Ticker"], how="left")
    out = out.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    out["SkewWeightFF"] = out.groupby("Ticker")["SkewWeight"].ffill()
    return out



def compute_asset_class_returns(all_data_weights: pd.DataFrame) -> pd.DataFrame:
    """Compute daily strategy and equal-weight market returns by asset class."""
    out = all_data_weights.copy()
    out["WeightedReturn"] = out["SkewWeightFF"] * out["LogReturn"]

    asset_portfolios = (
        out.groupby(["Date", "AssetClass"], as_index=False)
        .agg(PortfolioReturn=("WeightedReturn", "sum"), MktReturn=("LogReturn", "mean"))
        .dropna()
    )
    return asset_portfolios



def compute_global_factor(
    asset_portfolios: pd.DataFrame,
    lookback: int,
    vol_target: float,
    scale_market_with_strategy_vol: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build vol-scaled class returns and aggregate global factor series."""
    out = asset_portfolios.copy().sort_values(["AssetClass", "Date"]).reset_index(drop=True)

    out["StratVol"] = out.groupby("AssetClass")["PortfolioReturn"].transform(
        lambda s: s.rolling(window=lookback, min_periods=100).std()
    )
    out["MktVol"] = out.groupby("AssetClass")["MktReturn"].transform(
        lambda s: s.rolling(window=lookback, min_periods=100).std()
    )

    out["NormReturn"] = vol_target * out["PortfolioReturn"] / out["StratVol"]

    if scale_market_with_strategy_vol:
        denom = out["StratVol"]
    else:
        denom = out["MktVol"]
    out["NormMarketReturn"] = vol_target * out["MktReturn"] / denom

    gcf = (
        out.dropna(subset=["NormReturn", "NormMarketReturn"])
        .groupby("Date", as_index=False)
        .agg(Return=("NormReturn", "mean"), MktReturn=("NormMarketReturn", "mean"))
    )

    return out, gcf



def weight_sanity_checks(monthly_vals: pd.DataFrame) -> pd.DataFrame:
    """Check long sum, short sum and net exposure by date and class."""
    return (
        monthly_vals.groupby(["Date", "AssetClass"], as_index=False)
        .agg(
            long_sum=("SkewWeight", lambda s: s[s > 0].sum()),
            short_sum=("SkewWeight", lambda s: s[s < 0].sum()),
            net=("SkewWeight", "sum"),
        )
        .sort_values(["Date", "AssetClass"])
        .reset_index(drop=True)
    )



def monthly_turnover(monthly_vals: pd.DataFrame) -> pd.DataFrame:
    """Compute one-way turnover from month-to-month weight changes."""
    w = monthly_vals[["Date", "AssetClass", "Ticker", "SkewWeight"]].copy()
    w = w.sort_values(["AssetClass", "Ticker", "Date"]).reset_index(drop=True)

    w["PrevWeight"] = w.groupby(["AssetClass", "Ticker"])["SkewWeight"].shift(1).fillna(0.0)
    w["AbsDelta"] = (w["SkewWeight"] - w["PrevWeight"]).abs()

    # Divide by 2 to convert total absolute reallocation into one-way turnover.
    turnover = (
        w.groupby(["Date", "AssetClass"], as_index=False)["AbsDelta"].sum().rename(columns={"AbsDelta": "Turnover"})
    )
    turnover["Turnover"] = turnover["Turnover"] / 2.0
    return turnover

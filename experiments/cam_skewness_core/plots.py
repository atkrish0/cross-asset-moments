"""Plot helpers for cross-asset skewness workflow."""

from __future__ import annotations

import math
from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd

from .analytics import drawdown_series



def plot_sample_returns_and_skew(all_data: pd.DataFrame, sample_tickers: Sequence[str]) -> None:
    sample = all_data[all_data["Ticker"].isin(sample_tickers)].copy()

    plt.figure(figsize=(12, 4))
    for ticker in sample_tickers:
        s = sample[sample["Ticker"] == ticker]
        if not s.empty:
            plt.plot(s["Date"], s["LogReturn"].cumsum(), label=ticker)
    plt.title("Cumulative Log Returns")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Log Return")
    plt.legend()
    plt.show()

    plt.figure(figsize=(12, 4))
    for ticker in sample_tickers:
        s = sample[sample["Ticker"] == ticker]
        if not s.empty:
            plt.plot(s["Date"], s["Skew"], label=ticker)
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Rolling Skew")
    plt.xlabel("Date")
    plt.ylabel("Skew")
    plt.legend()
    plt.show()



def plot_skew_distribution_box(all_data: pd.DataFrame) -> None:
    data = [
        all_data.loc[all_data["AssetClass"] == ac, "Skew"].dropna().values
        for ac in sorted(all_data["AssetClass"].unique())
    ]
    labels = sorted(all_data["AssetClass"].unique())

    plt.figure(figsize=(12, 4))
    plt.boxplot(data, labels=labels, showfliers=False)
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Skew Distribution by Asset Class (Outliers Hidden)")
    plt.ylabel("Skew")
    plt.show()



def plot_latest_skew_and_weights(monthly_vals: pd.DataFrame, asset_class: str = "Commodities") -> pd.DataFrame:
    latest_date = monthly_vals["Date"].max()
    snap = monthly_vals[(monthly_vals["AssetClass"] == asset_class) & (monthly_vals["Date"] == latest_date)].copy()
    snap = snap.sort_values("EOMSkew")

    plt.figure(figsize=(11, 5))
    plt.bar(snap["Ticker"], snap["EOMSkew"], color="orange")
    plt.title(f"{asset_class} ETFs - Latest Skew Values")
    plt.xlabel("ETFs")
    plt.ylabel("Skew")
    plt.show()

    plt.figure(figsize=(11, 5))
    colors = ["royalblue" if x >= 0 else "firebrick" for x in snap["SkewWeight"]]
    plt.bar(snap["Ticker"], snap["SkewWeight"], color=colors)
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title(f"{asset_class} ETFs - Portfolio Weights Based on Latest Skew")
    plt.xlabel("ETFs")
    plt.ylabel("Portfolio Weight")
    plt.show()

    return snap



def plot_sample_weight_history(monthly_vals: pd.DataFrame, tickers: Sequence[str]) -> None:
    plt.figure(figsize=(14, 5))
    styles = {
        tickers[0]: {"color": "blue", "marker": "x"},
        tickers[1]: {"color": "orange", "marker": "o"},
        tickers[2]: {"color": "green", "marker": "+"},
    }

    for ticker in tickers:
        s = monthly_vals[monthly_vals["Ticker"] == ticker]
        if s.empty:
            continue
        style = styles.get(ticker, {})
        plt.plot(
            s["Date"],
            s["SkewWeight"],
            label=ticker,
            linewidth=1.8,
            markersize=6,
            marker=style.get("marker", None),
            color=style.get("color", None),
        )

    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Portfolio Weights")
    plt.xlabel("Date")
    plt.ylabel("Weight")
    plt.legend()
    plt.show()



def plot_asset_class_cum_returns(asset_portfolios: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 6))
    for ac in sorted(asset_portfolios["AssetClass"].unique()):
        ac_data = asset_portfolios[asset_portfolios["AssetClass"] == ac]
        plt.plot(ac_data["Date"], ac_data["PortfolioReturn"].cumsum(), label=ac)
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Skew Portfolios by Asset Class")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.show()



def plot_asset_class_strategy_vs_market(asset_portfolios: pd.DataFrame, ncols: int = 3) -> None:
    classes = sorted(asset_portfolios["AssetClass"].unique())
    n = len(classes)
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows), sharex=False)
    if nrows == 1:
        axes = [axes] if ncols == 1 else axes

    flat_axes = axes.flatten() if hasattr(axes, "flatten") else axes

    for i, ac in enumerate(classes):
        ax = flat_axes[i]
        ac_data = asset_portfolios[asset_portfolios["AssetClass"] == ac]
        ax.plot(ac_data["Date"], ac_data["PortfolioReturn"].cumsum(), label="Skew Portfolio", color="blue")
        ax.plot(ac_data["Date"], ac_data["MktReturn"].cumsum(), label="Market", color="orange")
        ax.axhline(0, color="black", linestyle="--", linewidth=1)
        ax.set_title(ac)
        ax.set_xlabel("Date")
        ax.set_ylabel("Cumulative Return")
        ax.legend()

    for j in range(i + 1, len(flat_axes)):
        flat_axes[j].axis("off")

    plt.tight_layout()
    plt.show()



def plot_global_factor(gcf: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(gcf["Date"], gcf["Return"].cumsum(), label="Global Skew Factor")
    plt.plot(gcf["Date"], gcf["MktReturn"].cumsum(), label="Global Market Return")
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Global Portfolio")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.show()



def plot_global_drawdown(gcf: pd.DataFrame) -> None:
    dd = drawdown_series(gcf.set_index("Date")["Return"])
    plt.figure(figsize=(12, 4))
    plt.plot(dd.index, dd.values, color="firebrick")
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title("Global Skew Factor Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.show()



def plot_turnover_by_class(turnover: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 5))
    for ac in sorted(turnover["AssetClass"].unique()):
        s = turnover[turnover["AssetClass"] == ac]
        plt.plot(s["Date"], s["Turnover"], label=ac)
    plt.title("Monthly One-Way Turnover by Asset Class")
    plt.xlabel("Date")
    plt.ylabel("Turnover")
    plt.legend()
    plt.show()

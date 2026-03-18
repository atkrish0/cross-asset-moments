"""Performance analytics and regression attribution helpers."""

from __future__ import annotations

import datetime as dt
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .data_loader import load_ticker_yf



def run_asset_class_alpha_beta(asset_portfolios: pd.DataFrame) -> pd.DataFrame:
    """OLS by asset class: strategy return vs class market return."""
    rows = []
    for ac in sorted(asset_portfolios["AssetClass"].unique()):
        ac_data = asset_portfolios[asset_portfolios["AssetClass"] == ac].dropna(
            subset=["PortfolioReturn", "MktReturn"]
        )
        X = sm.add_constant(ac_data["MktReturn"])
        y = ac_data["PortfolioReturn"]
        model = sm.OLS(y, X).fit()
        rows.append(
            {
                "Asset Class": ac,
                "alpha": model.params.get("const", np.nan),
                "alpha_p": model.pvalues.get("const", np.nan),
                "beta": model.params.get("MktReturn", np.nan),
                "beta_p": model.pvalues.get("MktReturn", np.nan),
                "R2": model.rsquared,
            }
        )
    return pd.DataFrame(rows).sort_values("Asset Class").reset_index(drop=True)



def run_equity_factor_regression(
    asset_portfolios: pd.DataFrame,
    factor_tickers: Sequence[str],
    history_days: int,
    end_date: pd.Timestamp | None = None,
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper, pd.DataFrame]:
    """Regress equity strategy return on market plus factor ETFs."""
    if end_date is None:
        end_date = pd.Timestamp(dt.datetime.now().date()) + pd.Timedelta(days=1)
    start_date = end_date - pd.Timedelta(days=history_days)

    factor_frames = []
    for ticker in factor_tickers:
        f = load_ticker_yf(ticker, start_date, end_date)
        if not f.empty:
            factor_frames.append(f)

    if not factor_frames:
        raise ValueError("Could not load factor ETFs from yfinance.")

    equity_factors = pd.concat(factor_frames, ignore_index=True)
    factor_wide = equity_factors.pivot(index="Date", columns="Ticker", values="LogReturn").reset_index()

    equity = asset_portfolios[asset_portfolios["AssetClass"] == "Equity"].copy()
    equity = equity.merge(factor_wide, on="Date", how="left")

    reg_cols = ["MktReturn"] + list(factor_tickers)
    reg_df = equity.dropna(subset=["PortfolioReturn"] + reg_cols).copy()

    X = sm.add_constant(reg_df[reg_cols])
    y = reg_df["PortfolioReturn"]
    model = sm.OLS(y, X).fit()
    return model, reg_df



def build_coef_table(model: sm.regression.linear_model.RegressionResultsWrapper) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Coef": model.params,
            "StdErr": model.bse,
            "t": model.tvalues,
            "p": model.pvalues,
            "CI_L": model.conf_int()[0],
            "CI_U": model.conf_int()[1],
        }
    ).round(6)



def drawdown_series(returns: pd.Series) -> pd.Series:
    """Compute drawdown series from return stream."""
    wealth = returns.fillna(0.0).cumsum()
    running_max = wealth.cummax()
    return wealth - running_max



def _annualization_factor(dates: pd.Series) -> float:
    if len(dates) < 2:
        return 252.0
    date_delta = (dates.max() - dates.min()).days
    if date_delta <= 0:
        return 252.0
    obs = len(dates)
    return obs * 365.25 / date_delta



def performance_table(
    returns_df: pd.DataFrame,
    date_col: str,
    ret_col: str,
    group_col: str,
) -> pd.DataFrame:
    """Trader-friendly performance summary by group."""
    rows = []
    for grp, df in returns_df.groupby(group_col):
        r = df[ret_col].dropna()
        if r.empty:
            continue
        ann_factor = _annualization_factor(df[date_col])

        ann_return = r.mean() * ann_factor
        ann_vol = r.std(ddof=0) * np.sqrt(ann_factor)
        sharpe = np.nan if ann_vol == 0 else ann_return / ann_vol

        dd = drawdown_series(r)
        max_dd = dd.min()
        hit_rate = (r > 0).mean()

        rows.append(
            {
                group_col: grp,
                "Obs": len(r),
                "AnnReturn": ann_return,
                "AnnVol": ann_vol,
                "Sharpe": sharpe,
                "MaxDrawdown": max_dd,
                "HitRate": hit_rate,
            }
        )

    return pd.DataFrame(rows).sort_values(group_col).reset_index(drop=True)

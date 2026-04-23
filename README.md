# Cross-Asset Moments: Realized Skewness Strategy (Living Technical Reference)

This document is the authoritative project reference for the cross-asset skewness strategy implemented in this repository.

## 1) Problem Context and Objective

The project tests whether **cross-sectional realized skewness** can be used as a systematic long-short signal across liquid ETFs from multiple asset classes.

Core hypothesis:

- Assets with relatively more negative recent skewness (within their asset class) may subsequently outperform assets with relatively more positive skewness.

Practical objective:

- Build a bias-aware, monthly rebalanced, class-neutral signal portfolio.
- Aggregate class sleeves into a global factor.
- Evaluate whether returns are distinct from broad market and common equity style factors.

Current implementation state:

- **Implemented (legacy):** `experiments/cam_skewness_v1.ipynb` (original draft; Alpaca-era style).
- **Implemented (single-notebook source-style):** `experiments/cam_skewness_v2.ipynb` (yfinance replacement, monolithic flow).
- **Implemented (modular production-style):** `experiments/cam_skewness_v3.ipynb` + `experiments/cam_skewness_core/*.py`.

---

## 2) Conceptual Authority and Fidelity

External conceptual authority:

- [Cross Asset Skew - A Trading Strategy](https://dm13450.github.io/2024/02/08/Cross-Asset-Skew-A-Trading-Strategy.html)

### 2.1 Core alignment with source workflow

The implemented workflow matches the source at the strategy core:

1. Compute rolling realized skew per asset.
2. Take end-of-month skew snapshot.
3. Rank cross-sectionally within each asset class.
4. Convert ranks to class-neutral long-short weights.
5. Activate next trading day (no look-ahead).
6. Aggregate to class and then global portfolio.
7. Run regression-based attribution (alpha/beta; equity factor extension).

### 2.2 Intentional divergences

- **Data vendor:** `yfinance` instead of Alpaca.
- **Date coverage:** local runs can extend beyond source sample window (e.g., through 2026).
- **Engineering controls:** stronger schema normalization and failure handling.
- **Research diagnostics (v3):** added PM/trader analytics (turnover, cost scenarios, drawdown, breadth/utilization views).

These are methodological extensions, not strategy-definition changes.

### 2.3 Source-Concept Checklist (Explicit)

The source article’s conceptual blocks are all represented in this project:

1. **Skew definition and rolling estimator** using return mean/vol over a 256-day window.
2. **Cross-sectional implementation** (relative skew within asset class, not absolute skew level trading).
3. **Monthly rebalance signal timing** using end-of-month skew.
4. **Look-ahead control** by activating weights on the next trading day.
5. **Self-financed class portfolios** with long and short books normalized to +1/-1.
6. **Class-level backtest vs class market proxy** (equal-weight average return in class).
7. **Global aggregation with volatility scaling** to avoid high-vol sleeves dominating.
8. **Alpha/beta attribution** via OLS of class strategy return vs class market return.
9. **Equity factor decomposition** with `MTUM`, `VTV`, `VUG`, `VIG`.
10. **Implementation caveat acknowledgement** that transaction costs/slippage are not explicitly modeled in the base replication.

---

## 3) Data Universe and Hyperparameters

Primary config lives in:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/config.py`

Key parameters:

- `LOOKBACK = 256`
- `HISTORY_DAYS = 3650`
- `VOL_TARGET = 0.10`

Universe sleeves:

- `Equity`, `FI`, `Commodities`, `Other`, `Ccy`

### 3.1 Why SPY, GLD, AGG are repeatedly shown

These three are used as **diagnostic anchors** in plots:

- `SPY`: broad US equity beta proxy.
- `GLD`: liquid commodity/precious metals proxy.
- `AGG`: broad US investment-grade bond aggregate proxy.

They are chosen for interpretability across risk regimes, not because the strategy is restricted to those names.

Notebook anchor (`v3`):

```python
from experiments.cam_skewness_core.config import SAMPLE_TICKERS, SAMPLE_WEIGHT_TICKERS
# SAMPLE_TICKERS = ["SPY", "GLD", "AGG"]
```

---

## 4) Data Engineering Layer (Ingestion, Normalization, QA)

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/data_loader.py`

### 4.1 Canonical schema

Data are normalized to:

- `Date, Ticker, close, open, NextOpen, LogReturn, AssetClass`

Notebook-equivalent core logic (`v2`/`v3`):

```python
df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
df["close"] = pd.to_numeric(df[close_col], errors="coerce")
df["open"] = pd.to_numeric(df["Open"], errors="coerce")
df["NextOpen"] = df["open"].shift(-1)
df["LogReturn"] = np.log(df["close"] / df["close"].shift(1))
```

### 4.2 Why this matters statistically

- Cross-sectional ranking is very sensitive to column inconsistencies and timestamp drift.
- `Adj Close` preference protects return continuity around distributions/splits.
- Explicit empty-schema and failure capture reduce silent downstream bias.

### 4.3 Implemented QA outputs

- universe summary: listed vs unique tickers and duplicates.
- ticker-level start/end/obs/missing-return rate.
- load failure table by `(AssetClass, Ticker, Error)`.

Notebook anchor (`v3`):

```python
all_data, failures = load_universe_yf(UNIVERSE, HISTORY_DAYS)
quality = data_quality_summary(all_data)
```

---

## 5) Signal Engineering: Realized Skewness

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/signal.py::add_skew_features`

### 5.1 Estimator definition

For returns \(r_t\) and rolling window length \(N\):

\[
\mu_t = \frac{1}{N}\sum_{i=t-N+1}^{t} r_i,
\qquad
\sigma_t = \sqrt{\frac{1}{N-1}\sum_{i=t-N+1}^{t}(r_i-\mu_t)^2}
\]

Standardized return:

\[
z_t = \frac{r_t - \mu_t}{\sigma_t}
\]

Daily skew contribution:

\[
\text{SkewDay}_t = z_t^3
\]

Rolling realized skew signal:

\[
\text{Skew}_t = \frac{1}{N}\sum_{i=t-N+1}^{t} \text{SkewDay}_i
\]

Notebook anchor:

```python
grp = out.groupby("Ticker", sort=False)["LogReturn"]
out["Avg"] = grp.transform(lambda s: s.rolling(window=lookback, min_periods=lookback).mean())
out["Dev"] = grp.transform(lambda s: s.rolling(window=lookback, min_periods=lookback).std())
out["SkewDay"] = ((out["LogReturn"] - out["Avg"]) / out["Dev"]) ** 3
out["Skew"] = out.groupby("Ticker", sort=False)["SkewDay"].transform(
    lambda s: s.rolling(window=lookback, min_periods=lookback).mean()
)
```

### 5.2 Interpretation

- Signal is expected to be jumpy due to cubic amplification of tail moves.
- Large crisis periods (e.g., 2020) create strong asymmetry and regime shifts in rolling skew.

---

## 6) Cross-Sectional Portfolio Construction

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/signal.py::build_monthly_signal_table`
- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/signal.py::add_rank_weights`

### 6.1 Monthly signal extraction and activation date

For each `(Month, AssetClass, Ticker)`:

- `EOMSkew = last(Skew)` at month-end.
- `NextDate = next trading day` (activation date).

### 6.2 Rank-to-weight transform

Within each `(Date, AssetClass)` cross-section, with rank \(\operatorname{rank}(\cdot)\):

\[
w_i^{raw} = \operatorname{rank}(\text{EOMSkew}_i; \text{descending}) - \frac{n+1}{2}
\]

Normalize to balanced long-short exposure:

\[
w_i = \frac{w_i^{raw}}{\sum_j |w_j^{raw}|/2}
\]

This enforces:

\[
\sum_{i: w_i>0} w_i = +1,
\qquad
\sum_{i: w_i<0} w_i = -1,
\qquad
\sum_i w_i = 0
\]

Notebook anchor:

```python
monthly_vals["SkewWeightRaw"] = monthly_vals.groupby(["Date", "AssetClass"])["EOMSkew"].transform(
    lambda s: s.rank(ascending=False, method="average") - ((len(s) + 1) / 2)
)
```

---

## 7) Execution Mapping and Daily PnL Assembly

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/backtest.py::apply_monthly_weights_to_daily`
- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/backtest.py::compute_asset_class_returns`

### 7.1 Anti-look-ahead mechanism

- Monthly weight is attached to `NextDate`, then forward-filled daily within ticker.

### 7.2 Return equations

Per ticker-day:

\[
r_{i,t}^{w} = w_{i,t}^{FF} \cdot r_{i,t}
\]

Per class-day:

\[
R_{c,t}^{strat} = \sum_{i \in c} r_{i,t}^{w},
\qquad
R_{c,t}^{mkt} = \frac{1}{|c|}\sum_{i \in c} r_{i,t}
\]

Notebook anchor:

```python
all_data_weights["WeightedReturn"] = all_data_weights["SkewWeightFF"] * all_data_weights["LogReturn"]
asset_portfolios = all_data_weights.groupby(["Date", "AssetClass"], as_index=False).agg(
    PortfolioReturn=("WeightedReturn", "sum"),
    MktReturn=("LogReturn", "mean")
)
```

### 7.3 Important fix in v2

A key correction was applied to avoid false zero-returns before weights activate:

- use `sum(min_count=1)` and active-name count,
- set class `PortfolioReturn` to `NaN` when no active names.

This prevents volatility understatement and downstream scaling explosions.

---

## 8) Risk Normalization and Global Factor Construction

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/backtest.py::compute_global_factor`

### 8.1 Vol targeting logic

For each class \(c\):

\[
\hat\sigma^{strat}_{c,t} = \text{rolling-std}(R^{strat}_{c,t}),
\qquad
\hat\sigma^{mkt}_{c,t} = \text{rolling-std}(R^{mkt}_{c,t})
\]

Normalized returns:

\[
\tilde R^{strat}_{c,t} = \sigma^* \frac{R^{strat}_{c,t}}{\hat\sigma^{strat}_{c,t}},
\qquad
\tilde R^{mkt}_{c,t} = \sigma^* \frac{R^{mkt}_{c,t}}{\hat\sigma^{mkt}_{c,t}}
\]

Global aggregates:

\[
R_t^{global} = \frac{1}{C}\sum_{c=1}^{C}\tilde R^{strat}_{c,t},
\qquad
R_t^{global,mkt} = \frac{1}{C}\sum_{c=1}^{C}\tilde R^{mkt}_{c,t}
\]

Notebook anchor:

```python
gcf = (
    asset_portfolios.dropna(subset=["NormReturn", "NormMarketReturn"])
    .groupby("Date", as_index=False)
    .agg(Return=("NormReturn", "mean"), MktReturn=("NormMarketReturn", "mean"))
)
```

### 8.2 Why this step exists

Without vol normalization, high-vol sleeves dominate global PnL mechanically. The normalization makes the cross-class blend risk-aware instead of notional-weighted.

### 8.3 Exact Source vs Local Scaling Detail

The source article scales both strategy and market sleeves by the **same class volatility estimate derived from strategy returns**:

\[
\tilde R^{mkt}_{c,t,\text{source}} = \sigma^* \frac{R^{mkt}_{c,t}}{\hat\sigma^{strat}_{c,t}}
\]

In this repository:

- `v2` is intended to remain as close as possible to source-style replication.
- `v3` supports a cleaner implementation where market can be scaled by its own sleeve volatility (default in modular helper), with an explicit switch available:

```python
compute_global_factor(..., scale_market_with_strategy_vol=True)
```

This difference can materially change the shape/level of the global market comparison line and should always be stated when interpreting results.

---

## 9) Statistical Attribution Layer

Implementation:

- `/Users/atheeshkrishnan/AK/DEV/cross-asset-moments/experiments/cam_skewness_core/analytics.py`

### 9.1 Class alpha/beta model

For each asset class:

\[
R^{strat}_{c,t} = \alpha_c + \beta_c R^{mkt}_{c,t} + \epsilon_{c,t}
\]

Estimated by OLS (`statsmodels`).

### 9.2 Equity factor extension

On the equity sleeve:

\[
R^{strat}_{eq,t} = \alpha + \beta_m R^{mkt}_{eq,t} + \beta_{MTUM} f_{MTUM,t} + \beta_{VTV} f_{VTV,t} + \beta_{VUG} f_{VUG,t} + \beta_{VIG} f_{VIG,t} + \epsilon_t
\]

Notebook anchor:

```python
reg_cols = ["MktReturn", "MTUM", "VTV", "VUG", "VIG"]
X = sm.add_constant(reg_df[reg_cols])
y = reg_df["PortfolioReturn"]
model = sm.OLS(y, X).fit()
```

Observed from current run (as shared in notebook outputs):

- `R^2 ≈ 0.116` for equity multi-factor regression.
- Intercept not statistically significant.
- Several style exposures statistically significant.

Interpretation: equity sleeve return is only partially explained by these style factors; residual component remains.

---

## 10) Trader/PM Analytics in Current Implementation

Primary analytics in `v3` (plus selected `v1`-inspired charts):

- latest commodity skew cross-section bars.
- latest commodity rank-weight bars.
- sample ticker weight histories.
- class cumulative strategy curves.
- class strategy-vs-market panels.
- global factor vs global market.
- drawdown curve.
- monthly turnover by class.
- cost-adjusted cumulative return scenarios.
- breadth/utilization diagnostics (improved from flat-line view).

Interpretive emphasis:

- signal efficacy by sleeve, not only globally.
- regime behavior and concentration risk.
- implementation drag (turnover/cost) before claiming deployability.

---

## 11) Section-by-Section Outcome Snapshot (from current outputs)

Based on generated notebook outputs shared during validation (data-vendor and sample-window dependent):

1. **Data and schema checks passed** with expected columns and non-empty universe pull.
2. **Skew feature creation behaved as expected** (large negative excursions around stress periods).
3. **Weight neutrality checks are exact** (`long_sum=+1`, `short_sum=-1`, `net≈0` across groups).
4. **Class-level performance is heterogeneous** (commodity sleeve was strongest in the shown run, other sleeves mixed).
5. **Global factor is sensitive to scaling details**, and was the main area where implementation bugs materially changed chart shape.
6. **Attribution shows low-to-moderate explanatory power in shown runs**, with equity sleeve having meaningful factor loadings but not fully explained return.

---

## 12) Major Bugs/Errors and Fixes

### 12.1 `KeyError: 'Ticker'` during loader/diagnostics (v2)

Symptom:

- downstream filtering like `all_data[all_data['Ticker'] == "SPY"]` failed.

Root cause:

- transformations via unstable `groupby.apply` paths could drop/reshape schema.

Fix:

- switched to `groupby.transform` pattern for rolling features to preserve original schema.
- hardened loader to always return canonical columns, including empty-schema fallback.

### 12.2 `ModuleNotFoundError: No module named 'experiments'` (v3)

Root cause:

- notebook kernel cwd/path not guaranteeing project root import visibility.

Fix:

- added project-root `sys.path` bootstrap in v3 import cell.
- added `experiments/__init__.py`.

### 12.3 Distorted global factor chart (v2)

Symptom:

- global skew cumulative line unrealistically high versus expected scale.

Root cause:

- pre-activation periods were treated as zero strategy return (instead of missing), shrinking rolling vol denominator and inflating normalized returns.

Fix:

- class aggregation now uses active-name guard and `sum(min_count=1)`.
- missing pre-activation periods excluded from scaling/aggregation.

### 12.4 Over-simplistic breadth plot

Symptom:

- flat lines conveyed little information.

Fix:

- replaced with richer breadth diagnostics (range/heatmap/stat summaries) in v3 analytics flow.

---

## 13) Current Caveats and Assumptions

Material caveats affecting interpretation:

- `yfinance` is convenient but not institutional-grade point-in-time data.
- no transaction-level fill simulation (slippage/latency/borrow/fees not modeled endogenously in core replication).
- benchmark definitions are equal-weight class proxies, not tradable total-return composites.
- regressions use OLS with standard errors; no HAC/Newey-West corrections by default.
- duplicate ticker entries in raw universe definition are deduplicated at load time.
- inferred execution assumption is effectively frictionless rebalance at/near next session open (source article similarly notes trading-cost simplification).

Interpret results as **research-factor evidence**, not directly executable live PnL.

---

## 14) Why These Methods Were Chosen

- **Rolling skew estimator:** directly targets asymmetry, the stated signal hypothesis.
- **Cross-sectional rank construction:** robust against level differences across assets.
- **Class-neutral normalization:** isolates relative skew effect from class directionality.
- **Monthly rebalance with next-day activation:** practical cadence and no look-ahead.
- **Vol targeting before global aggregation:** controls cross-sleeve risk concentration.
- **Regression attribution:** separates potential alpha from known market/style exposures.

---

## 15) Interview-Ready Project Narrative

### Situation

The project started as a research replication exercise of a published cross-asset skewness strategy, but the original implementation context and data vendor assumptions were different from the local setup. The practical challenge was to preserve strategy logic while migrating to a free and accessible data source (`yfinance`) and still produce trustworthy inference for portfolio construction and attribution.

### Task

Build a technically defensible end-to-end research pipeline that:

- reproduces the core skewness signal and monthly cross-sectional backtest mechanics,
- enforces look-ahead-safe execution timing,
- supports attribution (alpha/beta and multi-factor equity decomposition),
- and is robust enough to discuss in a technical interview from both quant and engineering perspectives.

### Action

#### 1. Replication and signal implementation

- Implemented rolling realized skewness using a two-layer rolling transformation:
  - rolling mean/std on daily log returns,
  - rolling mean of cubic standardized returns.
- Preserved source-consistent construction:
  - month-end signal extraction,
  - cross-sectional rank conversion to class-neutral long/short weights,
  - next-trading-day activation.

#### 2. Data engineering hardening

- Built canonical ingestion/cleaning logic to normalize inconsistent Yahoo schemas (multi-index columns, date naming differences, adjusted close handling, duplicates, numeric coercion).
- Added explicit failure diagnostics (`AssetClass`, `Ticker`, `Error`) and coverage summaries to avoid silent data loss.

#### 3. Backtest correctness and risk normalization

- Implemented daily return mapping from monthly weights via activation-date merge and within-ticker forward fill.
- Added a critical guard for pre-activation periods (no active weights):
  - prevent zero-imputation from contaminating class return series,
  - avoid denominator collapse in volatility scaling.
- Constructed global factor via class-level volatility normalization and equal-risk aggregation.

#### 4. Statistical attribution and explainability

- Ran per-class OLS regressions:
  - `PortfolioReturn ~ const + MktReturn`.
- Extended equity sleeve with style-factor regression:
  - `PortfolioReturn ~ const + MktReturn + MTUM + VTV + VUG + VIG`.
- Reported coefficients, p-values, confidence intervals, and fit diagnostics for interpretability.

#### 5. Engineering evolution for maintainability

- Converted notebook-heavy flow into a modular architecture (`v3`) with separable concerns:
  - `data_loader`, `signal`, `backtest`, `analytics`, `plots`.
- Kept a source-style single-notebook variant (`v2`) for conceptual parity and easier auditability.
- Resolved critical implementation issues:
  - `KeyError: 'Ticker'` schema drift,
  - import path failures for `experiments` package,
  - distorted global-factor chart from invalid early-period aggregation.

### Result

- Delivered two production-usable research artifacts:
  - `v2`: source-style single-notebook replication with yfinance,
  - `v3`: modular, extensible research framework with richer diagnostics.
- Achieved exact weight neutrality sanity checks at rebalance level (`long=+1`, `short=-1`, `net≈0`).
- Produced stable attribution outputs that are interpretable in interview settings (factor exposures, significance, partial explanatory power rather than overclaimed alpha).
- Improved confidence in result validity by explicitly handling failure modes that can bias backtests (schema mismatch, missing activation states, scaling artifacts).

### Technical Interview Talking Points

- **Modeling depth:** why third-moment asymmetry is modeled and why rank-based cross-sectional construction is robust.
- **Bias control:** next-day activation and handling of missing-weight periods.
- **Validation discipline:** neutrality checks, class-vs-market comparisons, drawdown/turnover/cost lenses.
- **Attribution literacy:** distinguishing standalone signal from market/style exposures via regression diagnostics.
- **Engineering quality:** migration from monolithic notebook to reusable module stack without changing economic logic.

---

## 16) Living-Document Update Rules

When the project evolves, update this README by preserving the same flow:

1. data generation + QA
2. signal math
3. portfolio mapping
4. risk scaling
5. attribution
6. outcomes and caveats
7. bug/fix log

Any future method changes should document:

- exact equation or transformation changed,
- code location (`notebook cell` and/or `module function`),
- expected effect on interpretation.

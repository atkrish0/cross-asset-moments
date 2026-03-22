# cam_skewness_v3: End-to-End Project Explanation

## 1. Project Overview

This project implements and validates a **systematic cross-asset skewness long-short strategy** inspired by the source write-up on cross-asset skew as a trading signal.

The core idea is:
- Measure each ETF's recent **realized skewness** from daily returns.
- Rank ETFs **within each asset class** by this skew metric.
- Go long the more negatively skewed names and short the more positively skewed names.
- Rebalance monthly and hold daily between rebalance dates.
- Evaluate class-level and global performance, then run regressions to understand exposure vs market/factor benchmarks.

This notebook is a practical replication using **Yahoo Finance (`yfinance`)** and robust data/shape handling.

## 2. Research Hypothesis and Intuition

### 2.1 Hypothesis
A cross-sectional skewness signal contains predictive information beyond broad market moves, and can be harvested through market-neutral long-short portfolios.

### 2.2 Intuition
Skewness captures asymmetry in return distributions:
- Negative skew implies more frequent/extreme downside-tail behavior.
- Positive skew implies more upside-tail behavior.

By ranking skew cross-sectionally (within asset class), the strategy attempts to isolate a relative pricing effect rather than directional beta.

## 3. Universe and Configuration

### 3.1 Parameters
- `LOOKBACK = 256`
- `HISTORY_DAYS = 3650` (~10 years)
- `VOL_TARGET = 0.10`

### 3.2 Universe Construction
Asset classes:
- Equity
- FI (Fixed Income)
- Commodities
- Other
- Ccy (Currencies)

The universe is based on the original implementation structure and includes roughly ~60 ETFs (with dedupe logic to handle repeats like `EWG`).

### 3.3 Why this setup makes sense
- 256 trading days is a common annual-scale rolling horizon.
- Multi-asset design tests whether skew effects generalize beyond equities.
- Class-wise ranking/normalization avoids cross-asset comparability issues in raw returns and volatility.

## 4. Data Ingestion Layer (Yahoo Finance)

## 4.1 Loader goals
The loader is designed for reliability first:
- Normalize Yahoo schema variations.
- Handle MultiIndex columns safely.
- Enforce required columns (`Date`, `Open`, `Adj Close/Close`).
- Return a strict common schema.
- Track failed downloads and continue processing.

### 4.2 Standardized output schema
Per ticker, output columns are:
- `Date`
- `Ticker`
- `close` (adjusted close when available)
- `open`
- `NextOpen`
- `LogReturn`

After class assignment:
- `AssetClass`

### 4.3 Implementation details
- `LogReturn = log(close_t / close_{t-1})`
- `NextOpen = open_{t+1}` (prepared for next-day execution interpretation)
- Data sorted/deduped by date.
- Universe pull dedupes repeated tickers via `sorted(set(tickers))`.

### 4.4 Observed output
From your run:
- Loader version: `yf_loader_v3_2026_03_14`
- `all_data.shape = (145696, 7)`
- Columns: `['Date', 'Ticker', 'close', 'open', 'NextOpen', 'LogReturn', 'AssetClass']`

Interpretation:
- Healthy data size for a 10-year multi-ETF sample.
- Schema integrity checks passed.

## 5. Signal Engineering: Rolling Skewness

### 5.1 Signal formula
For each ticker and date:

\[
z_t = \frac{r_t - \mu_t}{\sigma_t}
\]

\[
\text{SkewDay}_t = z_t^3
\]

\[
\text{Skew}_t = \text{rolling mean of } \text{SkewDay}_t \text{ over 256 days}
\]

where:
- \(r_t\) is daily log return,
- \(\mu_t\) and \(\sigma_t\) are rolling mean/std over `LOOKBACK`.

### 5.2 Why this construction
- Cubing standardized returns emphasizes tail asymmetry.
- Rolling mean smooths daily noise into a tradable signal.
- Ticker-wise transform preserves cross-sectional comparability.

### 5.3 Observed output
From your run:
- Post-feature shape: `(116058, 11)`
- Added columns: `Avg`, `Dev`, `SkewDay`, `Skew`

Interpretation:
- Row count drops as expected due to rolling warmup requirements.
- Feature pipeline is structurally correct.

## 6. Diagnostics on SPY / GLD / AGG

Two checks are plotted:
1. Cumulative log returns for representative ETFs.
2. Rolling skew series for the same tickers.

### 6.1 What these plots verify
- Price-return series are realistic and continuous.
- Skew series exhibit expected jumpiness due to third-moment amplification.
- Regime shifts (e.g., stress periods) appear in skew behavior.

### 6.2 Interpretation of your output
- Return paths look plausible for 2018–2026.
- Skew spikes are large but expected in this model family.

## 7. Backtest Construction

## 7.1 Rebalance timeline
- Compute end-of-month skew snapshot per ticker/class.
- Compute `NextDate` as the next available trading day per ticker.
- Signals are activated on `NextDate` to avoid look-ahead bias.

### 7.2 Monthly signal table
`monthly_vals` includes:
- `Month`, `AssetClass`, `Ticker`
- `Date` (month-end signal date)
- `NextDate` (activation date)
- `EOMSkew`

### 7.3 Ranking and raw weights
Within each `(Date, AssetClass)`:
- Rank `EOMSkew` descending and center ranks:

\[
w_i^{raw} = \text{rank}_i - \frac{n+1}{2}
\]

This makes:
- More negative skew -> larger positive weight.
- More positive skew -> larger negative weight.

### 7.4 Normalization
Normalize raw weights so:
- Sum of positive weights = `+1`
- Sum of negative weights = `-1`
- Net class exposure = `0`

### 7.5 Output interpretation
Your sample rows correctly show:
- Activation on next trading day.
- Symmetric long/short sizing from centered ranks.
- Zero-centered exposure structure.

## 8. Weight Activation and Daily Forward Fill

### 8.1 Mechanism
- Join monthly weights on activation date (`NextDate -> Date`).
- Forward-fill within each ticker until next monthly refresh.

### 8.2 Why this is correct
- Converts monthly decisions into daily-held positions.
- Preserves realistic execution timing.

### 8.3 Interpretation of your sample output
- Pre-activation rows show `NaN` weight.
- First activation day shows concrete weight.
- Subsequent days forward-filled correctly.

This matches source methodology and avoids look-ahead.

## 9. Daily Portfolio Return Aggregation by Asset Class

### 9.1 Construction
- `WeightedReturn = SkewWeightFF * LogReturn`
- Group by `(Date, AssetClass)`:
  - `PortfolioReturn = sum(WeightedReturn)`
  - `MktReturn = mean(LogReturn)` (equal-weight class benchmark)

### 9.2 Why this benchmark
`MktReturn` serves as an internal, class-level market proxy for alpha/beta attribution.

### 9.3 Interpretation of early rows
Early strategy return can be near `0` before full activation, while market benchmark moves immediately; this is expected.

## 10. Class-Level Cumulative Performance

### 10.1 Plot meaning
Cumulative sums of class `PortfolioReturn` visualize which asset classes contribute most to strategy PnL.

### 10.2 Interpretation of your run
- Commodities: strongest contributor.
- Equity/FI: positive but smaller.
- Ccy: modest positive.
- Other: near flat/slightly negative.

This dispersion is common and conceptually consistent with the source narrative.

## 11. Volatility Scaling and Global Factor Construction

### 11.1 Scaling logic
Per asset class:
- Compute rolling strategy volatility:

\[
\text{Vol}_t = \text{rolling std}(\text{PortfolioReturn}, 256)
\]

- Scale returns to target volatility:

\[
\text{NormReturn}_t = 0.10 \cdot \frac{\text{PortfolioReturn}_t}{\text{Vol}_t}
\]

\[
\text{NormMarketReturn}_t = 0.10 \cdot \frac{\text{MktReturn}_t}{\text{Vol}_t}
\]

Then average across classes per date to form `gcf` (global skew factor and global market comparator).

### 11.2 Interpretation of your output
- Global skew factor is smoother and steadily positive.
- Global market comparator is much more volatile.

### 11.3 Important caveat
`NormMarketReturn` uses **strategy vol** as denominator, not market vol. This can amplify comparator moves when strategy vol is low. The code is valid, but interpretation of the orange comparator should acknowledge this scaling choice.

## 12. Performance Attribution (Class-Level OLS)

### 12.1 Model
For each asset class:

\[
\text{PortfolioReturn}_t = \alpha + \beta \cdot \text{MktReturn}_t + \epsilon_t
\]

### 12.2 Your results summary
From the reported table:
- Alphas are small and mostly not significant.
- Betas are near zero to modest, with low R² values.

Interpretation:
- Strategy returns are not strongly explained by simple class benchmark movements.
- This supports the idea of a distinct cross-sectional skew signal component.

## 13. Equity Factor Extension

### 13.1 Setup
Load factor proxy ETFs:
- `MTUM` (momentum)
- `VTV` (value)
- `VUG` (growth)
- `VIG` (quality/dividend-style proxy)

Regress Equity strategy returns on:
- `MktReturn`, `MTUM`, `VTV`, `VUG`, `VIG`.

### 13.2 Your regression outputs
Key reported values:
- `R² ≈ 0.116`
- Intercept not significant.
- Significant factor exposures across market and style proxies.

### 13.3 Interpretation
- Factors explain a modest share of equity strategy variation.
- No strong residual intercept after controls.
- Coefficients are conditional exposures (collinearity among ETFs can affect sign/magnitude interpretation).

## 14. Compact Coefficient Summary

The compact table correctly reproduces the OLS model coefficients, t-stats, p-values, and confidence intervals in a report-friendly format.

This is useful for:
- presentation,
- auditability,
- resume/project documentation.

## 15. Validation Checks (Portfolio Neutrality)

### 15.1 Checks performed
For each `(Date, AssetClass)` at rebalance:
- `long_sum = sum(weights > 0)`
- `short_sum = sum(weights < 0)`
- `net = sum(all weights)`

### 15.2 Your output
- `long_sum = 1.0`
- `short_sum = -1.0`
- `net = 0.0`
consistently across the sample.

### 15.3 Significance
This is a strong implementation validation:
- normalization works exactly as intended,
- class-level dollar neutrality is maintained throughout.

## 16. Alignment vs Source Project

### 16.1 What aligns strongly
- Signal definition and rolling construction.
- Monthly cross-sectional ranking by class.
- Next-day activation and daily hold mechanics.
- Class/global portfolio aggregation.
- OLS-based attribution workflow.

### 16.2 Expected differences
- Data provider differences (`yfinance` vs source provider) can change exact return paths/coefs.
- Sample endpoint reflects current run date, not static publication window.
- Market comparator scaling choice in section 11 affects relative plot amplitude.

## 17. What This Project Demonstrates

This implementation demonstrates competency in:
- multi-asset data engineering,
- robust ETL for market data,
- rolling higher-moment signal modeling,
- cross-sectional portfolio construction,
- bias-aware backtest mechanics (next-day execution),
- volatility targeting,
- statistical attribution and interpretation,
- reproducibility/sanity validation.

## 18. Limitations and Suggested Next Enhancements

### 18.1 Current limitations
- No transaction costs/slippage/borrow constraints.
- No turnover diagnostics yet.
- Comparator scaling nuance (strategy-vol denominator for market leg).
- Non-robust OLS covariance by default.

### 18.2 High-impact next steps
- Add transaction cost model and turnover tracking.
- Add robust/HAC standard errors in regressions.
- Compare multiple lookbacks (e.g., 126/256/504).
- Use market-vol scaling for comparator or leave benchmark unscaled for interpretability.
- Add out-of-sample split and rolling stability diagnostics.

## 19. Final Verdict

Based on code review and observed outputs, the project is:
- **Conceptually sound**,
- **Implementation-consistent**, and
- **Faithful to the source methodology** with expected vendor/sample differences.

It is a valid and defensible replication of a cross-asset skewness strategy pipeline.

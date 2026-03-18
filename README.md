# cross-asset-moments

Comprehensive research repository for cross-asset higher-moment strategies, with current focus on a **systematic realized-skewness long-short model** across ETFs.

## 1) Project Purpose

This project studies whether **cross-sectional realized skewness** contains tradable signal across multiple asset classes.

Core research question:
- If we rank assets by recent skewness within an asset class, does going **long negative-skew assets** and **short positive-skew assets** produce economically meaningful returns?

The implementation is designed to be:
- replicable,
- auditable,
- modular,
- practical from a trader/PM perspective.

## 2) Ground-Truth Reference and Alignment

Primary reference implementation/inspiration:
- [Cross Asset Skew - A Trading Strategy (Dean Markwick)](https://dm13450.github.io/2024/02/08/Cross-Asset-Skew-A-Trading-Strategy.html)

### Alignment summary
The `v2` notebook follows the same core pipeline as the reference:
1. Build rolling skew per asset.
2. Use month-end skew cross-section by asset class.
3. Rank and convert to class-neutral long/short weights.
4. Activate weights on next trading day (anti-look-ahead).
5. Aggregate class and global returns.
6. Run alpha/beta and equity factor regressions.

### Intentional differences
- Data source is `yfinance` (free) instead of Alpaca.
- Robust data QA, schema guards, and modularized code are added.
- Additional trader-focused diagnostics are included (turnover, cost scenarios, drawdown).

## 3) Repository Structure

```text
cross-asset-moments/
├─ README.md
├─ LICENSE
├─ ref/
└─ experiments/
   ├─ __init__.py
   ├─ cam_skewness_v1.ipynb                  # original notebook version
   ├─ cam_skewness_v2.ipynb                  # current modular production notebook
   ├─ cam_skewness_v2.md                     # detailed narrative companion
   ├─ cam_skewness_core/                     # extracted implementation modules
   │  ├─ __init__.py
   │  ├─ config.py                           # parameters + universe
   │  ├─ data_loader.py                      # yfinance ingestion + QA
   │  ├─ signal.py                           # skew signal + monthly signal table
   │  ├─ backtest.py                         # weight activation + returns + turnover
   │  ├─ analytics.py                        # regression + performance stats
   │  └─ plots.py                            # reusable visualization blocks
   └─ misc/
      ├─ cam_mean_v1.ipynb
      ├─ cam_variance_v1.ipynb
      └─ cam_kurtosis_v1.ipynb
```

## 4) End-to-End Methodology (What, How, Why)

## 4.1 Universe and Configuration

### What was done
- Defined ETF universe across 5 sleeves:
  - Equity
  - FI (fixed income)
  - Commodities
  - Other
  - Ccy (currency)
- Set key hyperparameters:
  - `LOOKBACK = 256`
  - `HISTORY_DAYS = 3650`
  - `VOL_TARGET = 0.10`

### Why
- 256 days approximates 1 trading year and stabilizes moment estimates.
- Multi-asset setup tests signal transferability beyond a single class.
- Vol target enables risk-balanced aggregation across sleeves.

## 4.2 Data Ingestion

### What was done
- Implemented canonical loader in `data_loader.py`:
  - pulls daily OHLC data from Yahoo,
  - uses adjusted close where available for return continuity,
  - computes `LogReturn`, `NextOpen`, and standardized schema,
  - tracks failures (ticker-level diagnostics).

### Why
- Raw vendor outputs vary by ticker/version and can silently break research.
- Canonical schema prevents downstream logic drift.
- Explicit failures improve reproducibility and debugging.

## 4.3 Signal Engineering (Realized Skew)

### What was done
For each ticker:
- compute rolling mean/std of log returns over `N=256`,
- standardize daily return,
- cube standardized return,
- apply rolling mean to create skew signal.

Formula used:

\[
S_t = \frac{1}{N} \sum_{i=t-N+1}^{t} \left(\frac{r_i - \mu_t}{\sigma_t}\right)^3
\]

### Why
- Cubic moment captures asymmetry in return tails.
- Cross-sectional ranking of skew is the actionable signal in reference methodology.

## 4.4 Portfolio Construction and Rebalancing

### What was done
- Extracted month-end (`EOM`) skew per ticker and class.
- Set activation date to next trading day per ticker.
- Ranked assets within each `(Date, AssetClass)`.
- Converted centered ranks into long/short weights.
- Normalized so each class is self-financed:
  - long sum = `+1`
  - short sum = `-1`
  - net = `0`

### Why
- Prevent look-ahead bias.
- Keep exposures class-neutral and comparable.
- Isolate relative-value skew effect from outright directional beta.

## 4.5 Daily Return Aggregation

### What was done
- Forward-filled active monthly weights to daily frequency.
- Computed class portfolio return:
  - `PortfolioReturn = sum(weight * LogReturn)`
- Computed class market proxy:
  - `MktReturn = mean(LogReturn)`

### Why
- Strategy decisions are monthly, but PnL accrues daily.
- Class benchmark required for alpha/beta attribution.

## 4.6 Global Portfolio Construction

### What was done
- Computed rolling class volatilities.
- Vol-normalized class strategy and market returns.
- Averaged normalized class returns into global factor.

### Why
- Equal notional weighting can over-concentrate risk in volatile sleeves.
- Vol normalization makes cross-class aggregation risk-aware.

## 4.7 Attribution and Factor Analysis

### What was done
1. Class-level OLS:
   \[
   r^{strat}_{t} = \alpha + \beta \cdot r^{mkt}_{t} + \epsilon_t
   \]
2. Equity multi-factor OLS with proxies:
   - `MktReturn`, `MTUM`, `VTV`, `VUG`, `VIG`

### Why
- Distinguish true alpha from repackaged market/factor exposure.
- Assess how much skew returns are explained by common style premia.

## 5) Analysis and Backtesting Outputs (Trader/PM View)

The v2 notebook emphasizes practical diagnostics, not just cumulative return charts.

## 5.1 Data Integrity and Coverage
- Universe summary (`listed`, `unique`, duplicates).
- Ticker-level history coverage and missingness.
- Class utilization diagnostics.

## 5.2 Signal Diagnostics
- Sample cumulative return paths (SPY/GLD/AGG).
- Rolling skew traces (regime sensitivity and jump behavior).
- Skew distribution by asset class.

## 5.3 Execution Diagnostics
- Latest commodity skew cross-section bar chart.
- Latest commodity portfolio weights bar chart.
- Sample ticker weight history (SPY/AGG/GLD).

## 5.4 Performance Diagnostics
- Class-level cumulative strategy returns.
- Class-level strategy vs market panel comparison.
- Global strategy vs market cumulative comparison.
- Global strategy drawdown profile.

## 5.5 Implementation Friction Diagnostics
- Monthly one-way turnover by sleeve.
- Cost-adjusted scenario curves (5/10/20 bps) to approximate implementation drag.

## 6) Notebook Design Philosophy (v2)

`cam_skewness_v2.ipynb` is intentionally a **thin orchestration layer**:
- sectioned like a research report,
- explains intent in markdown,
- calls functional blocks from `experiments/cam_skewness_core`.

Benefits:
- cleaner notebook,
- easier debugging,
- reusable code for batch/reruns,
- fewer stale-cell and copy/paste errors.

## 7) How to Run

## 7.1 Environment requirements
Python 3.10+ recommended with:
- `numpy`
- `pandas`
- `matplotlib`
- `statsmodels`
- `yfinance`
- `ipykernel`

## 7.2 Run sequence
1. Open `experiments/cam_skewness_v2.ipynb`.
2. Restart kernel.
3. Run cells top-to-bottom.
4. Confirm first cell prints project root path.
5. Review section outputs in order.

## 7.3 Operational notes
- Internet access is required for Yahoo pulls.
- Results can drift over time as data updates.
- Vendor differences vs Alpaca are expected.

## 8) Major Bugs/Errors Encountered and Fixes

This section documents key failures found during development and the exact remediation.

| Issue | Symptom | Root Cause | Fix Implemented |
|---|---|---|---|
| Import path failure | `ModuleNotFoundError: No module named 'experiments'` in notebook | Kernel started from a cwd not containing repo root on `sys.path` | Added root-discovery + `sys.path` bootstrap in import cell; added `experiments/__init__.py` |
| Empty universe shape failure | `KeyError: 'Ticker'` when sorting loaded data | No frames loaded; empty DataFrame without expected schema | Loader now returns canonical empty schema and explicit diagnostics before downstream steps |
| Yahoo schema drift | Missing expected columns for some downloads | `yfinance` outputs differ by version/ticker (MultiIndex, Date/Datetime differences) | Added robust schema normalization in `clean_yf` |
| Signal-step column loss | `KeyError: 'Ticker'` in diagnostics after skew construction | `groupby.apply` behavior causing schema/index instability in some pandas contexts | Replaced with `groupby.transform`-based feature construction |
| Stale notebook state confusion | Old logic running despite file edits | Kernel retained previous function definitions | Added version stamps/explicit restart guidance; modularized logic into `.py` to reduce cell-state drift |
| Hardcoded provider credentials (legacy path) | Security/reproducibility risk | Prior Alpaca-style inline secrets | Removed provider-coupled secrets from working pipeline; standardized on free `yfinance` |
| Flat/uninformative breadth visualization | Constant horizontal lines with low informational value | Breadth mostly static over time in this universe | Replaced with min/median/max coverage view + yearly utilization heatmap |
| Global comparator scaling ambiguity | Hard-to-interpret market comparator behavior | Scaling market leg by strategy vol can distort comparator magnitude | Made scaling logic explicit and configurable; defaulted to market-vol scaling in modular backtest helper |

## 9) Key Assumptions and Limitations

- No explicit transaction-cost model in base strategy return (separate scenario analysis provided).
- No borrow constraints/locate availability modeling.
- ETF survivorship/history limitations from free data source.
- Equal-weight class benchmark is a practical proxy, not a full canonical factor model.
- OLS defaults are sensitive to residual assumptions; robust covariance not yet default.

## 10) What Was Added Beyond the Reference

To make the strategy useful for actual portfolio workflow, v2 adds:
- modular codebase,
- explicit data QA layer,
- richer EDA and execution diagnostics,
- turnover and cost sensitivity,
- cleaner attribution tables,
- robust sanity assertions for neutrality constraints.

## 11) Future Improvements

- Add robust/HAC errors to regressions.
- Add purged walk-forward or anchored out-of-sample validation.
- Add explicit slippage and spread model by asset class.
- Add rank decay and holding-period sensitivity.
- Add scenario dashboard for leverage and class risk budgets.

## 12) Current Status

`cam_skewness_v2.ipynb` is the current production notebook for skewness replication and analysis.

It is:
- aligned with the reference methodology at the core level,
- improved in engineering robustness,
- expanded for trader/PM interpretation.

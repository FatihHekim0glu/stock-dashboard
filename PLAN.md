# Build plan

This file tracks the build from scaffold to deployment. Each section maps to one or more commits.

## Data Acquired

- [x] yfinance wrapper in `src/data.fetch_ohlcv` with chrome-impersonating `curl_cffi` session
- [x] `diskcache` layer under `.yfcache/` keyed on `(ticker, start, end, trading_day_stamp)`
- [x] Stooq CSV fallback when yfinance returns empty or raises
- [x] `trading_day_stamp` helper that rolls over at 21:00 UTC
- [x] Defensive error handling — empty frames, partial ranges, delisted tickers, network timeout

## EDA / Exploration

- [ ] Notebook pulling 3 tickers (one liquid US large-cap, one ETF, one low-volume name)
- [ ] Missing trading-day check against `pandas_market_calendars` NYSE schedule
- [ ] Return distribution plots — daily log returns, QQ vs normal, autocorrelation
- [ ] Datatype sanity check — OHLCV all float64, index is tz-naive `DatetimeIndex`

## Baseline Built

_Skipped — superseded by Main Build below, which shipped the full app in one pass._

- [~] Bare Streamlit app — ticker input box, single line chart of close price
- [~] No indicators, no caching, no fallback — just prove the data round-trips to the browser

## Main Build

- [x] Implement 5 indicators in `src/indicators.py` — SMA, EMA, Bollinger, RSI, MACD — plus render volume bars directly from the OHLCV frame
- [x] Summary statistics module — CAGR, vol, Sharpe, max drawdown, best/worst day
- [x] Candlestick vs line toggle in the price subplot
- [x] Per-indicator on/off checkboxes in the sidebar
- [x] Synchronized hover across price, indicator, and volume subplots
- [x] Plotly `rangebreaks` to hide weekends and US market holidays (via `pandas_market_calendars` XNYS)

## Testing & CI

- [x] Closed-form indicator tests — constant series, monotone series, single-value series
- [x] TA-Lib oracle tests gated behind `pytest.importorskip("talib")`
- [x] Financial-math tests — CAGR with known inputs, max drawdown on a hand-drawn equity curve
- [x] GitHub Actions workflow on push and PR, matrix on Python 3.11 and 3.12 (live CI badge link updates after first push to a public repo)

## Polish

- [ ] README screenshots of the running app — one wide, one mobile width
- [ ] ScreenToGif capture of typical usage at `docs/demo.gif`, under 5 MB
- [x] Mermaid architecture diagram in README "How it works"
- [ ] Hand-curated `requirements.txt` — pinned versions, no transitive bloat from `pip freeze`

## Pushed to GitHub & Deployed

- [ ] Public GitHub repository with descriptive About text and topics
- [ ] Hugging Face Space deployed from the repo
- [ ] Live demo link added to README, replacing the TODO marker
- [ ] "May take ~15 seconds to wake on first visit" note next to the link

## Stretch goals (after Definition of Done)

- [ ] SPY benchmark overlay, normalized to 100 at the start of the selected range
- [ ] CSV export button for the loaded OHLCV plus computed indicator columns
- [ ] Dividend markers on the price chart, sourced from yfinance `Ticker.dividends`
- [ ] Regime indicator — bull/bear shading driven by the 200-day SMA crossover

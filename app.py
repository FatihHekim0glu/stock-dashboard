"""Streamlit entry point — single-ticker stock dashboard.

Run locally with: streamlit run app.py

Cache topology (three layers, see cached_* helpers below):

  1. cached_fetch              — 6h  TTL, just the network call
  2. cached_indicators_only    — 24h TTL, derives indicator columns
  3. cached_stats              — 24h TTL, derives Summary (rf_annual only here)

Critically, the indicator/stats layers do NOT receive the DataFrame as an
argument. Hashing a 2500-row frame on every Streamlit rerun would dominate
cost; instead the downstream layers re-call the upstream layer, which is
itself cached. The `day_stamp` (from data.trading_day_stamp()) is threaded
through every layer's key so caches invalidate together once per UTC day
after 21:00.

Splitting indicators and stats means changing `rf_annual` only invalidates
the (cheap) stats layer; the (expensive) indicator recompute is preserved.

The Plotly figure is built at render time without caching: building from a
cached DataFrame takes <100ms, and pickling a multi-MB figure into
st.cache_data was actually slower than rebuilding.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src import charts, data, indicators, stats
from src.data import DataFetchError

# Anchor the date picker to NYSE local "today" rather than the server's
# clock. Otherwise a Hugging Face Space (UTC) at 22:00 ET on day N already
# sees day N+1 UTC and offers a date that has zero NYSE bars; conversely an
# Asian-hosted instance at 06:00 ET caps the user one day behind reality.
_NY_TZ = ZoneInfo("America/New_York")

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,15}$")

st.set_page_config(
    page_title="Stock Dashboard",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Cache layers
# ---------------------------------------------------------------------------


_FETCH_TTL_SECONDS = 21_600  # 6h — daily bars only refresh after market close
_DERIVED_TTL_SECONDS = 86_400  # 24h — indicators + stats only need same-day freshness


@st.cache_data(ttl=_FETCH_TTL_SECONDS, max_entries=128, show_spinner="Fetching OHLCV...")
def cached_fetch(ticker: str, start, end, day_stamp: str) -> pd.DataFrame:
    return data.fetch_ohlcv(ticker, start, end)


@st.cache_data(ttl=_DERIVED_TTL_SECONDS, max_entries=512)
def cached_indicators_only(
    ticker: str,
    start,
    end,
    day_stamp: str,
    indicators_selected: tuple[str, ...],
) -> pd.DataFrame:
    df = cached_fetch(ticker, start, end, day_stamp).copy()
    close = df["Close"]

    if "SMA 20" in indicators_selected:
        df["sma_20"] = indicators.sma(close, length=20)
    if "SMA 50" in indicators_selected:
        df["sma_50"] = indicators.sma(close, length=50)
    if "EMA 12" in indicators_selected:
        df["ema_12"] = indicators.ema(close, length=12)
    if "EMA 26" in indicators_selected:
        df["ema_26"] = indicators.ema(close, length=26)
    if "Bollinger Bands" in indicators_selected:
        bb = indicators.bollinger_bands(close, length=20, k=2.0)
        df["bb_upper"] = bb["upper"]
        df["bb_middle"] = bb["middle"]
        df["bb_lower"] = bb["lower"]
    if "RSI" in indicators_selected:
        df["rsi"] = indicators.rsi(close, length=14)
    if "MACD" in indicators_selected:
        macd_df = indicators.macd(close, fast=12, slow=26, signal=9)
        df["macd"] = macd_df["macd"]
        # charts.py reads MACD-prefixed names so the columns don't collide with
        # generic words like "signal" / "histogram" if the df picks up other data.
        df["macd_signal"] = macd_df["signal"]
        df["macd_hist"] = macd_df["histogram"]

    return df


@st.cache_data(ttl=_DERIVED_TTL_SECONDS, max_entries=512)
def cached_stats(
    ticker: str,
    start,
    end,
    day_stamp: str,
    rf_annual: float,
) -> stats.Summary:
    df = cached_fetch(ticker, start, end, day_stamp)
    return stats.summary(df["Close"], rf_annual=rf_annual)


def build_figure_for_render(
    df: pd.DataFrame,
    indicators_selected: tuple[str, ...],
    candlestick: bool,
):
    label_to_tag = {
        "SMA 20": "sma_20",
        "SMA 50": "sma_50",
        "EMA 12": "ema_12",
        "EMA 26": "ema_26",
        "Bollinger Bands": "bb",
        "RSI": "rsi",
        "MACD": "macd",
    }
    chart_indicators = tuple(
        label_to_tag[label] for label in indicators_selected if label in label_to_tag
    )
    return charts.build_figure(df, indicators=chart_indicators, candlestick=candlestick)


# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

INDICATOR_OPTIONS = [
    "SMA 20",
    "SMA 50",
    "EMA 12",
    "EMA 26",
    "Bollinger Bands",
    "RSI",
    "MACD",
]

with st.sidebar:
    st.header("Inputs")
    ticker = st.text_input("Ticker", value="AAPL").strip().upper()

    today = datetime.now(_NY_TZ).date()
    five_years_ago = today - timedelta(days=5 * 365)
    earliest = date(1970, 1, 1)
    start_date = st.date_input(
        "Start date", value=five_years_ago, min_value=earliest, max_value=today
    )
    end_date = st.date_input("End date", value=today, min_value=earliest, max_value=today)

    selected_indicators = st.multiselect(
        "Indicators",
        options=INDICATOR_OPTIONS,
        default=INDICATOR_OPTIONS,
    )

    candlestick = st.toggle("Candlestick view", value=True)

    rf_annual = st.number_input(
        "Risk-free rate",
        value=0.0,
        step=0.001,
        format="%.4f",
        help="Annualized; used only for Sharpe",
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _is_finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _fmt_pct(value, decimals: int = 2) -> str:
    if value is None or not _is_finite(value):
        return "—"
    return f"{value * 100:.{decimals}f}%"


def _fmt_num(value, decimals: int = 2) -> str:
    if value is None or not _is_finite(value):
        return "—"
    return f"{value:.{decimals}f}"


st.title("Stock Dashboard")

# Validate inputs.
if not ticker:
    st.error("Ticker cannot be empty.")
    st.stop()

if not _TICKER_RE.match(ticker):
    st.error(
        "Ticker must contain only letters, digits, '.', '-' (1-15 chars). Examples: AAPL, BRK-B, BP.L"
    )
    st.stop()

if end_date <= start_date:
    st.error("End date must be after start date.")
    st.stop()

indicators_tuple = tuple(selected_indicators)
day_stamp = data.trading_day_stamp()

try:
    df = cached_indicators_only(
        ticker,
        start_date,
        end_date,
        day_stamp,
        indicators_tuple,
    )
    summary = cached_stats(
        ticker,
        start_date,
        end_date,
        day_stamp,
        rf_annual,
    )
except DataFetchError as e:
    st.error(f"Could not load data for {ticker}: {e}")
    st.stop()

if summary.trading_days < 5:
    st.warning(
        f"Only {summary.trading_days} trading day(s) in range — volatility and Sharpe will be unreliable."
    )

fig = build_figure_for_render(df, indicators_tuple, candlestick)

st.plotly_chart(fig, use_container_width=True)

# Metric cards — first row.
# Explicit ratios + small gap let Streamlit auto-stack on narrow viewports
# while preserving the 5-across desktop layout.
row1 = st.columns([1, 1, 1, 1, 1], gap="small")
row1[0].metric("Cumulative Return", _fmt_pct(summary.cumulative_return))
row1[1].metric("CAGR", _fmt_pct(summary.annualized_return))
row1[2].metric("Volatility", _fmt_pct(summary.annualized_volatility))
row1[3].metric(
    f"Sharpe (rf={rf_annual * 100:.2f}%)",
    _fmt_num(summary.sharpe),
)
row1[4].metric("Max DD", _fmt_pct(summary.max_drawdown))

# Metric cards — second row.
row2 = st.columns([1, 1, 1, 1, 1], gap="small")
row2[0].metric("Best Day", _fmt_pct(summary.best_day))
row2[1].metric("Worst Day", _fmt_pct(summary.worst_day))
row2[2].metric("Trading Days", f"{summary.trading_days}")
row2[3].metric("Start Date", summary.start.strftime("%Y-%m-%d"))
row2[4].metric("End Date", summary.end.strftime("%Y-%m-%d"))

"""
candle_engine.py
────────────────
Fetches BSE SENSEX data via yfinance and detects candlestick patterns
for four timeframes: 1m, 2m, 5m, 15m.

Note on intervals: Yahoo Finance (and therefore yfinance) only supports a
fixed set of intraday intervals — 1m, 2m, 5m, 15m, 30m, 60m/90m. "3m" is
NOT a valid interval and will fail silently or raise, which is why it was
replaced with "2m" here.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── Timeframe config ──────────────────────────────────────────────────────────
# zoom_candles = how many candles to show in the zoomed tab view
TIMEFRAMES = [
    {"label": "1m",  "interval": "1m",  "period": "1d",  "zoom_candles": 30},
    {"label": "2m",  "interval": "2m",  "period": "5d",  "zoom_candles": 25},
    {"label": "5m",  "interval": "5m",  "period": "5d",  "zoom_candles": 24},
    {"label": "15m", "interval": "15m", "period": "5d",  "zoom_candles": 20},
]

SENSEX_TICKER = "^BSESN"   # Yahoo Finance symbol for BSE Sensex

# Intervals Yahoo Finance actually supports for intraday data.
VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}


# ── Data fetching ─────────────────────────────────────────────────────────────
def fetch_sensex_data(interval: str, period: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Download OHLCV data.
    Returns (dataframe, error_message) — dataframe is None on failure and
    error_message explains why (invalid interval, no data returned, market
    closed with nothing cached, network/API error, etc).
    """
    if interval not in VALID_INTERVALS:
        msg = f"'{interval}' is not a Yahoo Finance interval (valid: {sorted(VALID_INTERVALS)})"
        print(f"[fetch_sensex_data] {msg}")
        return None, msg

    try:
        ticker = yf.Ticker(SENSEX_TICKER)
        df = ticker.history(interval=interval, period=period)

        if df is None or df.empty:
            msg = ("No candles returned by Yahoo Finance for this interval/period. "
                   "Common causes: market is closed and nothing recent is cached, "
                   "or Yahoo doesn't carry this granularity for ^BSESN right now.")
            return None, msg

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)

        # Convert index to IST
        if df.index.tzinfo is not None:
            df.index = df.index.tz_convert(IST)
        else:
            df.index = df.index.tz_localize("UTC").tz_convert(IST)

        # Filter to market hours 9:15–15:30
        df = df.between_time("09:15", "15:30")

        if df.empty:
            msg = "Data was returned but nothing fell within 9:15–15:30 IST after timezone conversion."
            return None, msg

        return df, None
    except Exception as e:
        print(f"[fetch_sensex_data] Error for {interval}: {e}")
        return None, str(e)


# ── Pattern helpers ───────────────────────────────────────────────────────────
def body(c) -> float:
    return abs(c["Close"] - c["Open"])

def upper_wick(c) -> float:
    return c["High"] - max(c["Open"], c["Close"])

def lower_wick(c) -> float:
    return min(c["Open"], c["Close"]) - c["Low"]

def is_bullish(c) -> bool:
    return c["Close"] > c["Open"]

def is_bearish(c) -> bool:
    return c["Close"] < c["Open"]

def candle_range(c) -> float:
    return c["High"] - c["Low"] if c["High"] != c["Low"] else 1e-9

def body_ratio(c) -> float:
    return body(c) / candle_range(c)

def is_doji(c, thresh=0.08) -> bool:
    return body_ratio(c) < thresh

def is_spinning_top(c, low=0.08, high=0.25) -> bool:
    return low <= body_ratio(c) <= high

def is_hammer(c) -> bool:
    b = body(c)
    lw = lower_wick(c)
    uw = upper_wick(c)
    return lw >= 2 * b and uw < b * 0.6 and b > 0

def is_inverted_hammer(c) -> bool:
    b = body(c)
    uw = upper_wick(c)
    lw = lower_wick(c)
    return uw >= 2 * b and lw < b * 0.6 and b > 0

def is_shooting_star(c) -> bool:
    return is_inverted_hammer(c) and is_bearish(c)

def is_hanging_man(c) -> bool:
    return is_hammer(c) and is_bearish(c)

def is_marubozu(c, thresh=0.85) -> bool:
    return body_ratio(c) >= thresh

def is_bullish_engulfing(prev, curr) -> bool:
    return (is_bearish(prev) and is_bullish(curr)
            and curr["Open"] <= prev["Close"]
            and curr["Close"] >= prev["Open"])

def is_bearish_engulfing(prev, curr) -> bool:
    return (is_bullish(prev) and is_bearish(curr)
            and curr["Open"] >= prev["Close"]
            and curr["Close"] <= prev["Open"])

def is_morning_star(c1, c2, c3) -> bool:
    """Three-candle reversal: big red, small body/doji, big green."""
    return (is_bearish(c1) and body_ratio(c1) > 0.5
            and is_spinning_top(c2) or is_doji(c2)
            and is_bullish(c3) and body_ratio(c3) > 0.4
            and c3["Close"] > (c1["Open"] + c1["Close"]) / 2)

def is_evening_star(c1, c2, c3) -> bool:
    return (is_bullish(c1) and body_ratio(c1) > 0.5
            and (is_spinning_top(c2) or is_doji(c2))
            and is_bearish(c3) and body_ratio(c3) > 0.4
            and c3["Close"] < (c1["Open"] + c1["Close"]) / 2)

def is_three_white_soldiers(candles) -> bool:
    if len(candles) < 3: return False
    return all(is_bullish(c) and body_ratio(c) > 0.5 and upper_wick(c) < body(c) * 0.3
               for c in candles[-3:])

def is_three_black_crows(candles) -> bool:
    if len(candles) < 3: return False
    return all(is_bearish(c) and body_ratio(c) > 0.5 and lower_wick(c) < body(c) * 0.3
               for c in candles[-3:])

def is_pin_bar_bull(c, wick_ratio=2.5) -> bool:
    """Long lower wick, small body near top."""
    b = body(c)
    lw = lower_wick(c)
    uw = upper_wick(c)
    return b > 0 and lw >= wick_ratio * b and uw < lw * 0.4

def is_pin_bar_bear(c, wick_ratio=2.5) -> bool:
    b = body(c)
    uw = upper_wick(c)
    lw = lower_wick(c)
    return b > 0 and uw >= wick_ratio * b and lw < uw * 0.4

def momentum_direction(candles, n=3) -> str:
    """Look at last n candles for momentum."""
    recent = candles[-n:] if len(candles) >= n else candles
    bull_count = sum(1 for c in recent if is_bullish(c))
    bear_count = sum(1 for c in recent if is_bearish(c))
    if bull_count >= n:   return "bull"
    if bear_count >= n:   return "bear"
    if bull_count > bear_count: return "mild_bull"
    if bear_count > bull_count: return "mild_bear"
    return "neut"


# ── Core pattern detector ────────────────────────────────────────────────────
def detect_patterns(df: pd.DataFrame, tf_label: str) -> dict:
    """
    Analyse the last few candles and return:
      signal   : "bull" | "bear" | "neut"
      patterns : list[str]   — pattern names detected
      analysis : str         — one-line explanation
      action   : str         — suggested option action
    """
    if df is None or len(df) < 2:
        return {"signal": "neut", "patterns": ["Insufficient data"],
                "analysis": "Need more candles.", "action": "WAIT"}

    rows = [df.iloc[i] for i in range(len(df))]
    c  = rows[-1]   # latest candle
    p1 = rows[-2] if len(rows) >= 2 else c
    p2 = rows[-3] if len(rows) >= 3 else p1

    patterns_found = []
    signals = []

    # ── Single-candle ──────────────────────────────────────────────
    if is_doji(c):
        patterns_found.append("Doji")
        signals.append("neut")

    if is_spinning_top(c):
        patterns_found.append("Spinning Top")
        signals.append("neut")

    if is_hammer(c) and is_bullish(c):
        patterns_found.append("Hammer ↑")
        signals.append("bull")

    if is_hanging_man(c):
        patterns_found.append("Hanging Man ↓")
        signals.append("bear")

    if is_shooting_star(c):
        patterns_found.append("Shooting Star ↓")
        signals.append("bear")

    if is_inverted_hammer(c) and is_bullish(c):
        patterns_found.append("Inverted Hammer ↑")
        signals.append("bull")

    if is_pin_bar_bull(c):
        patterns_found.append("Bullish Pin Bar ↑")
        signals.append("bull")

    if is_pin_bar_bear(c):
        patterns_found.append("Bearish Pin Bar ↓")
        signals.append("bear")

    if is_marubozu(c) and is_bullish(c):
        patterns_found.append("Bullish Marubozu ↑")
        signals.append("bull")

    if is_marubozu(c) and is_bearish(c):
        patterns_found.append("Bearish Marubozu ↓")
        signals.append("bear")

    # ── Two-candle ────────────────────────────────────────────────
    if is_bullish_engulfing(p1, c):
        patterns_found.append("Bullish Engulfing ↑")
        signals.extend(["bull", "bull"])

    if is_bearish_engulfing(p1, c):
        patterns_found.append("Bearish Engulfing ↓")
        signals.extend(["bear", "bear"])

    # ── Three-candle ──────────────────────────────────────────────
    if len(rows) >= 3:
        if is_morning_star(p2, p1, c):
            patterns_found.append("Morning Star ↑")
            signals.extend(["bull", "bull"])

        if is_evening_star(p2, p1, c):
            patterns_found.append("Evening Star ↓")
            signals.extend(["bear", "bear"])

        if is_three_white_soldiers(rows):
            patterns_found.append("3 White Soldiers ↑")
            signals.extend(["bull", "bull"])

        if is_three_black_crows(rows):
            patterns_found.append("3 Black Crows ↓")
            signals.extend(["bear", "bear"])

    # ── Momentum fallback ─────────────────────────────────────────
    mom = momentum_direction(rows, n=3)
    if not patterns_found:
        if mom == "bull":
            patterns_found.append("Bull momentum")
            signals.append("bull")
        elif mom == "bear":
            patterns_found.append("Bear momentum")
            signals.append("bear")
        elif mom == "mild_bull":
            patterns_found.append("Mild bullish bias")
            signals.append("bull")
        elif mom == "mild_bear":
            patterns_found.append("Mild bearish bias")
            signals.append("bear")
        else:
            patterns_found.append("No clear pattern")
            signals.append("neut")

    # ── Tally signal ──────────────────────────────────────────────
    bull_v = signals.count("bull")
    bear_v = signals.count("bear")
    if bull_v > bear_v:      final_signal = "bull"
    elif bear_v > bull_v:    final_signal = "bear"
    else:                    final_signal = "neut"

    # ── Analysis text ─────────────────────────────────────────────
    latest_ohlc = (f"O:{c['Open']:.0f}  H:{c['High']:.0f}  "
                   f"L:{c['Low']:.0f}  C:{c['Close']:.0f}")

    analysis_map = {
        "bull": f"Buyers in control on {tf_label}. {latest_ohlc}",
        "bear": f"Sellers in control on {tf_label}. {latest_ohlc}",
        "neut": f"Indecision on {tf_label}. {latest_ohlc}",
    }
    analysis = analysis_map[final_signal]

    action_map = {
        "bull": "BUY CALL (CE)",
        "bear": "BUY PUT  (PE)",
        "neut": "WAIT — No trade",
    }
    action = action_map[final_signal]

    return {
        "signal":   final_signal,
        "patterns": patterns_found,
        "analysis": analysis,
        "action":   action,
    }


# ── Overall verdict from all timeframes ──────────────────────────────────────
def get_overall_verdict(tf_results: dict) -> dict:
    """
    Aggregate signals from all timeframes into one verdict.
    Weights: 15m > 5m > 2m > 1m
    """
    weights = {"1m": 1, "2m": 2, "5m": 3, "15m": 4}
    bull_score = 0
    bear_score = 0
    bull_count = 0
    bear_count = 0

    for tf, result in tf_results.items():
        w = weights.get(tf, 1)
        sig = result.get("signal", "neut")
        if sig == "bull":
            bull_score += w
            bull_count += 1
        elif sig == "bear":
            bear_score += w
            bear_count += 1

    total = bull_score + bear_score
    if total == 0:
        return {
            "direction":  "neut",
            "title":      "No clear direction",
            "subtitle":   "All timeframes showing indecision",
            "confluence": 0,
        }

    bull_pct = bull_score / total

    if bull_pct >= 0.7:
        direction = "bull"
        conf      = bull_count
        title     = "Strong call signal" if bull_count >= 3 else "Bullish bias"
        subtitle  = (f"Bulls dominate on {bull_count}/4 timeframes — "
                     f"look for CE entry on pullback")
    elif bull_pct <= 0.3:
        direction = "bear"
        conf      = bear_count
        title     = "Strong put signal" if bear_count >= 3 else "Bearish bias"
        subtitle  = (f"Bears dominate on {bear_count}/4 timeframes — "
                     f"look for PE entry on bounce")
    else:
        direction = "neut"
        conf      = 0
        title     = "Mixed signals — wait"
        subtitle  = "Timeframes not aligned. No trade is a valid trade."

    return {
        "direction":  direction,
        "title":      title,
        "subtitle":   subtitle,
        "confluence": conf,
    }

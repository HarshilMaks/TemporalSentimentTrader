"""
Technical indicator calculations for TFT Trader.

Provides standalone functions to compute indicators on any OHLCV DataFrame.
The stock_scraper already computes these via pandas_ta during ingestion,
but this module is used by the feature builder and signal engine when
indicators need to be calculated on-the-fly from raw data.
"""

import pandas as pd
import numpy as np


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators to an OHLCV DataFrame.

    Expects columns: Open, High, Low, Close, Volume (or lowercase variants).
    Returns the same DataFrame with indicator columns added.
    """
    df = _normalize_columns(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_sma(df)
    df = add_volume_ratio(df)
    df = add_obv(df)
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure consistent column naming (capitalize first letter)."""
    col_map = {}
    for c in df.columns:
        low = c.lower()
        if low in ("open", "high", "low", "close", "volume"):
            col_map[c] = low.capitalize()
        elif low in ("open_price",):
            col_map[c] = "Open"
        elif low in ("adjusted_close",):
            col_map[c] = "Adj_Close"
    if col_map:
        df = df.rename(columns=col_map)
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI (Relative Strength Index) — 14-period default."""
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD (12, 26, 9) — value, signal line, and histogram."""
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]
    return df


def add_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """Bollinger Bands (20, 2) — upper, lower, and position within band."""
    sma = df["Close"].rolling(window=period).mean()
    std = df["Close"].rolling(window=period).std()
    df["bb_upper"] = sma + std_dev * std
    df["bb_lower"] = sma - std_dev * std
    bb_width = df["bb_upper"] - df["bb_lower"]
    df["bb_position"] = np.where(
        bb_width > 0,
        (df["Close"] - df["bb_lower"]) / bb_width,
        0.5,
    )
    return df


def add_sma(df: pd.DataFrame) -> pd.DataFrame:
    """SMA 50 and SMA 200."""
    df["sma_50"] = df["Close"].rolling(window=50).mean()
    df["sma_200"] = df["Close"].rolling(window=200).mean()
    return df


def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Volume ratio = current volume / 20-day average volume."""
    avg = df["Volume"].rolling(window=period).mean()
    df["volume_ratio"] = df["Volume"] / avg.replace(0, np.nan)
    return df


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """On-Balance Volume."""
    sign = np.sign(df["Close"].diff()).fillna(0)
    df["obv"] = (sign * df["Volume"]).cumsum()
    return df

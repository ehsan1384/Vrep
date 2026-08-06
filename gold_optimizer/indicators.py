"""اندیکاتورهای تکنیکال برای ترکیب استراتژی‌ها."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(series, fast) - ema(series, slow)
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def bollinger(
    series: pd.Series,
    length: int = 20,
    std_mult: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(series, length)
    std = series.rolling(length, min_periods=length).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    lowest = low.rolling(k_period, min_periods=k_period).min()
    highest = high.rolling(k_period, min_periods=k_period).max()
    k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d = k.rolling(d_period, min_periods=d_period).mean()
    return k, d


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr_atr = atr(high, low, close, length)
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(
        alpha=1 / length, adjust=False, min_periods=length
    ).mean() / tr_atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(
        alpha=1 / length, adjust=False, min_periods=length
    ).mean() / tr_atr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def compute_indicator_bundle(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """محاسبه بسته اندیکاتورها بر اساس پارامترهای داده شده."""
    out = df.copy()
    c, h, l = out["close"], out["high"], out["low"]

    out["ema_fast"] = ema(c, params["ema_fast"])
    out["ema_slow"] = ema(c, params["ema_slow"])
    out["rsi"] = rsi(c, params["rsi_len"])
    macd_line, macd_sig, macd_hist = macd(
        c, params["macd_fast"], params["macd_slow"], params["macd_signal"]
    )
    out["macd"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    bb_u, bb_m, bb_l = bollinger(c, params["bb_len"], params["bb_std"])
    out["bb_upper"] = bb_u
    out["bb_mid"] = bb_m
    out["bb_lower"] = bb_l
    stoch_k, stoch_d = stochastic(h, l, c, params["stoch_k"], params["stoch_d"])
    out["stoch_k"] = stoch_k
    out["stoch_d"] = stoch_d
    out["atr"] = atr(h, l, c, params["atr_len"])
    out["adx"] = adx(h, l, c, params["adx_len"])
    return out

"""ترکیب سیگنال‌های اندیکاتورها و ساخت استراتژی‌ها."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


SignalFn = Callable[[pd.DataFrame, dict], pd.Series]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    description: str
    signal_fn: SignalFn


def _align_bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def signal_ema_rsi(df: pd.DataFrame, p: dict) -> pd.Series:
    """کراس EMA + فیلتر RSI."""
    bull = (df["ema_fast"] > df["ema_slow"]) & (df["rsi"] > p["rsi_buy"]) & (
        df["rsi"] < p["rsi_ob"]
    )
    bear = (df["ema_fast"] < df["ema_slow"]) & (df["rsi"] < p["rsi_sell"]) & (
        df["rsi"] > p["rsi_os"]
    )
    sig = np.where(bull, 1, np.where(bear, -1, 0))
    return pd.Series(sig, index=df.index)


def signal_macd_stoch(df: pd.DataFrame, p: dict) -> pd.Series:
    """MACD کراس + Stochastic."""
    macd_up = (df["macd"] > df["macd_signal"]) & (
        df["macd"].shift(1) <= df["macd_signal"].shift(1)
    )
    macd_dn = (df["macd"] < df["macd_signal"]) & (
        df["macd"].shift(1) >= df["macd_signal"].shift(1)
    )
    bull = macd_up & (df["stoch_k"] < p["stoch_ob"]) & (df["stoch_k"] > df["stoch_d"])
    bear = macd_dn & (df["stoch_k"] > p["stoch_os"]) & (df["stoch_k"] < df["stoch_d"])
    sig = np.where(_align_bool(bull), 1, np.where(_align_bool(bear), -1, 0))
    return pd.Series(sig, index=df.index)


def signal_bb_rsi(df: pd.DataFrame, p: dict) -> pd.Series:
    """برگشت از باند بولینگر + RSI."""
    bull = (df["close"] <= df["bb_lower"]) & (df["rsi"] < p["rsi_os_level"])
    bear = (df["close"] >= df["bb_upper"]) & (df["rsi"] > p["rsi_ob_level"])
    sig = np.where(_align_bool(bull), 1, np.where(_align_bool(bear), -1, 0))
    return pd.Series(sig, index=df.index)


def signal_trend_adx(df: pd.DataFrame, p: dict) -> pd.Series:
    """روند EMA با فیلتر قدرت ADX و ATR."""
    strong = df["adx"] > p["adx_min"]
    bull = strong & (df["ema_fast"] > df["ema_slow"]) & (df["close"] > df["ema_fast"])
    bear = strong & (df["ema_fast"] < df["ema_slow"]) & (df["close"] < df["ema_fast"])
    # فقط وقتی کراس تازه یا ادامه روند با RSI میانه
    rsi_ok_long = (df["rsi"] > p["rsi_mid_low"]) & (df["rsi"] < p["rsi_mid_high"])
    rsi_ok_short = rsi_ok_long
    sig = np.where(
        _align_bool(bull & rsi_ok_long),
        1,
        np.where(_align_bool(bear & rsi_ok_short), -1, 0),
    )
    return pd.Series(sig, index=df.index)


def signal_combo_triple(df: pd.DataFrame, p: dict) -> pd.Series:
    """رأی‌گیری سه استراتژی: EMA+RSI، MACD+Stoch، BB+RSI."""
    a = signal_ema_rsi(df, p)
    b = signal_macd_stoch(df, p)
    c = signal_bb_rsi(df, p)
    votes = a + b + c
    # حداقل ۲ رأی هم‌جهت
    sig = np.where(votes >= 2, 1, np.where(votes <= -2, -1, 0))
    return pd.Series(sig, index=df.index)


def signal_momentum_burst(df: pd.DataFrame, p: dict) -> pd.Series:
    """مومنتوم کوتاه: MACD هیستوگرام + Stochastic + ADX."""
    hist_up = df["macd_hist"] > 0
    hist_dn = df["macd_hist"] < 0
    stoch_long = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < p["stoch_ob"])
    stoch_short = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > p["stoch_os"])
    trend = df["adx"] > p["adx_min"]
    bull = trend & hist_up & stoch_long & (df["ema_fast"] > df["ema_slow"])
    bear = trend & hist_dn & stoch_short & (df["ema_fast"] < df["ema_slow"])
    sig = np.where(_align_bool(bull), 1, np.where(_align_bool(bear), -1, 0))
    return pd.Series(sig, index=df.index)


STRATEGIES: list[StrategySpec] = [
    StrategySpec(
        "ema_rsi",
        "کراس EMA سریع/کند + فیلتر RSI",
        signal_ema_rsi,
    ),
    StrategySpec(
        "macd_stoch",
        "کراس MACD + Stochastic",
        signal_macd_stoch,
    ),
    StrategySpec(
        "bb_rsi",
        "برگشت بولینگر + RSI اشباع",
        signal_bb_rsi,
    ),
    StrategySpec(
        "trend_adx",
        "روند EMA با فیلتر ADX",
        signal_trend_adx,
    ),
    StrategySpec(
        "combo_triple",
        "رأی‌گیری سه‌گانه EMA/MACD/BB",
        signal_combo_triple,
    ),
    StrategySpec(
        "momentum_burst",
        "مومنتوم MACD+Stoch+ADX+EMA",
        signal_momentum_burst,
    ),
]


def apply_signal_persistence(signal: pd.Series, hold_bars: int) -> pd.Series:
    """کاهش سیگنال‌های پشت‌سرهم؛ بعد از هر سیگنال، hold_bars کندل صبر می‌کند."""
    if hold_bars <= 1:
        return signal
    out = signal.copy()
    cooldown = 0
    vals = signal.to_numpy()
    result = np.zeros_like(vals)
    for i, v in enumerate(vals):
        if cooldown > 0:
            cooldown -= 1
            result[i] = 0
            continue
        if v != 0:
            result[i] = v
            cooldown = hold_bars - 1
        else:
            result[i] = 0
    out.iloc[:] = result
    return out

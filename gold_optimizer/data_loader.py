"""تولید / بارگذاری داده M1 برای XAUUSD."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    BARS_PER_DAY,
    DATA_DAYS,
    RANDOM_SEED,
    US_SESSION_END_UTC,
    US_SESSION_START_UTC,
)


def generate_synthetic_xauusd(
    days: int = DATA_DAYS,
    seed: int = RANDOM_SEED,
    start_price: float = 2350.0,
) -> pd.DataFrame:
    """داده واقعی‌نما برای طلا با نوسان سشن آمریکا بالاتر."""
    rng = np.random.default_rng(seed)
    n = days * BARS_PER_DAY
    # یک ماه منتهی به ۶ آگوست ۲۰۲۶ (هم‌راستا با تاریخ اجرای تست)
    end = pd.Timestamp("2026-08-06 23:59:00", tz="UTC")
    start = end - pd.Timedelta(minutes=n - 1)
    idx = pd.date_range(start, periods=n, freq="1min")

    # نوسان پایه + تقویت در سشن آمریکا + روند درون‌روزی
    base_vol = 0.00010
    hours = idx.hour
    minutes = idx.minute
    in_us = (hours >= US_SESSION_START_UTC) & (hours < US_SESSION_END_UTC)
    us_boost = np.where(in_us, 1.9, 0.65)

    # هر روز معاملاتی یک جهت غالب تصادفی در سشن آمریکا
    day_ids = (idx.normalize() - idx.normalize()[0]).days
    day_dirs = rng.choice([-1.0, 1.0], size=int(day_ids.max()) + 1)
    trend = np.zeros(n)
    # drift ملایم فقط داخل سشن آمریکا (لبه قابل‌کشف برای روند)
    session_progress = ((hours - US_SESSION_START_UTC) * 60 + minutes).astype(float)
    session_progress = np.clip(session_progress, 0, (US_SESSION_END_UTC - US_SESSION_START_UTC) * 60)
    trend[in_us] = (
        day_dirs[day_ids[in_us]]
        * 0.000035
        * (1.0 + 0.4 * np.sin(session_progress[in_us] / 60.0))
    )

    shocks = rng.normal(0.0, base_vol, size=n) * us_boost + trend
    # چند جهش خبری تصادفی نزدیک شروع سشن آمریکا
    jump_candidates = np.where(in_us & (hours == US_SESSION_START_UTC))[0]
    if len(jump_candidates) > 0:
        jump_idx = rng.choice(
            jump_candidates,
            size=min(len(jump_candidates), max(3, days)),
            replace=False,
        )
        shocks[jump_idx] += day_dirs[day_ids[jump_idx]] * np.abs(
            rng.normal(0.0008, 0.0004, size=len(jump_idx))
        )

    log_prices = np.log(start_price) + np.cumsum(shocks)
    close = np.exp(log_prices)

    # ساخت OHLC از close
    wiggle = np.abs(rng.normal(0.0, 0.15, size=n))
    open_ = np.roll(close, 1)
    open_[0] = start_price
    high = np.maximum(open_, close) + wiggle
    low = np.minimum(open_, close) - wiggle
    volume = rng.integers(80, 400, size=n) * us_boost.astype(int).clip(1)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )
    df.index.name = "datetime"
    return df


def load_or_create_data(data_dir: Path | None = None) -> pd.DataFrame:
    """اگر CSV موجود باشد بارگذاری می‌کند؛ وگرنه داده مصنوعی می‌سازد."""
    data_dir = data_dir or Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "xauusd_m1.csv"

    if csv_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["datetime"])
        df = df.set_index("datetime").sort_index()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns.str.lower())
        if missing:
            raise ValueError(f"ستون‌های ناقص در CSV: {missing}")
        df.columns = [c.lower() for c in df.columns]
        return df

    df = generate_synthetic_xauusd()
    out = df.reset_index()
    out.to_csv(csv_path, index=False)
    return df


def filter_us_session(df: pd.DataFrame) -> pd.DataFrame:
    """فقط کندل‌های سشن آمریکا."""
    hours = df.index.hour
    mask = (hours >= US_SESSION_START_UTC) & (hours < US_SESSION_END_UTC)
    return df.loc[mask].copy()

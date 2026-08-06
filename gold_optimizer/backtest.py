"""موتور بک‌تست سشن آمریکا برای XAUUSD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from config import (
    COMMISSION_PER_LOT,
    CONTRACT_SIZE,
    INITIAL_CAPITAL,
    LEVERAGE,
    LOT_SIZE,
    MAX_OPEN_TRADES,
    MAX_RISK_PER_TRADE_PCT,
    SL_ATR_MULT,
    SPREAD_USD,
    TP_ATR_MULT,
    US_FORCE_CLOSE_MINUTE,
    US_SESSION_END_UTC,
    US_SESSION_START_UTC,
)


@dataclass
class Trade:
    direction: int  # 1 buy, -1 sell
    entry_time: pd.Timestamp
    entry_price: float
    sl: float
    tp: float
    lot: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    pnl: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    strategy_name: str
    params: dict[str, Any]
    final_equity: float
    total_pnl: float
    max_drawdown: float
    win_rate: float
    trades: int
    winning_trades: int
    losing_trades: int
    daily_pnl: dict[str, float] = field(default_factory=dict)
    equity_curve: list[float] = field(default_factory=list)


def _position_margin(price: float, lot: float) -> float:
    notional = lot * CONTRACT_SIZE * price
    return notional / LEVERAGE


def _spread_cost(lot: float) -> float:
    return SPREAD_USD * lot * CONTRACT_SIZE


def _commission(lot: float) -> float:
    return COMMISSION_PER_LOT * lot


def _pnl_usd(direction: int, entry: float, exit_price: float, lot: float) -> float:
    return direction * (exit_price - entry) * lot * CONTRACT_SIZE


def _is_us_session(ts: pd.Timestamp) -> bool:
    return US_SESSION_START_UTC <= ts.hour < US_SESSION_END_UTC


def _should_force_close(ts: pd.Timestamp) -> bool:
    """در انتهای سشن آمریکا همه معاملات باید بسته شوند."""
    if ts.hour > US_SESSION_END_UTC - 1:
        return True
    if ts.hour == US_SESSION_END_UTC - 1 and ts.minute >= US_FORCE_CLOSE_MINUTE:
        return True
    return False


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    strategy_name: str,
    params: dict[str, Any],
    initial_capital: float = INITIAL_CAPITAL,
    lot_size: float = LOT_SIZE,
    sl_atr_mult: float | None = None,
    tp_atr_mult: float | None = None,
) -> BacktestResult:
    sl_mult = sl_atr_mult if sl_atr_mult is not None else params.get("sl_atr", SL_ATR_MULT)
    tp_mult = tp_atr_mult if tp_atr_mult is not None else params.get("tp_atr", TP_ATR_MULT)

    cash = initial_capital
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    open_trades: list[Trade] = []
    closed: list[Trade] = []
    equity_curve: list[float] = []
    daily_pnl: dict[str, float] = {}
    day_start_equity = initial_capital
    current_day: str | None = None

    # سیگنال را با داده هم‌تراز کن
    sig = signal.reindex(df.index).fillna(0).astype(int)

    for ts, row in df.iterrows():
        day_key = ts.strftime("%Y-%m-%d")
        if current_day is None:
            current_day = day_key
            day_start_equity = equity
        elif day_key != current_day:
            daily_pnl[current_day] = equity - day_start_equity
            current_day = day_key
            day_start_equity = equity

        in_session = _is_us_session(ts)
        force_close = _should_force_close(ts)

        # مدیریت پوزیشن‌های باز
        still_open: list[Trade] = []
        for tr in open_trades:
            hit_sl = False
            hit_tp = False
            exit_px = None
            reason = ""

            if tr.direction == 1:
                if row["low"] <= tr.sl:
                    hit_sl = True
                    exit_px = tr.sl
                    reason = "sl"
                elif row["high"] >= tr.tp:
                    hit_tp = True
                    exit_px = tr.tp
                    reason = "tp"
            else:
                if row["high"] >= tr.sl:
                    hit_sl = True
                    exit_px = tr.sl
                    reason = "sl"
                elif row["low"] <= tr.tp:
                    hit_tp = True
                    exit_px = tr.tp
                    reason = "tp"

            if force_close and not (hit_sl or hit_tp):
                exit_px = float(row["close"])
                reason = "session_end"
                hit_sl = hit_tp = False

            if hit_sl or hit_tp or (force_close and exit_px is not None):
                assert exit_px is not None
                pnl = _pnl_usd(tr.direction, tr.entry_price, exit_px, tr.lot)
                pnl -= _spread_cost(tr.lot) + _commission(tr.lot)
                tr.exit_time = ts
                tr.exit_price = exit_px
                tr.pnl = pnl
                tr.reason = reason
                cash += pnl
                closed.append(tr)
            else:
                still_open.append(tr)
        open_trades = still_open

        # ورود فقط داخل سشن و قبل از force close
        if (
            in_session
            and not force_close
            and len(open_trades) < MAX_OPEN_TRADES
            and not np.isnan(row.get("atr", np.nan))
            and row["atr"] > 0
        ):
            direction = int(sig.loc[ts])
            if direction != 0:
                atr_v = float(row["atr"])
                entry = float(row["close"]) + direction * (SPREAD_USD / 2.0)
                sl = entry - direction * sl_mult * atr_v
                tp = entry + direction * tp_mult * atr_v

                # اندازه لات بر اساس ریسک
                risk_cash = equity * (MAX_RISK_PER_TRADE_PCT / 100.0)
                stop_dist = abs(entry - sl)
                if stop_dist > 0:
                    risk_lot = risk_cash / (stop_dist * CONTRACT_SIZE)
                    lot = min(lot_size, max(0.01, round(risk_lot, 2)))
                else:
                    lot = lot_size

                margin = _position_margin(entry, lot)
                if margin <= cash * 0.9 and equity > 50:
                    open_trades.append(
                        Trade(
                            direction=direction,
                            entry_time=ts,
                            entry_price=entry,
                            sl=sl,
                            tp=tp,
                            lot=lot,
                        )
                    )

        # ارزش شناور
        floating = 0.0
        for tr in open_trades:
            floating += _pnl_usd(tr.direction, tr.entry_price, float(row["close"]), tr.lot)
        equity = cash + floating
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

        # اگر سرمایه تقریباً صفر شد متوقف شو
        if equity < 20:
            break

    # بستن باقیمانده در صورت وجود
    if open_trades and len(df) > 0:
        last_ts = df.index[-1]
        last_px = float(df.iloc[-1]["close"])
        for tr in open_trades:
            pnl = _pnl_usd(tr.direction, tr.entry_price, last_px, tr.lot)
            pnl -= _spread_cost(tr.lot) + _commission(tr.lot)
            tr.exit_time = last_ts
            tr.exit_price = last_px
            tr.pnl = pnl
            tr.reason = "eod_force"
            cash += pnl
            closed.append(tr)
        open_trades = []
        equity = cash

    if current_day is not None:
        daily_pnl[current_day] = equity - day_start_equity

    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl <= 0]
    total_pnl = equity - initial_capital
    win_rate = (len(wins) / len(closed) * 100.0) if closed else 0.0

    return BacktestResult(
        strategy_name=strategy_name,
        params=params,
        final_equity=round(equity, 2),
        total_pnl=round(total_pnl, 2),
        max_drawdown=round(max_dd * 100.0, 2),
        win_rate=round(win_rate, 2),
        trades=len(closed),
        winning_trades=len(wins),
        losing_trades=len(losses),
        daily_pnl={k: round(v, 2) for k, v in daily_pnl.items()},
        equity_curve=equity_curve,
    )

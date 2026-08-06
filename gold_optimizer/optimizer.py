"""لوپ بهینه‌سازی: تست ترکیب اندیکاتورها و پارامترهای مختلف."""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from backtest import BacktestResult, run_backtest
from config import OPTIMIZER_MAX_COMBOS, TOP_N_REPORT
from indicators import compute_indicator_bundle
from strategies import STRATEGIES, apply_signal_persistence


def param_grid() -> dict[str, list[Any]]:
    """شبکه پارامترهای اندیکاتورها و مدیریت ریسک."""
    return {
        "ema_fast": [5, 8, 12],
        "ema_slow": [21, 34, 55],
        "rsi_len": [7, 14],
        "rsi_buy": [45, 50],
        "rsi_sell": [50, 55],
        "rsi_ob": [70, 75],
        "rsi_os": [25, 30],
        "rsi_os_level": [25, 30],
        "rsi_ob_level": [70, 75],
        "rsi_mid_low": [40, 45],
        "rsi_mid_high": [60, 65],
        "macd_fast": [8, 12],
        "macd_slow": [21, 26],
        "macd_signal": [5, 9],
        "bb_len": [14, 20],
        "bb_std": [1.5, 2.0],
        "stoch_k": [7, 14],
        "stoch_d": [3],
        "stoch_ob": [75, 80],
        "stoch_os": [20, 25],
        "atr_len": [10, 14],
        "adx_len": [14],
        "adx_min": [18, 25],
        "sl_atr": [1.2, 1.5, 2.0],
        "tp_atr": [2.0, 2.5, 3.0],
        "hold_bars": [3, 5],
    }


def _smart_param_combos(max_combos: int = OPTIMIZER_MAX_COMBOS) -> Iterator[dict[str, Any]]:
    """
    به‌جای ضرب کامل (که خیلی بزرگ است)، یک جستجوی لایه‌ای می‌سازد:
    هسته روند + هسته اسیلاتور + ریسک را جداگانه می‌چرخاند.
    """
    grid = param_grid()

    cores = list(
        itertools.product(
            grid["ema_fast"],
            grid["ema_slow"],
            grid["rsi_len"],
            grid["macd_fast"],
            grid["macd_slow"],
            grid["macd_signal"],
            grid["bb_len"],
            grid["bb_std"],
            grid["stoch_k"],
            grid["atr_len"],
            grid["adx_min"],
        )
    )
    risk_sets = list(itertools.product(grid["sl_atr"], grid["tp_atr"], grid["hold_bars"]))
    oscillators = list(
        itertools.product(
            grid["rsi_buy"],
            grid["rsi_sell"],
            grid["rsi_ob"],
            grid["rsi_os"],
            grid["rsi_os_level"],
            grid["rsi_ob_level"],
            grid["stoch_ob"],
            grid["stoch_os"],
            grid["rsi_mid_low"],
            grid["rsi_mid_high"],
        )
    )

    # نمونه‌برداری یکنواخت از فضا
    step_core = max(1, len(cores) // max(1, max_combos // 4))
    step_risk = max(1, len(risk_sets) // 3)
    step_osc = max(1, len(oscillators) // 4)

    count = 0
    for i, core in enumerate(cores[::step_core]):
        for risk in risk_sets[::step_risk]:
            for osc in oscillators[::step_osc]:
                (
                    ema_fast,
                    ema_slow,
                    rsi_len,
                    macd_fast,
                    macd_slow,
                    macd_signal,
                    bb_len,
                    bb_std,
                    stoch_k,
                    atr_len,
                    adx_min,
                ) = core
                if ema_fast >= ema_slow or macd_fast >= macd_slow:
                    continue
                sl_atr, tp_atr, hold_bars = risk
                if tp_atr <= sl_atr:
                    continue
                (
                    rsi_buy,
                    rsi_sell,
                    rsi_ob,
                    rsi_os,
                    rsi_os_level,
                    rsi_ob_level,
                    stoch_ob,
                    stoch_os,
                    rsi_mid_low,
                    rsi_mid_high,
                ) = osc

                yield {
                    "ema_fast": ema_fast,
                    "ema_slow": ema_slow,
                    "rsi_len": rsi_len,
                    "rsi_buy": rsi_buy,
                    "rsi_sell": rsi_sell,
                    "rsi_ob": rsi_ob,
                    "rsi_os": rsi_os,
                    "rsi_os_level": rsi_os_level,
                    "rsi_ob_level": rsi_ob_level,
                    "rsi_mid_low": rsi_mid_low,
                    "rsi_mid_high": rsi_mid_high,
                    "macd_fast": macd_fast,
                    "macd_slow": macd_slow,
                    "macd_signal": macd_signal,
                    "bb_len": bb_len,
                    "bb_std": bb_std,
                    "stoch_k": stoch_k,
                    "stoch_d": 3,
                    "stoch_ob": stoch_ob,
                    "stoch_os": stoch_os,
                    "atr_len": atr_len,
                    "adx_len": 14,
                    "adx_min": adx_min,
                    "sl_atr": sl_atr,
                    "tp_atr": tp_atr,
                    "hold_bars": hold_bars,
                }
                count += 1
                if count >= max_combos:
                    return


def optimize(
    df: pd.DataFrame,
    max_combos: int = OPTIMIZER_MAX_COMBOS,
) -> list[BacktestResult]:
    """اجرای لوپ کامل روی استراتژی‌ها × پارامترها."""
    results: list[BacktestResult] = []
    combos = list(_smart_param_combos(max_combos=max_combos))
    total = len(combos) * len(STRATEGIES)
    done = 0

    print(f"شروع بهینه‌سازی: {len(combos)} ست پارامتر × {len(STRATEGIES)} استراتژی = {total} تست")

    # کش اندیکاتور برای پارامترهای یکسان هسته
    indicator_cache: dict[tuple, pd.DataFrame] = {}

    for params in combos:
        cache_key = (
            params["ema_fast"],
            params["ema_slow"],
            params["rsi_len"],
            params["macd_fast"],
            params["macd_slow"],
            params["macd_signal"],
            params["bb_len"],
            params["bb_std"],
            params["stoch_k"],
            params["stoch_d"],
            params["atr_len"],
            params["adx_len"],
        )
        if cache_key not in indicator_cache:
            indicator_cache[cache_key] = compute_indicator_bundle(df, params)
        enriched = indicator_cache[cache_key]

        for strat in STRATEGIES:
            raw_sig = strat.signal_fn(enriched, params)
            sig = apply_signal_persistence(raw_sig, params["hold_bars"])
            # فقط سشن آمریکا را معامله کن (بک‌تست خودش هم چک می‌کند)
            result = run_backtest(enriched, sig, strat.name, params)
            results.append(result)
            done += 1
            if done % 25 == 0 or done == total:
                best = max(results, key=lambda r: r.total_pnl)
                print(
                    f"[{done}/{total}] بهترین تا الان: {best.strategy_name} "
                    f"سود={best.total_pnl}$ سرمایه={best.final_equity}$"
                )

    results.sort(key=lambda r: r.total_pnl, reverse=True)
    return results


def results_to_frame(results: list[BacktestResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append(
            {
                "strategy": r.strategy_name,
                "total_pnl": r.total_pnl,
                "final_equity": r.final_equity,
                "max_drawdown_pct": r.max_drawdown,
                "win_rate_pct": r.win_rate,
                "trades": r.trades,
                "wins": r.winning_trades,
                "losses": r.losing_trades,
                "params_json": json.dumps(r.params, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def save_results(
    results: list[BacktestResult],
    out_dir: Path,
    top_n: int = TOP_N_REPORT,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = results_to_frame(results)
    csv_path = out_dir / "all_results.csv"
    frame.to_csv(csv_path, index=False)

    best = results[0]
    summary = {
        "best_strategy": best.strategy_name,
        "best_pnl": best.total_pnl,
        "best_final_equity": best.final_equity,
        "best_max_drawdown_pct": best.max_drawdown,
        "best_win_rate_pct": best.win_rate,
        "best_trades": best.trades,
        "best_params": best.params,
        "best_daily_pnl": best.daily_pnl,
        "top_n": [
            {
                "rank": i + 1,
                "strategy": r.strategy_name,
                "total_pnl": r.total_pnl,
                "final_equity": r.final_equity,
                "max_drawdown_pct": r.max_drawdown,
                "win_rate_pct": r.win_rate,
                "trades": r.trades,
                "params": r.params,
            }
            for i, r in enumerate(results[:top_n])
        ],
    }
    summary_path = out_dir / "best_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path

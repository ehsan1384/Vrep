#!/usr/bin/env python3
"""
بهینه‌ساز استراتژی طلا (XAUUSD) — سشن آمریکا — تایم‌فریم M1

سرمایه اولیه: ۵۰۰ دلار | اهرم: ۱:۲۰۰
هر روز در پایان سشن آمریکا همه معاملات بسته می‌شوند،
سود/ضرر روزانه ثبت می‌شود، و لوپ با پارامترهای مختلف تکرار می‌گردد.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import (
    DATA_DAYS,
    INITIAL_CAPITAL,
    LEVERAGE,
    LOT_SIZE,
    OPTIMIZER_MAX_COMBOS,
    TIMEFRAME,
    TOP_N_REPORT,
    US_SESSION_END_UTC,
    US_SESSION_START_UTC,
)
from data_loader import load_or_create_data
from optimizer import optimize, save_results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gold US-session M1 strategy optimizer")
    p.add_argument(
        "--max-combos",
        type=int,
        default=OPTIMIZER_MAX_COMBOS,
        help="حداکثر تعداد ست پارامتر برای جستجو",
    )
    p.add_argument(
        "--top",
        type=int,
        default=TOP_N_REPORT,
        help="تعداد بهترین نتایج برای گزارش",
    )
    return p.parse_args()


def print_report(summary: dict) -> None:
    print("\n" + "=" * 72)
    print("نتیجه نهایی بهینه‌سازی استراتژی طلا (XAUUSD)")
    print("=" * 72)
    print(f"سرمایه اولیه     : {INITIAL_CAPITAL} USD")
    print(f"اهرم             : 1:{LEVERAGE}")
    print(f"تایم‌فریم         : {TIMEFRAME}")
    print(f"سشن آمریکا (UTC) : {US_SESSION_START_UTC}:00 تا {US_SESSION_END_UTC}:00")
    print(f"حجم پایه         : {LOT_SIZE} lot")
    print(f"روزهای داده      : ~{DATA_DAYS}")
    print("-" * 72)
    print(f"بهترین استراتژی  : {summary['best_strategy']}")
    print(f"سود کل           : {summary['best_pnl']} USD")
    print(f"سرمایه نهایی     : {summary['best_final_equity']} USD")
    print(f"حداکثر افت سرمایه: {summary['best_max_drawdown_pct']}%")
    print(f"نرخ برد          : {summary['best_win_rate_pct']}%")
    print(f"تعداد معاملات    : {summary['best_trades']}")
    print("-" * 72)
    print("پارامترهای برنده:")
    print(json.dumps(summary["best_params"], ensure_ascii=False, indent=2))
    print("-" * 72)
    print("سود/ضرر روزانه بهترین استراتژی:")
    for day, pnl in summary["best_daily_pnl"].items():
        sign = "+" if pnl >= 0 else ""
        print(f"  {day}: {sign}{pnl} USD")
    print("-" * 72)
    print(f"Top {len(summary['top_n'])}:")
    for item in summary["top_n"]:
        print(
            f"  #{item['rank']:02d}  {item['strategy']:<16}  "
            f"PnL={item['total_pnl']:>8}  Equity={item['final_equity']:>8}  "
            f"DD={item['max_drawdown_pct']:>5}%  WR={item['win_rate_pct']:>5}%  "
            f"Trades={item['trades']}"
        )
    print("=" * 72)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    results_dir = root / "results"

    print("بارگذاری / ساخت داده M1 طلا...")
    df = load_or_create_data(root / "data")
    print(f"تعداد کندل: {len(df)} | از {df.index[0]} تا {df.index[-1]}")

    results = optimize(df, max_combos=args.max_combos)
    if not results:
        print("هیچ نتیجه‌ای تولید نشد.", file=sys.stderr)
        return 1

    summary_path = save_results(results, results_dir, top_n=args.top)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print_report(summary)
    print(f"\nفایل خلاصه: {summary_path}")
    print(f"همه نتایج: {results_dir / 'all_results.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

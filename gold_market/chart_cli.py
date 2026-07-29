"""
نسخه خط فرمان: ذخیره نمودار ۱ دقیقه‌ای طلا + عمق خرید/فروش به صورت HTML.

اجرا:
    python chart_cli.py
خروجی:
    gold_1m_chart.html
    gold_depth.html
"""

from __future__ import annotations

from pathlib import Path

from app import (
    SYMBOL_LABEL,
    build_volume_at_price,
    fetch_gold_1m,
    make_candle_figure,
    make_depth_figure,
    style_depth_table,
)


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)

    print("Fetching COMEX Gold (GC=F) 1-minute data...")
    df = fetch_gold_1m(period="5d")
    last = float(df["close"].iloc[-1])
    depth = build_volume_at_price(df, bins=40)

    candle_path = out_dir / "gold_1m_chart.html"
    depth_path = out_dir / "gold_depth.html"
    table_path = out_dir / "gold_depth_table.csv"

    make_candle_figure(df.tail(400), f"{SYMBOL_LABEL} — 1m").write_html(candle_path)
    make_depth_figure(depth, last).write_html(depth_path)
    style_depth_table(depth, last).to_csv(table_path, index=False)

    print(f"Last price: {last:.2f}")
    print(f"Candles: {len(df)}")
    print(f"Wrote: {candle_path}")
    print(f"Wrote: {depth_path}")
    print(f"Wrote: {table_path}")


if __name__ == "__main__":
    main()

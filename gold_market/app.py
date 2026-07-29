"""
طلای بازار اصلی (COMEX Gold Futures) — نمودار ۱ دقیقه‌ای + عمق خرید/فروش

منبع قیمت: قرارداد آتی طلای COMEX با نماد GC=F (نزدیک‌ترین بازار شفاف و متمرکز طلا)
عمق بازار: پروفایل حجم در هر سطح قیمت از کندل‌های ۱ دقیقه‌ای
           (حجم خرید تقریبی از کندل صعودی، حجم فروش تقریبی از کندل نزولی)

اجرا:
    cd gold_market
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

# قرارداد آتی طلای COMEX — بازار اصلی شفاف (نه بروکر فارکس)
SYMBOL = "GC=F"
SYMBOL_LABEL = "COMEX Gold (GC=F)"
INTERVAL = "1m"
LOOKBACK_PERIOD = "5d"  # yfinance برای ۱ دقیقه حداکثر حدود ۷ روز می‌دهد
DEPTH_BINS = 40  # تعداد سطوح قیمت در عمق بازار
REFRESH_SECONDS = 60


def fetch_gold_1m(symbol: str = SYMBOL, period: str = LOOKBACK_PERIOD) -> pd.DataFrame:
    """دانلود کندل ۱ دقیقه‌ای طلای COMEX."""
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=INTERVAL, auto_adjust=True)
    if df.empty:
        raise RuntimeError(
            f"داده‌ای برای {symbol} دریافت نشد. اتصال اینترنت یا محدودیت Yahoo را بررسی کنید."
        )
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df


def fetch_quote_snapshot(symbol: str = SYMBOL) -> dict[str, Any]:
    """آخرین قیمت، بید و اسک از یاهو (خلاصه بازار، نه عمق کامل بورس)."""
    info: dict[str, Any] = {}
    ticker = yf.Ticker(symbol)
    try:
        fast = ticker.fast_info
        info["last"] = getattr(fast, "last_price", None) or getattr(fast, "previous_close", None)
        info["bid"] = getattr(fast, "bid", None)
        info["ask"] = getattr(fast, "ask", None)
        info["bid_size"] = getattr(fast, "bid_size", None)
        info["ask_size"] = getattr(fast, "ask_size", None)
    except Exception:
        pass
    try:
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            info["last"] = float(hist["Close"].iloc[-1])
            info["day_high"] = float(hist["High"].max())
            info["day_low"] = float(hist["Low"].min())
    except Exception:
        pass
    return info


def build_volume_at_price(df: pd.DataFrame, bins: int = DEPTH_BINS) -> pd.DataFrame:
    """
    عمق تقریبی بازار از روی حجم معاملات در هر سطح قیمت.

    - کندل صعودی (close >= open) → حجم به سمت خریداران
    - کندل نزولی (close < open) → حجم به سمت فروشندگان

    توجه: این Level 2 زنده بورس نیست؛ پروفایل حجم واقعی معاملات COMEX
    در تایم‌فریم ۱ دقیقه است و نزدیک‌ترین تقریب رایگان به «چقدر خرید/فروش در هر قیمت».
    """
    if df.empty:
        return pd.DataFrame(columns=["price", "buy_volume", "sell_volume", "total_volume"])

    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    if price_min >= price_max:
        price_max = price_min + 0.1

    edges = np.linspace(price_min, price_max, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0

    buy = np.zeros(bins, dtype=float)
    sell = np.zeros(bins, dtype=float)

    for _, row in df.iterrows():
        vol = float(row["volume"])
        if vol <= 0 or np.isnan(vol):
            continue
        # توزیع حجم روی بازه high-low کندل
        lo, hi = float(row["low"]), float(row["high"])
        if hi <= lo:
            hi = lo + 1e-6
        # وزن هر بین که با بازه کندل هم‌پوشانی دارد
        overlap = np.minimum(edges[1:], hi) - np.maximum(edges[:-1], lo)
        overlap = np.clip(overlap, 0, None)
        total_overlap = overlap.sum()
        if total_overlap <= 0:
            # کل حجم روی نزدیک‌ترین قیمت
            idx = int(np.clip(np.searchsorted(edges, (lo + hi) / 2.0) - 1, 0, bins - 1))
            weights = np.zeros(bins)
            weights[idx] = 1.0
        else:
            weights = overlap / total_overlap

        if float(row["close"]) >= float(row["open"]):
            buy += weights * vol
        else:
            sell += weights * vol

    out = pd.DataFrame(
        {
            "price": centers,
            "buy_volume": buy,
            "sell_volume": sell,
            "total_volume": buy + sell,
        }
    )
    return out


def make_candle_figure(df: pd.DataFrame, title: str) -> go.Figure:
    """نمودار شمعی ۱ دقیقه‌ای."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="GC",
            increasing_line_color="#0ecb81",
            decreasing_line_color="#f6465d",
            increasing_fillcolor="#0ecb81",
            decreasing_fillcolor="#f6465d",
        ),
        row=1,
        col=1,
    )
    colors = np.where(df["close"] >= df["open"], "#0ecb81", "#f6465d")
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], marker_color=colors, name="Volume", opacity=0.55),
        row=2,
        col=1,
    )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        paper_bgcolor="#0b0e11",
        plot_bgcolor="#0b0e11",
        font=dict(color="#eaecef"),
    )
    fig.update_xaxes(gridcolor="#1e2329", row=1, col=1)
    fig.update_yaxes(title_text="Price (USD/oz)", gridcolor="#1e2329", row=1, col=1)
    fig.update_yaxes(title_text="Volume", gridcolor="#1e2329", row=2, col=1)
    return fig


def make_depth_figure(depth: pd.DataFrame, last_price: float | None) -> go.Figure:
    """نمودار عمق: سمت چپ خریداران، سمت راست فروشندگان."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=depth["price"],
            x=-depth["buy_volume"],
            orientation="h",
            name="خریدار (Buy Volume)",
            marker_color="#0ecb81",
            hovertemplate="قیمت: %{y:.2f}<br>حجم خرید: %{customdata:.0f}<extra></extra>",
            customdata=depth["buy_volume"],
        )
    )
    fig.add_trace(
        go.Bar(
            y=depth["price"],
            x=depth["sell_volume"],
            orientation="h",
            name="فروشنده (Sell Volume)",
            marker_color="#f6465d",
            hovertemplate="قیمت: %{y:.2f}<br>حجم فروش: %{x:.0f}<extra></extra>",
        )
    )
    if last_price is not None and not np.isnan(last_price):
        fig.add_hline(
            y=last_price,
            line_dash="dot",
            line_color="#f0b90b",
            annotation_text=f"Last {last_price:.2f}",
            annotation_position="top left",
        )
    fig.update_layout(
        title="عمق بازار — حجم خرید/فروش در هر سطح قیمت (Volume-at-Price)",
        template="plotly_dark",
        barmode="overlay",
        height=560,
        margin=dict(l=40, r=20, t=50, b=30),
        paper_bgcolor="#0b0e11",
        plot_bgcolor="#0b0e11",
        font=dict(color="#eaecef"),
        xaxis_title="حجم ← خرید | فروش →",
        yaxis_title="قیمت (USD/oz)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        bargap=0.05,
    )
    fig.update_xaxes(gridcolor="#1e2329", zeroline=True, zerolinecolor="#848e9c")
    fig.update_yaxes(gridcolor="#1e2329")
    return fig


def style_depth_table(depth: pd.DataFrame, last_price: float | None) -> pd.DataFrame:
    """جدول سطوح قیمت برای نمایش."""
    table = depth.copy()
    table["price"] = table["price"].round(2)
    table["buy_volume"] = table["buy_volume"].round(0).astype(int)
    table["sell_volume"] = table["sell_volume"].round(0).astype(int)
    table["total_volume"] = table["total_volume"].round(0).astype(int)
    table["side"] = "around"
    if last_price is not None:
        table["side"] = np.where(table["price"] >= last_price, "ask / فروش", "bid / خرید")
    table = table.sort_values("price", ascending=False)
    table = table.rename(
        columns={
            "price": "قیمت",
            "buy_volume": "حجم خریداران",
            "sell_volume": "حجم فروشندگان",
            "total_volume": "جمع حجم",
            "side": "سمت",
        }
    )
    return table.reset_index(drop=True)


def main() -> None:
    st.set_page_config(
        page_title="COMEX Gold — 1m + Depth",
        page_icon="🟡",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(ellipse at top, #141820 0%, #0b0e11 55%); }
        div[data-testid="stMetricValue"] { font-size: 1.4rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("طلای بازار اصلی — COMEX")
    st.caption(
        "نمودار ۱ دقیقه‌ای قرارداد آتی طلای COMEX (`GC=F`) + حجم خرید/فروش در هر سطح قیمت. "
        "این داده از بازار شفاف بورس می‌آید، نه از دفتر سفارش بروکر فارکس."
    )

    with st.sidebar:
        st.header("تنظیمات")
        period = st.selectbox("بازه داده", ["1d", "2d", "5d"], index=2)
        bins = st.slider("تعداد سطوح عمق", min_value=20, max_value=80, value=DEPTH_BINS, step=5)
        auto_refresh = st.checkbox("بروزرسانی خودکار هر ۶۰ ثانیه", value=True)
        st.info(
            "فارکس طلا (`XAUUSD`) دفتر سفارش متمرکز عمومی ندارد. "
            "اینجا از بازار اصلی شفاف طلا یعنی `COMEX Gold Futures` استفاده شده است."
        )
        if auto_refresh:
            st.markdown(
                f"""
                <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
                """,
                unsafe_allow_html=True,
            )

    try:
        with st.spinner("در حال دریافت داده از بازار COMEX..."):
            df = fetch_gold_1m(period=period)
            quote = fetch_quote_snapshot()
            depth = build_volume_at_price(df, bins=bins)
    except Exception as exc:
        st.error(f"خطا در دریافت داده: {exc}")
        st.stop()

    last_price = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else last_price
    change = last_price - prev_close
    change_pct = (change / prev_close * 100.0) if prev_close else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("آخرین قیمت", f"{last_price:,.2f}", f"{change:+.2f} ({change_pct:+.3f}%)")
    c2.metric("بید", f"{quote.get('bid') or '—'}")
    c3.metric("اسک", f"{quote.get('ask') or '—'}")
    c4.metric("بالاترین روز", f"{quote.get('day_high') or df['high'].max():,.2f}")
    c5.metric("پایین‌ترین روز", f"{quote.get('day_low') or df['low'].min():,.2f}")

    left, right = st.columns([1.35, 1.0])
    with left:
        st.plotly_chart(
            make_candle_figure(df.tail(400), f"{SYMBOL_LABEL} — تایم‌فریم ۱ دقیقه"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(make_depth_figure(depth, last_price), use_container_width=True)

    st.subheader("جدول عمق — چه حجمی در چه قیمتی؟")
    st.caption(
        "حجم خریداران ≈ حجم کندل‌های صعودی در آن سطح قیمت · "
        "حجم فروشندگان ≈ حجم کندل‌های نزولی در آن سطح قیمت"
    )
    table = style_depth_table(depth, last_price)
    st.dataframe(table, use_container_width=True, height=420)

    top_buy = depth.loc[depth["buy_volume"].idxmax()]
    top_sell = depth.loc[depth["sell_volume"].idxmax()]
    st.success(
        f"بیشترین تجمع خریداران حول قیمت **{top_buy['price']:.2f}** "
        f"(حجم {top_buy['buy_volume']:.0f}) — "
        f"بیشترین تجمع فروشندگان حول قیمت **{top_sell['price']:.2f}** "
        f"(حجم {top_sell['sell_volume']:.0f})"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.caption(
        f"آخرین بروزرسانی: {now} | نماد: {SYMBOL} | کندل‌ها: {len(df)} | "
        "منبع قیمت: Yahoo Finance ← COMEX | "
        "عمق کامل Level 2 زنده CME نیاز به دیتافید پولی (مثل Databento / Bloomberg) دارد؛ "
        "این نسخه پروفایل حجم واقعی معاملات ۱ دقیقه‌ای را نشان می‌دهد."
    )


if __name__ == "__main__":
    main()

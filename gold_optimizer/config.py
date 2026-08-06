"""تنظیمات پایه بک‌تست طلا (XAUUSD)."""

from __future__ import annotations

# سرمایه و اهرم
INITIAL_CAPITAL = 500.0
LEVERAGE = 200

# نماد و حجم
SYMBOL = "XAUUSD"
LOT_SIZE = 0.01  # میکرو لات — مناسب سرمایه ۵۰۰ دلار
CONTRACT_SIZE = 100  # اونس در هر لات استاندارد
PIP_SIZE = 0.01  # برای طلا معمولاً ۰.۰۱ دلار
SPREAD_USD = 0.25  # اسپرد تقریبی به دلار در هر اونس
COMMISSION_PER_LOT = 0.0

# تایم‌فریم و سشن آمریکا (نیویورک) — ساعت UTC
TIMEFRAME = "M1"
US_SESSION_START_UTC = 13  # 08:00 EST / 09:00 EDT تقریبی
US_SESSION_END_UTC = 21  # قبل از پایان سشن همه پوزیشن‌ها بسته می‌شوند
US_FORCE_CLOSE_MINUTE = 55  # در ساعت پایان، دقیقه ۵۵

# مدیریت ریسک
MAX_RISK_PER_TRADE_PCT = 2.0  # حداکثر ۲٪ سرمایه در هر معامله
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.5
MAX_OPEN_TRADES = 1

# داده شبیه‌سازی / بک‌تست
DATA_DAYS = 30  # یک ماه گذشته
BARS_PER_DAY = 24 * 60
RANDOM_SEED = 42

# محدوده جستجوی پارامترها (برای سرعت و پوشش معقول)
OPTIMIZER_MAX_COMBOS = 120
TOP_N_REPORT = 10

# Gann Neural Step for XAUUSD

این پروژه یک نمونه قابل توسعه برای معامله XAUUSD با گن و بهینه‌سازی `step` با شبکه عصبی است.

ایده اصلی:

```text
GannStep = ATR(14) * NeuralMultiplier
```

مدل عصبی به جای پیش‌بینی مستقیم قیمت، یکی از multiplierهای مناسب برای ATR را انتخاب می‌کند. این طراحی برای طلا پایدارتر است، چون نوسان XAUUSD در سشن‌های مختلف تغییر زیادی دارد.

## ساختار پروژه

```text
gann/
  mql5/Experts/GannNeuralStepEA.mq5   Expert Advisor برای MetaTrader 5
  python/train_gann_step_model.py     آموزش GRU و خروجی ONNX
  python/requirements.txt             وابستگی‌های Python
  data/README.md                      راهنمای دیتای ورودی
  models/README.md                    محل خروجی مدل ONNX
```

## جریان کار پیشنهادی

1. در MetaTrader 5 دیتای XAUUSD را به CSV خروجی بگیرید.
2. مدل را با Python آموزش دهید:

```bash
cd gann
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
python3 python/train_gann_step_model.py \
  --csv data/XAUUSD_M15.csv \
  --onnx-out models/gann_step_gru.onnx \
  --epochs 25
```

3. فایل `models/gann_step_gru.onnx` را در مسیر `MQL5/Files` ترمینال MetaTrader 5 کپی کنید.
4. فایل `mql5/Experts/GannNeuralStepEA.mq5` را در `MQL5/Experts` کپی و Compile کنید.
5. اکسپرت را روی چارت XAUUSD اجرا کنید و در Strategy Tester تست بگیرید.

## ورودی مدل

مدل برای هر کندل 8 ویژگی دریافت می‌کند:

1. `(close - open) / ATR`
2. `(high - low) / ATR`
3. `(close - previous_close) / ATR`
4. مقدار RSI مقیاس‌شده
5. فاصله EMA سریع و کند نسبت به ATR
6. فاصله قیمت تا نزدیک‌ترین سطح گن نسبت به ATR
7. z-score حجم تیک
8. `ATR / close`

طول توالی پیش‌فرض 50 کندل است.

## خروجی مدل

خروجی مدل یک بردار احتمال برای multiplierهای زیر است:

```text
0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00
```

اکسپرت بیشترین احتمال را انتخاب می‌کند و step گن را می‌سازد.

## نکته مهم درباره ریسک

این پروژه نمونه آموزشی/تحقیقاتی است و سیگنال قطعی سودآور نیست. قبل از اجرای روی حساب واقعی:

- بک‌تست چندساله بگیرید.
- حتماً اسپرد و کمیسیون واقعی XAUUSD را لحاظ کنید.
- از walk-forward validation استفاده کنید.
- روی حساب دمو forward test انجام دهید.

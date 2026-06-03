# Data directory

فایل CSV خروجی گرفته‌شده از MetaTrader 5 را اینجا قرار دهید.

روش پیشنهادی:

1. فایل `mql5/Scripts/ExportRatesForGannNN.mq5` را در مسیر `MQL5/Scripts` کپی کنید.
2. در MetaTrader 5 آن را Compile و روی چارت اجرا کنید.
3. فایل خروجی مثل `XAUUSD_M15.csv` در مسیر `MQL5/Files` ساخته می‌شود.
4. فایل CSV را در این پوشه کپی کنید:

```text
gann/data/XAUUSD_M15.csv
```

حداقل چند هزار کندل پیشنهاد می‌شود. برای آموزش جدی، دیتای چند سال و تست walk-forward لازم است.

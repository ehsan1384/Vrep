# Models directory

خروجی آموزش مدل در این پوشه ساخته می‌شود:

```text
gann_step_gru.onnx
gann_step_gru.metadata.json
```

برای استفاده در Expert Advisor:

1. فایل `gann_step_gru.onnx` را به مسیر `MQL5/Files` ترمینال MetaTrader 5 کپی کنید.
2. در تنظیمات اکسپرت، مقدار `InpModelFile` را برابر نام فایل قرار دهید:

```text
gann_step_gru.onnx
```

فایل metadata فقط برای بررسی و مستندسازی آموزش است و توسط اکسپرت خوانده نمی‌شود.

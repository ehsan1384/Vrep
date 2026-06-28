# سنسور تشخیص ناهمواری پود بافندگی

این ماژول یک **سنسور تشخیص ناهمواری پود بافندگی** (`YarnIrregularitySensor`) برای پروژه `V-REP` اضافه می‌کند.

## قابلیت‌ها

- اندازه‌گیری قطر پود (میلی‌متر)
- تشخیص عیب‌های رایج نساجی:
  - `thin` — نازک
  - `thick` — ضخیم
  - `nep` — گره کوتاه
  - `break` — پارگی پود
- محاسبه ضریب تغییرات (`CV%`) برای ارزیابی یکنواختی پود

## ساختار فایل‌ها

| فایل | توضیح |
|------|--------|
| `Client/YarnIrregularityDetector.hpp/.cpp` | الگوریتم تشخیص عیب |
| `Client/YarnIrregularitySensor.hpp/.cpp` | اتصال به `V-REP` از طریق `float signal` |
| `scripts/yarn_irregularity_sensor.lua` | اسکریپت شبیه‌سازی سنسور نوری در `V-REP` |
| `YarnSensor/main.cpp` | برنامه نمونه خواندن سنسور |

## راه‌اندازی صحنه در V-REP

1. یک استوانه (`cylinder`) با نام `yarn` بسازید (نماینده پود).
2. یک `proximity sensor` از نوع `ray` با نام `yarnSensor_main` در مسیر پود قرار دهید.
3. اسکریپت `scripts/yarn_irregularity_sensor.lua` را به عنوان `child script` به سنسور وصل کنید.
4. برای شبیه‌سازی عیب، اندازه استوانه را در طول زمان تغییر دهید.

## کامپایل

```bash
cmake -S YarnSensor -B YarnSensor/build -DCMAKE_C_FLAGS=-m32 -DCMAKE_CXX_FLAGS=-m32
cmake --build YarnSensor/build -j$(nproc)
```

## اجرا

```bash
./YarnSensor/build/YarnSensor 127.0.0.1 19997
```

## سیگنال‌های V-REP

برای هر سنسور با نام `yarnSensor_main` این سیگنال‌ها منتشر می‌شوند:

- `yarnSensor_main_diameter` — قطر پود (mm)
- `yarnSensor_main_fault` — کد عیب (0=بدون عیب، 1=نازک، 2=ضخیم، 3=nep، 4=پارگی)
- `yarnSensor_main_cv` — ضریب تغییرات (%)

## تنظیم آستانه‌ها

در `YarnIrregularityDetector::Config`:

```cpp
config.nominalDiameterMm = 0.30;  // قطر اسمی پود
config.thinRatio = 0.75;          // آستانه نازکی
config.thickRatio = 1.35;         // آستانه ضخامت
config.nepRatio = 1.80;           // آستانه nep
config.breakRatio = 0.20;         // آستانه پارگی
```

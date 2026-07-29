#!/usr/bin/env bash
# اجرای داشبورد طلا — از پوشه gold_market
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501

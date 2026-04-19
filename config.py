"""
DinoDashboard — 全域設定常數

資料搬到 Supabase 之後，YAML / 本地 screenshots 資料夾都不再用。
只保留 BASE_DIR：app.py 用來寫本機 .flask_secret。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

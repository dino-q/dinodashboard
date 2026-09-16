"""一次性：把本機有 bat、但儀表板還沒有卡片的服務，加進「伺服器」分頁。

⚠️ 這支是**一次性**腳本，ITEMS 裡的名稱是寫死的。
   重跑不會再覆蓋既有設定（add_manual_entry 已改成「已存在就跳過」），
   但也因此**不要**把它當成「同步名稱」的工具——伺服器分頁的名稱
   正常情況應該跟著卡片走，只有「沒有對應卡片」的項目才需要寫死名稱。

這些之後若在卡片上補登同一個路徑，會自動合併成同一列（key 是路徑的雜湊），
現在先手動加不會白做。

用法：
    cd DinoDashboard
    .venv\\Scripts\\python.exe scripts\\seed_manual_servers.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from data.launcher import add_manual_entry, validate_bat_path  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

CC = r"C:\Users\AG_Di\Desktop\automation\Claude_code"

ITEMS = [
    (CC + r"\LINE\LINE_scheduled_sender\啟動.bat",     "LINE排程發送",         8881),
    (CC + r"\CLI\ChatGPT_MCP_Bridge\啟動.bat",         "ChatGPT MCP橋接",     8911),
    (CC + r"\sync\Notion_Tree\啟動.bat",               "Notion_Tree 檔案總管", 8884),
    (CC + r"\system\memory_check\啟動.bat",            "記憶體體檢",           8886),
    (CC + r"\YouTube\yt_comment\啟動.bat",             "YouTube KOL追蹤器",    8890),
    (CC + r"\tools\GS1_Barcode_Generator\啟動.bat",    "GS1條碼產生器",        8880),
    (CC + r"\side_project\DinoShareLink_Web\啟動.bat", "DinoShareLink網頁",   8900),
]


def main() -> int:
    ok = 0
    for path, label, port in ITEMS:
        exists = os.path.exists(path)
        norm, err = validate_bat_path(path)
        if err:
            print(f"  [跳過] {label:<20} 路徑不合格：{err}")
            continue
        key = add_manual_entry(norm, label, port)
        mark = "OK" if exists else "警告"
        print(f"  [{mark}] {label:<20} port={port:<6} key={key}  本機檔案存在={exists}")
        ok += 1
    print(f"\n完成 {ok}/{len(ITEMS)} 筆。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""把「伺服器」分頁的設定吐成 JSON，給本機的伺服器總管（Server_Launcher）讀。

為什麼是這種做法：
    合併邏輯（卡片的 bat 指令 ＋ launcher_entries 的開關 ＋ 手動新增）
    已經寫在 data/launcher.py 了。PowerShell 那邊如果再寫一份，兩份遲早會漂掉。
    所以總管直接呼叫這支腳本、拿 JSON，♻️ 沿用 get_manifest()／build_server_rows()。

    也不走 HTTP：Flask 本身就是被總管管理的服務之一，
    「要開伺服器得先有伺服器在跑」會變成雞生蛋。

輸出（UTF-8 JSON，只印這一段，錯誤走 stderr）：
    {
      "ok": true,
      "generated_at": "2026-09-15T16:00:00+08:00",
      "items": [{"key","label","bat","port","default_on","order"}],
      "archived_paths": [...],
      "hidden_paths": [...]
    }

用法：
    <DinoDashboard>\\.venv\\Scripts\\python.exe <DinoDashboard>\\scripts\\print_manifest.py
結束碼：0＝成功，1＝失敗（stderr 有原因）
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    try:
        from data.tools import load_tools
        from data.launcher import build_server_rows, get_manifest
    except Exception as exc:
        print(f"[print_manifest] 匯入失敗：{exc}", file=sys.stderr)
        return 1

    try:
        tools = load_tools()
        data = build_server_rows(tools)
        payload = {
            "ok": True,
            "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "items": get_manifest(tools),
            # 這兩份讓總管可以把「本機掃到、但在儀表板被封存或隱藏」的項目一起藏掉
            "archived_paths": [r["bat_path"] for r in data["archived"]],
            "hidden_paths": [r["bat_path"] for r in data["active"] if not r["visible"]],
        }
    except Exception as exc:
        print(f"[print_manifest] 取資料失敗：{exc}", file=sys.stderr)
        return 1

    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

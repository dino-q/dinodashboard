"""讓經銷商管理系統卡片沿用既有 8000 伺服器，修正測試網址。

預設唯讀預覽；加 --apply 才寫入 Supabase 的 tools.commands。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from data.supabase_client import get_client  # noqa: E402
from data.tools import get_tool  # noqa: E402

CARD_ID = "db9eb78329624c7fa7d30dd4b5bd2941"
OLD_TEST_BAT = (r"C:\Users\AG_Di\Desktop\automation\Claude_code\AGlife"
                r"\Distributor_MainData_Claudecode\啟動測試.bat")
TEST_URL = "http://localhost:8000/?env=staging"
TARGETS = [
    {"label": "測試：開啟網頁", "cmd": TEST_URL, "env": "local", "pinned": True},
]


def reconciled_commands(commands):
    """移除先前誤加的 8001 啟動鈕，更新測試網址；保留其餘指令。"""
    result = [dict(item) for item in commands
              if not (item.get("label") == "測試：啟動伺服器（8001）"
                      and item.get("cmd") == OLD_TEST_BAT)]
    for target in TARGETS:
        matches = [i for i, item in enumerate(result)
                   if item.get("label") == target["label"] or item.get("cmd") == target["cmd"]]
        if len(matches) > 1:
            raise RuntimeError(f"重複的測試入口，停止以免覆寫：{target['label']}")
        if matches:
            result[matches[0]] = dict(target)
        else:
            result.append(dict(target))
    return result


def main():
    tool = get_tool(CARD_ID)
    if not tool or tool.get("name_zh") != "經銷商管理系統(HTML)":
        raise RuntimeError("卡片 ID 或名稱不符，未修改任何資料")
    current = list(tool.get("commands") or [])
    updated = reconciled_commands(current)
    if updated == current:
        print("已正確設定；沒有資料需要修改。")
        return
    for target in TARGETS:
        print(f"{'確認' if '--apply' in sys.argv else '預覽'}：{target['label']} → {target['cmd']}")
    if "--apply" not in sys.argv:
        print("尚未寫入。加 --apply 才會更新 Dino 儀表板。")
        return
    get_client().table("tools").update({"commands": updated}).eq("id", CARD_ID).execute()
    saved = get_tool(CARD_ID)
    if list(saved.get("commands") or []) != updated:
        raise RuntimeError("寫入後讀回不一致，請人工檢查卡片")
    print("已寫入並讀回確認；原有指令未刪除。")


if __name__ == "__main__":
    main()

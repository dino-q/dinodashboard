"""在既有卡片上補一筆 bat 啟動指令（只動 commands 欄，其他欄位一律不碰）。

為什麼不用 add_tool_from_project.py --update：
    那支是「整張卡片覆寫」，要把既有欄位全部重寫一次才不會掉東西。
    這裡只是要補一顆按鈕，用整張覆寫風險反而高。

用法：
    .venv\\Scripts\\python.exe scripts\\add_bat_to_card.py            # 預覽
    .venv\\Scripts\\python.exe scripts\\add_bat_to_card.py --apply    # 真的寫
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from data.supabase_client import get_client  # noqa: E402
from data.tools import get_tool, _cache_clear_all  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

CC = r"C:\Users\AG_Di\Desktop\automation\Claude_code"

# (卡片 id, 按鈕標籤, bat 完整路徑, 要不要釘選)
TARGETS = [
    ("dinodashboard", "啟動 Bat",
     CC + r"\side_project\DinoDashboard\啟動.bat", True),
    ("dinodashboard", "安裝依賴 Bat",
     CC + r"\side_project\DinoDashboard\安裝.bat", False),
    ("db9eb78329624c7fa7d30dd4b5bd2941", "啟動 Bat",
     CC + r"\AGlife\Distributor_MainData_Claudecode\啟動.bat", True),
]


def main() -> int:
    apply = "--apply" in sys.argv
    sb = get_client()
    changed = 0

    for tool_id, label, bat, pinned in TARGETS:
        t = get_tool(tool_id)
        if not t:
            print(f"  [找不到卡片] id={tool_id}")
            continue
        cmds = list(t.get("commands") or [])
        if any((c.get("cmd") or "").strip().strip('"').lower() == bat.lower() for c in cmds):
            print(f"  [已存在] {t.get('name_zh')} → {label}")
            continue
        cmds.append({"label": label, "cmd": bat, "env": "bat", "pinned": pinned})
        print(f"  [{'寫入' if apply else '將寫入'}] {t.get('name_zh')} → [{label}] {bat}")
        if apply:
            sb.table("tools").update({"commands": cmds}).eq("id", tool_id).execute()
        changed += 1

    if apply:
        _cache_clear_all()
        print(f"\n完成，改了 {changed} 筆。")
    else:
        print(f"\n預覽：會改 {changed} 筆。加 --apply 才會真的寫入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

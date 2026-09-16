"""把一個專案的「專案連結七欄」寫成儀表板卡片。

給 slash command `/project-link-sync` 用。輸入是一份 JSON（描述一張卡片），
輸出是儀表板 tools 表的一筆資料。

♻️ 沿用 data/tools.py 的 add_tool() / update_tool()，
   不自己寫 insert——分類自動建立、id 去重、sort_order、env_types 同步都在裡面。

用法（先看會寫什麼，不會真的寫）：
    .venv\\Scripts\\python.exe scripts\\add_tool_from_project.py <卡片.json>

確認沒問題後真的寫入：
    .venv\\Scripts\\python.exe scripts\\add_tool_from_project.py <卡片.json> --apply

已存在同一個 id 時要明講才會覆蓋：
    .venv\\Scripts\\python.exe scripts\\add_tool_from_project.py <卡片.json> --apply --update

JSON 格式（只有 name_zh 是必填，其餘可省略）：
{
  "id": "gs1-barcode-generator",
  "name": "GS1 Barcode Generator",
  "name_zh": "國際條碼小工具（GS1條碼）",
  "description": "一段話說明",
  "category": "utility",
  "tags": ["python", "條碼"],
  "icon": "barcode",
  "color": "#6366F1",
  "path": "C:\\\\...\\\\專案資料夾",
  "url": "http://127.0.0.1:8880",
  "external_url": "",
  "pin_path": false,
  "pin_url": false,
  "pin_external_url": false,
  "commands": [
    {"label": "啟動 Bat", "cmd": "C:\\\\...\\\\啟動.bat", "env": "bat", "pinned": true}
  ]
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from data.tools import add_tool, get_tool, load_categories, update_tool  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def to_form(card: dict) -> dict:
    """把好讀的卡片 JSON 轉成 add_tool()/update_tool() 吃的表單格式。

    表單格式是網頁 <form> 的扁平鍵值，commands 會被拆成 cmd_label_0 / cmd_cmd_0 …
    """
    form: dict = {
        "id": card.get("id", ""),
        "name": card.get("name", ""),
        "name_zh": card.get("name_zh", ""),
        "description": card.get("description", ""),
        "category": card.get("category", "utility"),
        "tags": card.get("tags", []),
        "icon": card.get("icon", "box"),
        "color": card.get("color", "#6366F1"),
        "status": card.get("status", "active"),
        "path": card.get("path", ""),
        "url": card.get("url", ""),
        "external_url": card.get("external_url", ""),
    }
    for key in ("pin_path", "pin_url", "pin_external_url", "highlight"):
        if card.get(key):
            form[key] = "on"

    for i, c in enumerate(card.get("commands", [])):
        form[f"cmd_label_{i}"] = c.get("label", "")
        form[f"cmd_cmd_{i}"] = c.get("cmd", "")
        form[f"cmd_env_{i}"] = c.get("env", "local")
        if c.get("pinned"):
            form[f"cmd_pinned_{i}"] = "on"
    return form


def describe(card: dict, exists: dict | None) -> None:
    cats = {c["id"]: c.get("name_zh", c["id"]) for c in load_categories()}
    cat = card.get("category", "utility")
    print()
    print("  即將寫入儀表板的內容")
    print("  " + "-" * 64)
    print(f"  中文名稱   {card.get('name_zh', '')}")
    print(f"  英文名稱   {card.get('name', '')}")
    print(f"  卡片 id    {card.get('id', '(自動產生)')}")
    print(f"  分類       {cat}（{cats.get(cat, '⚠️ 這個分類不存在，會自動建立')}）")
    print(f"  標籤       {'、'.join(card.get('tags', [])) or '(無)'}")
    print(f"  圖示／顏色 {card.get('icon', 'box')} / {card.get('color', '#6366F1')}")
    print(f"  說明       {(card.get('description') or '(無)')[:60]}")
    print(f"  本地資料夾 {card.get('path') or '(無)'}")
    print(f"  本地網址   {card.get('url') or '(無)'}")
    print(f"  線上網址   {card.get('external_url') or '(無)'}")
    print("  按鈕：")
    for c in card.get("commands", []):
        pin = " ★釘選" if c.get("pinned") else ""
        print(f"    [{c.get('env', 'local'):<7}] {c.get('label', ''):<14} {c.get('cmd', '')}{pin}")
    print("  " + "-" * 64)
    if exists:
        print(f"  ⚠️ id「{card.get('id')}」已經存在（現在叫「{exists.get('name_zh')}」）。")
        print("     要覆蓋請加 --update，否則 add 會自動改用不重複的新 id。")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="把專案連結寫成 DinoDashboard 卡片")
    ap.add_argument("card_json", help="卡片 JSON 檔路徑")
    ap.add_argument("--apply", action="store_true", help="真的寫入；不加只是預覽")
    ap.add_argument("--update", action="store_true", help="id 已存在時覆蓋既有卡片")
    args = ap.parse_args()

    card = json.loads(Path(args.card_json).read_text(encoding="utf-8"))
    if not card.get("name_zh"):
        print("  [錯誤] JSON 缺少 name_zh（中文名稱），這是必填。")
        return 1

    exists = get_tool(card["id"]) if card.get("id") else None
    describe(card, exists)

    if not args.apply:
        print("  這是預覽，什麼都沒寫。確認無誤後加 --apply 再跑一次。")
        return 0

    form = to_form(card)
    if exists and args.update:
        row = update_tool(card["id"], form)
        print(f"  已更新卡片：{row['id']}（{row['name_zh']}）")
    else:
        row = add_tool(form)
        print(f"  已新增卡片：{row['id']}（{row['name_zh']}）")
    print("  儀表板重新整理就看得到：http://localhost:5050")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

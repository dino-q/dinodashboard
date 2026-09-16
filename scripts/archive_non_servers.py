"""把「不是伺服器」的 bat 在伺服器分頁封存起來。

清單本身是從卡片動態生成的，刪不掉也不該刪——卡片上那些 bat 是有用的工具捷徑。
但它們不是常駐服務，留在啟動清單只會變雜訊，所以走「封存」。

用法：
    .venv\\Scripts\\python.exe scripts\\archive_non_servers.py            # 預覽
    .venv\\Scripts\\python.exe scripts\\archive_non_servers.py --apply    # 真的封存
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

from data.launcher import build_server_rows, make_key, upsert_entry  # noqa: E402
from data.tools import load_tools  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

CC = r"C:\Users\AG_Di\Desktop\automation\Claude_code"

# 要封存的 bat（完整路徑）與原因
AUTO = r"C:\Users\AG_Di\Desktop\automation"

# 註：檔名含「安裝／install／setup」的不用列在這裡——
#     is_install_bat() 已經自動把它們擋在清單外（畫面上會顯示「已自動略過 N 支」）。
TARGETS = [
    # --- 3D：全部是一次性產圖／開桌面程式，不是常駐服務 ---
    (CC + r"\tools\3D_Draw\產生3D.bat",        "一次性產圖（拖檔上去）"),
    (CC + r"\tools\3D_Draw\手把十視圖.bat",      "一次性產圖"),
    (CC + r"\tools\3D_Draw\產生成品圖.bat",      "一次性產圖"),
    (CC + r"\tools\3D_Draw\開啟3D模型.bat",     "開桌面檢視器"),
    (CC + r"\tools\3D_Draw\啟動.bat",          "開 Blender 桌面程式"),
    (CC + r"\tools\3D_viewer\啟動.bat",         "開 F3D 桌面程式"),

    # --- 其他一次性腳本／登入用 ---
    (AUTO + r"\Playwright\_login\登入.bat",                      "一次性登入"),
    (AUTO + r"\Playwright\shopee-brand-monitor\登入帳號.bat",      "一次性登入"),
    (AUTO + r"\Python_code\Carrefour_DM\From Python\run_dm.bat", "跑完就結束"),
    (AUTO + r"\Python_code\PX_DM\From Python\run_px_dm.bat",     "跑完就結束"),
    (CC + r"\tools\How_To_Project\analyze.bat",                  "一次性分析工具"),
    (r"C:\Users\AG_Di\claude-debug.bat",                         "不在專案資料夾的偵錯腳本"),
]


def main() -> int:
    apply = "--apply" in sys.argv
    data = build_server_rows(load_tools())
    # 要連 archived 一起查，否則「已經封存過的」會被誤報成「找不到」，
    # 看起來像清單缺東西。（2026-09-15 踩過：Dino 自己先封存了 5 筆。）
    rows = {r["bat_key"]: r for r in data["active"] + data["archived"]}
    auto_skipped = {make_key(r["bat_path"]) for r in data.get("skipped_installs", [])}

    done = skipped = missing = 0
    for path, why in TARGETS:
        key = make_key(path)
        row = rows.get(key)
        if not row:
            if key in auto_skipped:
                print(f"  [自動略過] {path.rsplit(chr(92), 1)[-1]:<18} 是安裝腳本，本來就不進清單")
            else:
                print(f"  [找不到]   {path.rsplit(chr(92), 1)[-1]:<18} 卡片上沒有登記這支 bat")
            missing += 1
            continue
        if row["archived"]:
            print(f"  [已封存]   {row['label']}")
            skipped += 1
            continue
        if apply:
            upsert_entry(key, bat_path=row["bat_path"], tool_id=row["tool_id"],
                         archived=True, port=row["port"])
        print(f"  [{'封存' if apply else '將封存'}] {row['label']:<28} ← {why}")
        done += 1

    print()
    if apply:
        print(f"完成：封存 {done} 筆，已封存過 {skipped} 筆，找不到 {missing} 筆。")
    else:
        print(f"預覽：會封存 {done} 筆（已封存 {skipped}、找不到 {missing}）。加 --apply 才會真的寫入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""伺服器分頁（Server_Launcher 伺服器總管）的資料層。

清單不是另外維護的——每次從 `tools.commands` 裡 env='bat' 的項目動態生成，
再跟 `launcher_entries` 表合併出「顯示/預設勾/封存/顯示名稱」四個狀態。
所以在任何卡片新增一筆 bat 指令，伺服器分頁就會自動多一列。

建表 SQL：supabase_db/launcher_entries.sql（第一次用要先貼到 Supabase SQL Editor 跑）
"""
from __future__ import annotations

import hashlib
import re

from data.supabase_client import get_client

BAT_ENV = "bat"
TABLE = "launcher_entries"

# 本機伺服器總管的入口，放在這一頁最上面讓 Dino 一鍵複製。
# 刻意寫死絕對路徑：這支 Flask 可能跑在 Render 上、掃不到本機檔案系統，
# 而這個字串的用途純粹是「顯示給人複製」，程式不會去執行它。
LAUNCHER_BAT = (
    "C:\\Users\\AG_Di\\Desktop\\automation\\Claude_code"
    "\\system\\Server_Launcher\\伺服器總管.bat"
)

# 有些指令是 `cmd /c "C:\...\run.bat"` 這種包裝，要先剝掉才拿得到真正的路徑。
_CMD_WRAPPER = re.compile(r'^\s*cmd(?:\.exe)?\s+/[a-z]\s+', re.I)
_BAT_IN_TEXT = re.compile(r'([a-zA-Z]:\\[^"\'<>|]*?\.bat)', re.I)

# 安裝類的 bat 不該出現在「伺服器」分頁：它是一次性的裝依賴腳本，
# 不是可以啟動／關閉／看 port 的服務。（Dino 2026-09-15 指示）
# 卡片上仍然保留這顆按鈕，只是不進伺服器清單。
_INSTALL_BAT_RE = re.compile(r'(安裝|install|setup)', re.I)


def is_install_bat(bat_path: str, label: str = '') -> bool:
    """這支 bat 是不是「裝依賴」用的一次性腳本（＝不是伺服器）。

    檔名或卡片上的標籤任一個命中就算，例如 安裝.bat／安裝套件.bat／install.bat。
    """
    name = (bat_path or '').rsplit(chr(92), 1)[-1]
    return bool(_INSTALL_BAT_RE.search(name) or _INSTALL_BAT_RE.search(label or ''))


def extract_bat_path(cmd: str) -> str:
    """從指令字串裡挖出 .bat 的完整路徑；挖不到回空字串。

    吃得下這幾種寫法：
        C:\\path\\啟動.bat
        "C:\\path with space\\啟動.bat"
        cmd /c "C:\\path\\run.bat"
        C:\\path\\run.bat --flag
    """
    if not cmd:
        return ""
    s = cmd.strip()
    s = _CMD_WRAPPER.sub("", s)
    s = s.strip().strip('"').strip("'")
    if s.lower().endswith(".bat"):
        return s
    m = _BAT_IN_TEXT.search(cmd)
    return m.group(1) if m else ""


def make_key(bat_path: str) -> str:
    """路徑 → 穩定的短代號。

    直接拿 Windows 路徑當網址參數會死在反斜線與中文上，所以雜湊一次。
    正規化：統一反斜線、去掉頭尾空白與引號、轉小寫（Windows 路徑不分大小寫）。
    """
    norm = (bat_path or "").strip().strip('"').replace("/", "\\").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _port_from_url(url: str):
    """從 http://127.0.0.1:8884/ 這種網址挖出 port；沒有就回 None。"""
    m = re.search(r"://[^/]*?:(\d{2,5})\b", url or "")
    if not m:
        return None
    try:
        p = int(m.group(1))
    except ValueError:
        return None
    return p if 1 <= p <= 65535 else None


def _clean_label(tool_name: str, cmd_label: str, sibling_count: int) -> str:
    """自動帶的顯示名稱。

    同一張卡片只有一筆 bat → 直接用卡片中文名。
    有多筆 → 加上指令標籤區分（並去掉「啟動」前綴，不然每一列都叫「啟動 XXX」）。
    """
    base = (tool_name or "").strip()
    if sibling_count <= 1:
        return base
    tail = (cmd_label or "").strip()
    tail = re.sub(r"^\s*啟動\s*", "", tail)
    tail = re.sub(r"\s*[Bb]at\s*$", "", tail).strip()
    return f"{base}－{tail}" if tail else base


def collect_bat_commands(tools: list[dict], skipped: list | None = None) -> list[dict]:
    """掃過所有卡片，收出每一筆 env='bat' 的指令。

    回傳已排序（依卡片 sort_order，再依指令在卡片內的順序）的候選清單。
    同一個 bat 路徑被兩張卡片登記時只留第一筆，避免清單出現重複列。

    `skipped`：傳一個 list 進來，會把被 is_install_bat() 略過的安裝腳本填進去。
    ⚠️ 這些是被**程式**藏起來的、不是使用者封存的，所以一定要能回報給畫面顯示，
       否則就是「東西默默消失而且查不出原因」。
    """
    found: list[dict] = []
    seen: set[str] = set()

    for t in sorted(tools, key=lambda x: (x.get("sort_order") or 0, x.get("id") or "")):
        cmds = [c for c in (t.get("commands") or [])
                if (c.get("env") or "").strip().lower() == BAT_ENV]
        if not cmds:
            continue
        tool_name = t.get("name_zh") or t.get("name") or t.get("id") or ""
        port = _port_from_url(t.get("url") or "")

        # 先把「真的會進清單」的挑出來，再算同卡片有幾筆——
        # 不然安裝類被濾掉之後，只剩一支的卡片還是會被加上「－啟動」這種後綴。
        usable = []
        for c in cmds:
            bp = extract_bat_path(c.get("cmd") or "")
            if not bp:
                continue
            if is_install_bat(bp, c.get("label") or ""):
                if skipped is not None:
                    skipped.append({
                        "tool_name": tool_name,
                        "label": (c.get("label") or "").strip(),
                        "bat_path": bp,
                    })
                continue
            usable.append((c, bp))

        for c, bat_path in usable:
            key = make_key(bat_path)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "bat_key": key,
                "bat_path": bat_path,
                "tool_id": t.get("id"),
                "tool_name": tool_name,
                "cmd_label": (c.get("label") or "").strip(),
                "auto_label": _clean_label(tool_name, c.get("label") or "", len(usable)),
                "color": t.get("color") or "#6366F1",
                "icon": t.get("icon") or "box",
                "category": t.get("category") or "",
                "url": (t.get("url") or "").strip(),                    # 本機網址
                "external_url": (t.get("external_url") or "").strip(),  # 線上網址
                "port": port,
            })
    return found


def load_entries() -> dict[str, dict]:
    """讀 launcher_entries，回傳 {bat_key: row}。

    表還沒建（第一次用）時回空字典並標記，讓畫面能顯示「請先建表」而不是整頁 500。
    """
    try:
        rows = get_client().table(TABLE).select("*").execute().data or []
    except Exception:
        return {"__missing__": {}}
    return {r["bat_key"]: r for r in rows}


def table_missing(entries: dict) -> bool:
    return "__missing__" in entries


def build_server_rows(tools: list[dict]) -> dict:
    """合併三種來源，組出這一頁要顯示的清單。

    1. 卡片裡 env='bat' 的啟動指令（主要來源）
    2. launcher_entries 存下來的開關狀態（顯示/預設/封存/改名/port）
    3. 手動新增、沒有對應卡片的項目（tool_id 是空的那些）

    回傳 {active, archived, missing_table, launcher_bat}
    """
    skipped_installs: list[dict] = []
    found = collect_bat_commands(tools, skipped_installs)
    entries = load_entries()
    missing = table_missing(entries)

    rows = []
    for i, f in enumerate(found):
        e = entries.get(f["bat_key"]) or {}
        row = dict(f)
        row["manual"] = False
        row["label"] = (e.get("label") or "").strip() or f["auto_label"]
        row["visible"] = bool(e.get("visible", True))
        row["default_on"] = bool(e.get("default_on", False))
        row["archived"] = bool(e.get("archived", False))
        row["sort_order"] = e.get("sort_order", i)
        # 卡片的 url 沒有 port 時，用這一頁手動填的 port 補
        if row["port"] is None and e.get("port"):
            row["port"] = e["port"]
        rows.append(row)

    # 手動新增的：存在 launcher_entries 但沒有任何卡片指向它（tool_id 為空）。
    # 像 n8n\start-n8n.bat 這種沒登記成卡片的，就是走這條。
    seen = {r["bat_key"] for r in rows}
    base = len(found)
    for j, (key, e) in enumerate(sorted(entries.items())):
        if key == "__missing__" or key in seen or e.get("tool_id"):
            continue
        rows.append({
            "bat_key": key,
            "bat_path": e.get("bat_path") or "",
            "tool_id": None,
            "tool_name": "手動新增",
            "cmd_label": "",
            "auto_label": e.get("label") or "",
            "color": "#64748B",
            "icon": "terminal",
            "category": "__manual__",
            "url": ("http://127.0.0.1:%d" % e["port"]) if e.get("port") else "",
            "external_url": "",
            "manual": True,
            "label": (e.get("label") or "").strip() or (e.get("bat_path") or "").rsplit("\\", 1)[-1],
            "visible": bool(e.get("visible", True)),
            "default_on": bool(e.get("default_on", False)),
            "archived": bool(e.get("archived", False)),
            "port": e.get("port") or None,
            "sort_order": e.get("sort_order", base + j),
        })

    active = [r for r in rows if not r["archived"]]
    archived = [r for r in rows if r["archived"]]
    active.sort(key=lambda r: (r["sort_order"], r["label"]))
    archived.sort(key=lambda r: (r["sort_order"], r["label"]))

    # 分類分組（給「全部／分類」篩選與收折用）。載入分類失敗就退回不分組，
    # 頁面照樣看得到東西。
    try:
        from data.tools import load_categories
        groups = group_by_category(active, load_categories())
    except Exception:
        groups = group_by_category(active, [])

    return {"active": active, "archived": archived, "missing_table": missing,
            "launcher_bat": LAUNCHER_BAT, "groups": groups,
            "skipped_installs": skipped_installs}


class TableMissing(RuntimeError):
    """launcher_entries 還沒建。讓呼叫端可以回一句人話，而不是噴 500。"""


def group_by_category(rows: list[dict], categories: list[dict]) -> list[dict]:
    """把列依「卡片的分類」分組，給前端做篩選與收折用。

    ♻️ 沿用 categories 表既有的 name_zh / icon / sort_order，不另外定義一套分類。
    手動新增的沒有卡片，歸到虛擬分類 __manual__，永遠排最後。
    """
    catmap = {c["id"]: c for c in categories}
    # ⚠️ 排序基準用「categories 清單本身的順序」，不要自己讀某個欄位。
    #    load_categories() 回傳時已經照卡片頁的順序排好了（欄位叫 order 不叫 sort_order，
    #    2026-09-15 就是讀錯欄位、全部落到預設值，變成按筆畫排）。
    #    用位置當索引，不管欄位以後怎麼改名，都跟卡片頁一致。
    catpos = {c["id"]: i for i, c in enumerate(categories)}

    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r.get("category") or "__none__", []).append(r)

    out = []
    for cid, rs in buckets.items():
        c = catmap.get(cid)
        if c:
            name, icon, sort = c.get("name_zh") or cid, c.get("icon") or "folder", catpos.get(cid, 900)
        elif cid == "__manual__":
            name, icon, sort = "手動新增", "terminal", 998
        else:
            name, icon, sort = "未分類", "folder", 997
        out.append({"id": cid, "name": name, "icon": icon, "rows": rs,
                    "count": len(rs), "sort": sort})
    out.sort(key=lambda g: (g["sort"], g["name"]))
    return out


def upsert_entry(bat_key: str, *, bat_path: str = "", tool_id: str | None = None,
                 **fields) -> None:
    """寫入一支 bat 的狀態。第一次改某一列時才會真的產生資料列。

    表還沒建時丟 TableMissing，由路由層轉成 toast 提示。
    """
    payload = {"bat_key": bat_key}
    if bat_path:
        payload["bat_path"] = bat_path
    if tool_id:
        payload["tool_id"] = tool_id
    payload.update({k: v for k, v in fields.items() if v is not None})
    try:
        get_client().table(TABLE).upsert(payload, on_conflict="bat_key").execute()
    except Exception as exc:
        raise TableMissing(str(exc)) from exc


_WIN_BAT_PATH = re.compile(r'^[a-zA-Z]:\\[^<>"|?*\r\n]+\.bat$', re.I)


def validate_bat_path(raw: str) -> tuple[str, str]:
    """檢查手動輸入的路徑。回傳 (正規化後的路徑, 錯誤訊息)；成功時錯誤訊息是空字串。

    只驗格式不驗存在與否——這支 Flask 可能跑在 Render 上，看不到本機檔案系統。
    檔案在不在，由本機的伺服器總管啟動時回報。
    """
    p = (raw or "").strip().strip('"').strip("'")
    if not p:
        return "", "路徑不能空白"
    p = p.replace("/", "\\")
    if not p.lower().endswith(".bat"):
        return "", "路徑必須是 .bat 結尾"
    if not _WIN_BAT_PATH.match(p):
        return "", "請填完整的 Windows 路徑，例如 C:\\Users\\AG_Di\\...\\start.bat"
    return p, ""


def add_manual_entry(bat_path: str, label: str = "", port: int | None = None) -> str:
    """手動新增一支沒有對應卡片的 bat。回傳它的 bat_key。

    tool_id 刻意留空，build_server_rows 就是靠這個判斷「這是手動加的」。
    """
    key = make_key(bat_path)
    # ⚠️ 已經有這一筆就原封不動，**不覆蓋既有**設定。
    # 這裡以前是 upsert，等於重跑一次 scripts/seed_manual_servers.py
    # 就會把使用者改過的名稱、顯示、預設、封存全部打回預設值。
    # （Dino 2026-09-15 踩到：伺服器分頁的名稱被固定成腳本裡寫死的字串。）
    try:
        existing = get_client().table(TABLE).select("bat_key").eq("bat_key", key).execute().data
    except Exception as exc:
        raise TableMissing(str(exc)) from exc
    if existing:
        return key

    payload = {
        "bat_key": key,
        "bat_path": bat_path,
        "label": (label or "").strip(),
        "visible": True,
        "default_on": False,
        "archived": False,
    }
    if port:
        payload["port"] = port
    try:
        get_client().table(TABLE).insert(payload).execute()
    except Exception as exc:
        raise TableMissing(str(exc)) from exc
    return key


def delete_entry(bat_key: str) -> None:
    """刪掉一筆紀錄。只用在手動新增的項目——卡片來的刪了也會再長回來。"""
    try:
        get_client().table(TABLE).delete().eq("bat_key", bat_key).execute()
    except Exception as exc:
        raise TableMissing(str(exc)) from exc


def get_manifest(tools: list[dict]) -> list[dict]:
    """給本機伺服器總管讀的精簡清單：只留「要顯示且沒封存」的。

    欄位刻意壓到最少，讓 PowerShell 端好解析。
    """
    data = build_server_rows(tools)
    out = []
    for r in data["active"]:
        if not r["visible"]:
            continue
        out.append({
            "key": r["bat_key"],
            "label": r["label"],
            "bat": r["bat_path"],
            "port": r["port"] or 0,
            "default_on": r["default_on"],
            "order": r["sort_order"],
        })
    return out

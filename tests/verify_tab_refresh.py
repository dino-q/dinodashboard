"""驗證：從頁面外新增卡片後，不重新整理頁面，切到「本地」「伺服器」分頁就看得到（2026-10-04 修正）。

用法：先啟動 python app.py（5050），再用共用 Playwright venv 跑這支：
  "C:/Users/AG_Di/Desktop/automation/Playwright/.venv/Scripts/python.exe" tests/verify_tab_refresh.py
資料庫操作（登入 cookie、新增／刪除臨時卡片 zz-tab-refresh-test）交給儀表板自己的 .venv 執行（同檔的 helper 模式）。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH_PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TEST_ID = "zz-tab-refresh-test"
NAME = "分頁重抓測試卡（會自動刪除）"
BASE = "http://127.0.0.1:5050"


def helper(action):
    """在儀表板 venv 裡跑：cookie／add／delete。"""
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from app import app
    from data.tools import add_tool, delete_tool
    if action == "cookie":
        c = app.test_client()
        with c.session_transaction() as s:
            s["user"] = {"username": "tab-refresh-test", "role": "admin"}
        c.get("/")
        print(c.get_cookie("session").value)
    elif action == "add":
        with app.test_request_context("/"):
            add_tool({"id": TEST_ID, "name": "Tab Refresh Test", "name_zh": NAME, "category": "utility",
                      "url": "http://127.0.0.1:65001", "cmd_label_0": "啟動 Bat",
                      "cmd_cmd_0": "C:\\Users\\AG_Di\\zz_tab_refresh_test\\啟動.bat", "cmd_env_0": "bat"})
    elif action == "delete":
        with app.test_request_context("/"):
            delete_tool(TEST_ID)


def run(action):
    return subprocess.run([DASH_PY, __file__, "--helper", action], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from playwright.sync_api import sync_playwright
    cookie = run("cookie").splitlines()[-1]
    results = []

    def check(name, cond):
        results.append(bool(cond)); print(("✓ " if cond else "✗ ") + name)

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1366, "height": 900})
        ctx.add_cookies([{"name": "session", "value": cookie, "url": BASE}])
        page = ctx.new_page()
        page.goto(BASE + "/")
        page.wait_for_selector("#server-view", state="attached")
        check("頁面載入時還沒有測試卡", NAME not in page.content())
        run("add")  # 從頁面外新增（等同 /project-link-sync 腳本直接寫 Supabase）
        try:
            page.click(".view-toggle-btn[data-view=local]")
            page.wait_for_function(f"document.getElementById('local-view').textContent.includes({NAME!r})", timeout=15000)
            check("不重整、切到「本地」就出現新卡片", True)
            page.click(".view-toggle-btn[data-view=server]")
            page.wait_for_function(f"document.getElementById('server-view').textContent.includes({NAME!r})", timeout=15000)
            check("不重整、切到「伺服器」就出現新卡片", True)
            page.click(".view-toggle-btn[data-view=cards]")
            check("切回卡片區正常", page.locator("#tool-grid").count() == 1)
        except Exception as e:
            check(f"切分頁後出現新卡片（{e.__class__.__name__}）", False)
        finally:
            run("delete")
            print("已刪除測試卡", TEST_ID)
        b.close()
    print(f"結果：{sum(results)}/{len(results)} 通過")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--helper":
        helper(sys.argv[2])
    else:
        main()

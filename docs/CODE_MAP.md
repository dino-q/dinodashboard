# CODE_MAP

## 自動維運

| 檔案／函式 | 用途 | 沿用方式 |
|---|---|---|
| `scripts/cron_job_guardian.py` → `health_is_ready()` | 喚醒 Render，並確認 `/ping-db` 與 Supabase 已恢復 | 其他外部健康檢查可直接傳入 URL |
| `scripts/cron_job_guardian.py` → `request_json()` | 呼叫 cron-job.org API，且不輸出 Bearer Token | 後續 cron-job.org 管理功能沿用此函式 |
| `scripts/cron_job_guardian.py` → `repair_if_needed()` | 只在端點健康時重新啟用精確匹配的 keepalive 工作 | GitHub Actions 或本機人工 dry-run 均可呼叫 |
| `scripts/cron_job_guardian.py` → `report_error()` | 將去敏後的失敗原因寫入 GitHub Actions 註記 | 自動化執行失敗時沿用，禁止傳入 Secret |

## 自動化入口

| 檔案 | 用途 |
|---|---|
| `.github/workflows/cron-job-guardian.yml` | 每 30 分鐘巡檢並執行自動修復，也支援手動執行 |
| `static/js/dashboard.js` → `refreshSideView()`＋`routes/api.py` → `GET /api/local` | 🆕 切到「本地」「伺服器」分頁時重抓最新清單（2026-10-04）。這兩塊原本只在整頁載入時產生，從頁面外新增的卡片不會出現。♻️ 沿用既有 `GET /api/server`（`_server_response`）、`build_local_map()` 與 `_local_list.html`。驗證：`tests/verify_tab_refresh.py`（會建立並刪除臨時卡片）。 |
| `scripts/add_tool_from_project.py` → `find_duplicates()` | 🆕 新增卡片前找「id 不同但資料夾路徑或中文名稱相同」的既有卡片；`--apply` 撞到就停（`--allow-duplicate` 才放行）。沿用 `load_tools()`。不沿用 `get_tool()` 的原因：它只能用 id 查，手動建的卡片 id 是亂碼，撞不到。 |
| `scripts/update_distributor_test_launch.py` → `reconciled_commands()` | 🆕 精確補／更新「經銷商管理系統(HTML)」卡片的兩個測試入口；沿用 `get_tool()` 與 Supabase `tools.commands` 單欄更新，不改其他卡片或欄位。測試 BAT 標成 `local`，避免伺服器總管自動多列一台；按鈕仍保留在原工具卡。預設預覽，`--apply` 寫入並讀回核對。 |

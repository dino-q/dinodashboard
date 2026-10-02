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
| `scripts/update_distributor_test_launch.py` → `reconciled_commands()` | 🆕 精確補／更新「經銷商管理系統(HTML)」卡片的兩個測試入口；沿用 `get_tool()` 與 Supabase `tools.commands` 單欄更新，不改其他卡片或欄位。預設預覽，`--apply` 寫入並讀回核對。 |

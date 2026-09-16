# GIT_PUBLISH.md — DinoDashboard 推送設定

> 依全域規範：任何專案要連 GitHub（建 remote / 首次 push / 改可見性）之前，先看這份檔。

## Repo

| 項目 | 設定 |
|---|---|
| Owner | `dino-q`（全域規範：所有 repo 一律 dino-q） |
| Repo 名 | `dinodashboard` |
| 連結 | https://github.com/dino-q/dinodashboard |
| 可見性 | **Public（公開）** — 沿用 2026-04-19 建立時的設定 |
| 預設分支 | `main` |
| agdino 協作者 | **否** — 個人作品展示頁，公司帳號用不到 |
| 建立日期 | 2026-04-19 |

## ⚠️ 這是公開 repo，push 前必想一次

任何人都看得到 repo 內容。已知且可接受的既有情況：程式碼與部分文件裡有
`C:\Users\AG_Di\...` 開頭的本機路徑（`FEATURES.md`、`data\launcher.py`、
`data\auto_tag.py`、`scripts\*.py`、`docs\DESIGN_*.md`、
`templates\partials\_server_list.html` 等）。

**不要再往公開 repo 增加的東西**：

- 公司 Notion 的頁面 ID／網址、公司內部架構描述
- 任何帳號、金鑰、token、連線字串
- 客戶或公司專案的名稱與細節

需要寫這類內容時，改放到私有 repo
`https://github.com/dino-q/ClaudeCode_to_Codex_CLI_config_Sync`，
或只留在本機並加進 `.gitignore`。

## 推送範圍

### 會進 git

- 應用程式碼：`app.py`、`config.py`、`routes\`、`data\`、`templates\`、`static\`
- 部署設定：`render.yaml`、`Procfile`、`requirements.txt`、`runtime.txt`、`.python-version`
- 文件：`README`／`CLAUDE.md`／`AGENTS.md`／`DEPLOY.md`／`FEATURES.md`、`docs\`
- 維運腳本：`scripts\`

### 絕不進 git（`.gitignore` 已擋）

| 項目 | 原因 |
|---|---|
| `.env`、`.env.*`（`.env.example` 除外） | Supabase 金鑰與 Flask secret |
| `credentials.json` | 帳密資料 |
| `.flask_secret` | 本機 session 金鑰 |
| `專案資訊.md` | 未納入版控，內含完整本機路徑與部署備註 |
| `data\card_*.json` | 一次性卡片匯入檔，不是專案的一部分 |
| `static\screenshots\*` | 使用者上傳的截圖 |
| `.venv\`、`__pycache__\` | 可重建 |

## ⚠️ push 會觸發線上部署

`main` 分支 push 之後，**Render 會自動重新部署** https://dinodashboard.onrender.com
（`render.yaml` Blueprint）。就算改的只是文件也一樣會重啟。

- 免費方案，冷啟動 30 秒以上
- 15 分鐘無流量會 sleep，靠 cron-job.org 每 5 分鐘打 `/ping` 保活
- 環境變數（`SUPABASE_URL`／`SUPABASE_SECRET_KEY` 等）在 Render 控制台手動設定，不在 repo 裡

急著看網站的時候，不要在那個當下 push。

## 推送前檢查

1. `git status` 確認沒有把 `.env`、`credentials.json`、`.flask_secret` 誤加進去
2. 這次改動有沒有新增公司 Notion 頁面 ID 或內部資訊（見上面的公開 repo 提醒）
3. 確認 `gh auth status` 的 active account 是 `dino-q`

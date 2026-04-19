# DinoDashboard — Render + Supabase + UptimeRobot 部署指南

這份文件是一次性的上線步驟清單。照順序做，每一步做完再做下一步。

---

## 需求環境

- **Python 3.13**（鎖定版本在 `runtime.txt` 和 `.python-version`）
- **不要用 Python 3.14**：`supabase` 的相依 `pyiceberg` 尚無 3.14 的預編 wheel，從 source build 會需要 Visual C++ Build Tools
- 本機建議用 venv 隔離：
  ```powershell
  py -3.13 -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

---

## 架構總覽

```
使用者瀏覽器
    ↓ HTTPS
Render 的 Web Service  ←── UptimeRobot 每 5 分鐘 HEAD /ping（防 sleep）
    ↓
Supabase Postgres + Storage（資料 + 截圖）
```

- **Render 免費方案** 15 分鐘沒流量會 sleep，冷啟動要 30 秒以上
- **UptimeRobot 免費方案** 可建 50 個 HTTP Monitor，每 5 分鐘戳一次，剛好保住 Render

---

## 步驟 1 — Supabase 建資料庫

1. 到 https://supabase.com/dashboard，登入後建一個新 project（Region 挑最近，例如 Tokyo）
2. Project 建好後記下兩個東西（**只給你自己看**，千萬不要 commit 到 Git）：
   - **Project URL**：`Settings → API → Project URL`，長得像 `https://xxxxx.supabase.co`
   - **Secret API key**：`Settings → API → Project API keys → secret` 那排的 key（**不是** anon key），長得像 `sb_secret_xxx` 或 `eyJ...`
3. 點 `SQL Editor` → `New query`，把 `supabase_db/schema.sql` 整份貼上去 → `Run`
4. 跑完會看到 `Success. No rows returned` — 這代表 5 張 table 建好了

## 步驟 2 — Supabase 建 Storage bucket（存截圖）

1. 左側選 `Storage`
2. 點 `New bucket`
   - **Name**：`screenshots`（必須完全一樣，程式寫死在 `routes/api.py`）
   - **Public bucket**：**勾選**（不勾的話 `<img>` 讀不到）
3. 建好後不用設 policy，public bucket 預設就能 public read

## 步驟 3 — 本機建 `.env` 並灌資料進 Supabase

在專案根目錄（`DinoDashboard/`）建 `.env`：

```bash
# 從 .env.example 複製一份
cp .env.example .env
```

打開 `.env` 填入步驟 1 拿到的 URL 和 key：

```
SUPABASE_URL=https://你的project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_xxx
FLASK_SECRET_KEY=先放什麼都好_反正本機
PRIVATE_MODE=false
ALLOW_REGISTRATION=false
```

裝套件 + 跑 migration：

```bash
pip install -r requirements.txt
python supabase_db/migrate.py
```

你會看到：

```
🔗 連線：https://xxx.supabase.co
🧹 清空舊資料...
📁 分類：匯入 X 筆
🔧 工具：匯入 X 筆
...
✅ 全部匯入完成！
```

有錯的話最常見是：
- **"Missing SUPABASE_URL ..."** → `.env` 沒存好 / key 名字打錯
- **"relation does not exist"** → 步驟 1 的 schema.sql 沒跑過

## 步驟 4 — 本機跑起來驗證

```bash
python app.py
# 瀏覽器打開 http://localhost:5050
```

檢查清單：
- [ ] 首頁卡片有顯示
- [ ] 截圖顯示正常（如果原本就有的話。新上傳的會存到 Supabase Storage）
- [ ] 可以登入原本的帳號
- [ ] `http://localhost:5050/ping` 回傳 `ok`

## 步驟 5 — 推 Git 並部署到 Render

**重要**：先確認 `.env` 在 `.gitignore` 裡（本專案已經設好，但 double-check 不會有壞事）：

```bash
git check-ignore .env
# 應該輸出：.env
```

提交 + push：

```bash
git add .
git commit -m "feat: migrate to Supabase + Render deploy config"
git push
```

到 Render：

1. 登入 https://render.com
2. `New +` → `Blueprint`（會自動讀 `render.yaml`）
3. 連你的 GitHub repo → 選 DinoDashboard
4. Render 會問你填兩個環境變數（因為 `render.yaml` 標了 `sync: false`）：
   - `SUPABASE_URL` → 貼步驟 1 的 URL
   - `SUPABASE_SECRET_KEY` → 貼步驟 1 的 secret key
5. `Apply` → Render 開始 build 和 deploy，大約 2–3 分鐘
6. 完成後給你一個網址，例如 `https://dinodashboard.onrender.com`

開上去驗證：
- [ ] 首頁能開
- [ ] `/ping` 回 `ok`
- [ ] 能登入
- [ ] 截圖顯示正常

## 步驟 6 — cron-job.org 防止 Render sleep

### 為什麼選 cron-job.org 而不是 UptimeRobot？

這兩個服務設計目的根本不一樣：

| | cron-job.org | UptimeRobot |
|---|---|---|
| **本質** | 排程執行器（遠端 crontab） | 存活監控（健康檢查員） |
| **它問的問題** | "時間到了該不該 call 這個 URL？" | "這個服務還活著嗎？Uptime 幾 %？" |

我們的 `/ping` 需求本質上是**前者**——定時戳一下讓 Render 醒著，不需要監控統計。所以用排程器是更直覺的選擇。

### 功能比較（都用免費方案）

| 項目 | cron-job.org | UptimeRobot |
|---|---|---|
| 最小間隔 | **1 分鐘** | 5 分鐘 |
| 任務/監控數 | 無硬性上限 | 50 個 |
| 排程語法 | 標準 cron（`*/5 * * * *`） | 固定下拉選單 |
| Email 告警 | ✓ | ✓ |
| Slack/Discord | ✗（付費） | ✓ |
| Uptime % 統計 | ✗（只有執行紀錄） | ✓ |
| 公開狀態頁 | ✗ | ✓ |
| SSL 到期提醒 | ✗ | ✓ |
| 執行紀錄保留 | 最近 25 次 | 60 天 |
| 超時上限 | 30 秒 | 60 秒 |
| Server 位置 | 德國 | 美國 |

### cron-job.org 的限制（老實說）

- **沒有 uptime % 統計圖** — 只知道每次執行是否成功，不會幫你算「本月活了 99.2%」
- **沒有公開狀態頁** — 想對外放 `status.你的app.com` 給客戶看的話做不到
- **告警管道只有 email** — 想接 Slack / Discord / LINE 要付費
- **紀錄只保留 25 次** — 看不到一週前的狀況
- **UI 比較樸素** — 功能齊全但視覺停在 2010 年代

對個人工具站 keep-alive 來說，這些限制都不重要。未來需要向外展示可靠度時，兩邊可以**同時跑**（cron-job.org 當鬧鐘，UptimeRobot 當儀表板）。

### 設定步驟

1. 註冊 https://cron-job.org（免費，不用信用卡）
2. Dashboard → `Create cronjob`
   - **Title**：`DinoDashboard Keepalive`
   - **URL**：`https://你的app.onrender.com/ping`
   - **Schedule**：選 `Every 5 minutes`（或自訂 cron `*/5 * * * *`）
   - **Notifications**：勾 `Failure notification` 寄到你的 email
3. `Create`
4. 回 Dashboard，30 分鐘後看 Execution history — 應該會有 6 筆綠色 `OK`

### 驗證 keep-alive 真的有效

等到 cron-job.org 跑過幾次後：

1. 去 Render Dashboard → 你的 service → `Metrics` tab
2. 看 `Request count` — 應該每 5 分鐘有一根柱子
3. 看 `Service events` — 不應該再看到 `Service suspended due to inactivity`

---

## 後續維運

### 新增工具的截圖
直接從網頁 UI 上傳，會自動存到 Supabase Storage，DB 的 `screenshot` 欄位存 public URL。

### 新增 user
管理員登入 → `/admin/users` 頁面核准新註冊。

### 改資料
**不要改 `tools.yaml`**，那個檔已經不是資料源了（只是備份）。從網頁 UI 改，寫入會直接進 Supabase。

### 備份
Supabase Dashboard → `Database → Backups`，免費方案有每日備份保留 7 天。

### 其他免費 keep-alive 選項（備案）

如果哪天 cron-job.org 也不穩，這些都可以直接替補：

- **GitHub Actions cron**：repo 裡建 `.github/workflows/keepalive.yml` 排 `*/5 * * * *` 跑 `curl /ping`。免費額度每月 2000 分鐘用不到 1%
- **Cloudflare Workers Cron Triggers**：免費每天 10 萬次請求，最穩
- **Better Stack（原 Better Uptime）**：3 分鐘間隔 + 漂亮 UI，免費 10 個 monitor
- **UptimeRobot**：如果之後要 uptime % 統計和狀態頁，隨時可以加回來和 cron-job.org 並用

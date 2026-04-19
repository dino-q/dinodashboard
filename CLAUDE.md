# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DinoDashboard — 個人工具成果展示頁。展示所有自建工具的卡片/列表，提供啟動指令一鍵複製、多使用者權限管理、網站 / 本地 URL / 路徑 / 截圖。

## Tech Stack

- **Backend**: Flask + Jinja2，藍圖分層（`auth / main / api / admin`）
- **Frontend**: HTMX（server-side partial render）+ Lucide Icons (CDN) + 手寫 CSS（design tokens）
- **Data**: **Supabase** Postgres（5 張表：`tools / categories / users / env_types / quick_inputs`）+ Supabase Storage（截圖桶名 `screenshots`，public bucket）
- **Deploy**: Render（`render.yaml` Blueprint），cron-job.org 每 5 分鐘打 `/ping` 防 sleep
- **Python 3.13 必要**（`pyiceberg` 沒有 3.14 的 wheel）

`tools.yaml` 只是歷史備份，**不是資料源**。所有 CRUD 都走 Supabase，寫它不會影響線上。

## Commands

```powershell
# 本機開發
cd DinoDashboard
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py            # http://localhost:5050

# 從 tools.yaml + credentials.json 匯入 Supabase（一次性）
python supabase_db/migrate.py

# 本機掃描工具 path 自動補技術標籤
python scripts/auto_tag.py [--apply]
```

`.env` 必填：`SUPABASE_URL` / `SUPABASE_SECRET_KEY` / `FLASK_SECRET_KEY`；可選 `PRIVATE_MODE` / `ALLOW_REGISTRATION`。Render 上透過環境變數注入。詳細部署流程看 `DEPLOY.md`。

## 架構要點（需要讀多個檔案才能看懂的部分）

### 資料流
`tools.yaml`（歷史）→ `supabase_db/migrate.py`（一次性匯入）→ Supabase DB。運行時 `data/tools.py` 直接讀寫 Supabase，`tools.yaml` 不再被 app 讀取。

### 權限系統（`routes/auth.py`）
三種角色 `admin / editor / viewer`，用 `@login_required / @editor_required / @admin_required` 裝飾器；`app.py` 用 `@context_processor` 把 `is_admin / is_editor / is_viewer` 注入所有 Jinja 模板，模板用 `{% if is_editor %}` 切顯示。

### HTMX Partial 渲染模式
- 卡片刪 / star / filter → `hx-target="#tool-grid" hx-swap="innerHTML"` → 回 `partials/_tool_grid.html`
- OOB（out-of-band）更新：同個 response 還塞 `_featured_oob.html`、`_toc_oob.html` 同步 hero 區 & 側欄 TOC
- 編輯 modal 用 `partials/_tool_form.html`，提交後再 swap `#tool-grid`

### 頁面版型
首頁 `dashboard.html` 有個 `#snap-container`，前兩 section（`.site-hero` + `.featured-section`）是 `100dvh` snap pages；從 `.projects-section` 之後覆寫 `height: auto` 變成自由滾動。`dashboard.js` 自己寫 wheel handler 在 snap zone 攔截（不用原生 scroll-snap），在專案區放掉控制；scroll 位置橫跨 HTMX swap 會用 rAF lock ~240ms 防止 `scrollTop` 被拉回 0。

### Env Types / Quick Inputs 系統
- 每個工具的 launch command 有 `env` 欄（字串），指向 `env_types` 表的 `name`
- `DEFAULT_ENV_TYPES = ["local", "docker", "bat", "github", "Google Apps Script"]` **只在 DB 完全空時才 seed**（`load_env_types`），讓使用者刪掉的類型真的消失
- `load_env_types` 會掃所有 tools.commands 的 `env`，把「被用到但沒登記」的補回（orphan 防護）
- `_migrate_env_names` 是 lazy migration（每個 process 跑一次），把舊的 raw key 改掉（例：`gas` → `Google Apps Script`，同步改 `env_types` / `quick_inputs` / `tools.commands` jsonb）

### Hero 粒子球（`dashboard.js` 開頭）
Canvas 畫 3D 粒子球、跟隨滑鼠/觸控。桌機用「連續鄰近場」（`influence = (1 - distP/reach)^1.4`）；手機（`isMobile`）用「swarm churn」模型（每顆粒子有 lock / hold / cooldown 生命週期，同時鎖定上限 `N * 0.5`）。所有可調參數集中在該 IIFE 前段的常數區。

## 平台特定 CSS / JS

### `.is-ios` class（WebKit-mobile 專屬修正）
`dashboard.js` 開頭用 UA + `MacIntel + maxTouchPoints > 1` 偵測 iOS/iPadOS，貼 `.is-ios` 到 `<html>`。用這個 class 的 CSS 是 iOS-only 修正，**不要讓這些規則流入 Android/桌機**：
- `.is-ios .stat-rolling { height: 1.5em; }` — Inter-700 在 iOS 字身較高，1.2em 會切字
- `.is-ios .stat-item { align-items: flex-end; }` — iOS baseline 計算跟可見數字不對齊，改成 bottom align
- Rolling 動畫停點：iOS 路徑用 `getBoundingClientRect().height` 實量 px，其他平台維持 `translateY(-N*100%)`

修 iOS bug 之前先問「會不會影響 Android/桌機」。使用者多次強調：**好的地方不能動**。iOS-only 修正全部走 `.is-ios` 前綴或 `if (document.documentElement.classList.contains('is-ios'))` 分支。

### 登入後 scroll 重置
`scrollRestoration = 'manual'` + DOMContentLoaded / pageshow 強制 `scrollTop = 0`（除非 URL 有 hash）。iOS 會把上次 scroll 位置還原，加上 CSS scroll-snap 會卡在中間 snap page（精選區），必須手動重置。

## 常見陷阱

- **改 env 名稱不會 cascade 到舊工具的 commands**。使用者在 ⚡ 面板改名僅更新 `env_types` + `quick_inputs`，舊工具的 `commands[].env` 仍是舊值；`load_env_types` 的 orphan 防護會把舊名當作未登記的 env 補回來，看起來像「沒刪乾淨」。需要真的 rename 所有資料時用 lazy migration pattern（看 `_migrate_env_names`）。
- **截圖路徑**：新上傳存到 Supabase Storage (public URL 以 `https://...supabase.co/...` 開頭)；舊資料可能是 `screenshots/xxx.png` 相對路徑。模板用 `{% if screenshot.startswith('http') %}` 二選一。
- **Render 冷啟動** 30 秒以上，免費方案 15 分鐘無流量會 sleep。cron-job.org 每 5 分鐘打 `/ping` 防 sleep。
- **密碼設定檔 `.flask_secret`** 是本機 dev 用（git ignore），Render 上走 `FLASK_SECRET_KEY` 環境變數。沒設環境變數會每次重啟隨機，session 會失效。

## 設計系統

Dark mode first（Slate-900 + Indigo accent），Light mode 透過 `data-theme="light"` 切；全域 design tokens 在 CSS 頂端 `:root { --primary / --text / --border / ... }`，8px spacing grid，Lucide SVG icons（不用 emoji）。

# DinoDashboard — 功能與外部依賴說明

本檔案記錄每個需要「呼叫外部服務」或「掃描本機」的功能，以及部署時該注意什麼。

---

## 🔍 掃描本機技術標籤（Auto-Tag）

**位置**：filter-bar 篩選選單最下方「**掃描本機技術標籤 / Scan local tech tags**」按鈕（登入才顯示）

**觸發方式**

| 方式 | 指令 / 操作 |
|---|---|
| UI 按鈕 | 點篩選圖示 → 下拉選單 → 底部按鈕 |
| HTTP 端點 | `POST /api/auto-tag`（`@login_required`） |
| 命令列（CLI） | `python scripts/auto_tag.py [--apply]` |

**運作原理**

讀取每個工具的 `path` 欄位，把 Windows 路徑（`C:\Users\AG_Di\Desktop\automation\Claude_code\automatic_evolution\...`）對應到本機 `/app/...`，進入該資料夾掃描：

1. **Marker files**：`package.json`、`requirements.txt`、`Dockerfile`、`tsconfig.json`、`vite.config.*`、`tailwind.config.*`、`appsscript.json` 等
2. **副檔名統計**（最深 2 層）：`.py` / `.ts` / `.tsx` / `.js` / `.gs` / `.bat` / `.ps1` / `.sh` / `.html`
3. **`package.json` 依賴解析**：react / vue / svelte / next / vite / tailwind / express / puppeteer / playwright 等
4. **`requirements.txt` 關鍵字匹配**：flask / django / fastapi / htmx / pyautogui / openai / anthropic 等
5. **`.py` 檔 import 掃描**：`from flask`、`import pyautogui`、`from playwright.*` 等
6. **HTML 檔內容掃描**：htmx 字樣

偵測到的標籤**合併**進該工具既有 tags（不重複、不覆蓋原本自定標籤）。

**外部 API 依賴**
- ❌ **無** — 完全是本機檔案 I/O，零網路請求

**部署注意事項**
- 若 `tool.path` 在部署的伺服器上不存在（例如 cloud 機器不會有你的 Windows 路徑），該工具會被 gracefully skip（回傳 `status: "skipped", reason: "path unreachable"`），不會噴錯
- 只有自己 dev 機器跑 dashboard 才會真的掃到檔案；部署後此按鈕仍可點，只是會顯示「所有工具標籤已是最新」（沒掃到任何東西）

**程式碼位置**
```
data/auto_tag.py          ← 核心掃描邏輯
routes/api.py             ← POST /api/auto-tag 端點
templates/dashboard.html  ← filter menu 裡的觸發按鈕
scripts/auto_tag.py       ← CLI 包裝
```

---

## ✨ 自動建議英文名 & 標籤（Suggest）

**位置**：編輯 / 新增工具表單，中文名稱下方「**自動建議英文名稱 & 標籤**」按鈕

**運作原理**
1. 使用者填好中文名稱 / 說明
2. 呼叫 `POST /api/tool/suggest`
3. 後端做兩件事：
   - **中文名翻譯成英文** → 呼叫 [MyMemory Translation API](https://mymemory.translated.net/)（免費、無 key）
   - **關鍵字匹配**：用 `routes/api.py` 裡的 `_TECH_KEYWORDS` 字典掃描「中文名 + 說明」，匹配常見技術關鍵字（python、flask、docker、htmx、notion、line、爬蟲、AI、自動化 等）自動提議標籤

**外部 API 依賴**

| API | 用途 | 是否需要 key | 費用 |
|---|---|---|---|
| MyMemory Translation | 中翻英（工具名） | ❌ 不用 | 免費（每日 5000 字元匿名限額） |

- 網址：`https://api.mymemory.translated.net/get?q=...&langpair=zh-TW|en`
- Timeout：5 秒，失敗不阻塞（會跳過翻譯只回 tag 建議）
- **無需 Claude / OpenAI / Anthropic 等付費 API token**

**部署注意事項**
- 若伺服器無法連外（例如私有內網），翻譯功能會 timeout 但不會錯；標籤建議仍正常運作（那段是純在地關鍵字匹配）
- 想完全離線？可以從 `routes/api.py` 的 `_translate_zh_to_en` 改成 return `""`，整個功能退化成只建議標籤

---

## 🖼️ 圖示（Lucide Icons）

**來源**：CDN `https://unpkg.com/lucide@latest/dist/umd/lucide.min.js`

**用途**：所有 `<i data-lucide="icon-name">` 會被 JS 轉成 SVG

**外部依賴**：CDN 靜態檔（無 API、無 key）

**部署注意事項**
- 完全離線部署：下載 lucide 的 UMD 檔放進 `static/js/` 並改 `templates/base.html` 的 script src
- `@latest` 有版本漂移風險（lucide 會偶爾移除 brand icons 如 `github`），所以 GitHub 和 Notion 圖示已改用**內嵌 SVG**（`templates/partials/_icons.html` 的 `github_icon` / `notion_icon` macro），不依賴 lucide

---

## 🎨 字型（Google Fonts）

**來源**：`https://fonts.googleapis.com`（Inter、JetBrains Mono）

**外部依賴**：CDN（無 API、無 key）

**部署注意事項**：完全離線可自行下載字型檔 + 改 `base.html` 的 `@font-face` 設定

---

## 🌐 HTMX

**來源**：CDN `https://unpkg.com/htmx.org@2.0.4`

**外部依賴**：純前端 JS lib（無 API）

---

## 總結：這個 Dashboard 需要付費 API token 嗎？

### **完全不需要。**

- ❌ **無** Anthropic / Claude API
- ❌ **無** OpenAI
- ❌ **無** 任何需要登入的 LLM 服務
- ✅ 翻譯用免費 MyMemory（無 key）
- ✅ 圖示 / 字型 / htmx 走公開 CDN
- ✅ 核心資料處理、自動標籤、路徑掃描都是本機 Python + Flask

要**完全離線 / self-hosted 無外網**也能跑，只需下載：
1. Lucide UMD (`lucide.min.js`)
2. Inter + JetBrains Mono 字型檔
3. HTMX (`htmx.org@2.0.4`)

放到 `static/` 並改 `base.html` 的 `<script src>` / `<link href>` 即可。

# Design: 伺服器分頁 — 搜尋框與分類篩選整合成一排

## 任務意圖判定
- 屬於 ②「顧問」— 已有畫面（伺服器分頁）要對齊既有的專業版面（卡片分頁 `.filter-bar`）。
- 選用 skill：`ui-ux-pro-max`（Windows 主機端已補齊，直接 invoke 正版，未走 fallback）。
- 用途：確認整合順序、溢出策略、響應式收斂手法是否符合既有的可用性 checklist（觸控尺寸、對齊、間距系統），而不是憑感覺搬 DOM。

## 整體協調性檢視
- **退一步看整張畫面**：伺服器分頁原本是「搜尋框一排、分類 pill 另開一排（`flex-wrap: wrap` 自動換行）」，跟同一個 `#projects` 區塊裡「卡片」分頁的單排 `.filter-bar` 語彙不一致 —— 使用者在同一個頁面內切換兩個分頁，體感是兩套不同的篩選 UI。這正是 Dino 抱怨「不協調」的來源。
- **這次是「順手重排」不是「硬塞」**：搜尋框與分類 pill 兩塊 DOM 直接合併進同一個新容器 `.server-filter-bar`，重新分配了空間分配邏輯（pill 捲動槽吸收剩餘寬度、搜尋框固定寬度靠右），不是把舊的兩塊原封不動疊在一起。
- **沒有發現需要另外提案整合的按鍵**——伺服器分頁本身控制項不多（開關 / 預設 / 封存都在列內，不在這排篩選列上），這次只處理「搜尋＋分類」這一組，沒有動到其他按鈕、也沒有新增入口，不需要另外找 Dino 討論結構性變動。

## 設計決策

### 1. 這一排的排列順序：全部 pill → 分類捲動槽 → 溢出「⋯」→ 搜尋框（靠右、固定寬）
理由：**逐字對齊卡片分頁 `.filter-bar` 的既有順序**（見 `templates/dashboard.html` 150-315 行），而不是自創一套。分類篩選在使用流程上是「先縮小範圍」，搜尋是「範圍內找細節」，兩者互補、放同一排時分類理應在左（先看到有哪些類別）、搜尋在右（固定落點，使用者的眼睛/手指知道要去哪裡找）。這也是卡片分頁已經驗證過的動線，使用者已經有心智模型，伺服器分頁不需要重新發明。

### 2. Design tokens 全部沿用，不發明新值
- 分類 pill 樣式（padding `7px 16px`、字級 13px、圓角 `999px`、`active` 狀態＝`--surface-hover` 底 + `--primary` 邊框）直接照抄 `.filter-pill` 的數值與 token 用法，不再用舊版「filled primary 底色」的 `.server-filter-pill.active`（那是舊版自己發明的一套，跟卡片分頁不同語彙）。
- 捲動槽（`.server-filter-pills-scroll`）、溢出選單（`.server-filter-pills-more-*`）的間距、圓角（`var(--radius-sm)` / `var(--radius-md)`）、陰影（`var(--shadow-md)`）都直接照抄 `.filter-pills-scroll` / `.filter-pills-more-*` 的既有數值。
- 搜尋框 focus 狀態改用跟卡片分頁 `.search-input:focus` 一致的手法：`border-color: var(--primary)` + `box-shadow: 0 0 0 3px var(--primary-bg)` + 微幅展寬（原本伺服器搜尋框沒有 focus 展寬效果，也沒有 primary 光暈，現在對齊了）。
- **沒有沿用同一組 CSS class / JS 全域狀態**（沒有直接把 `.filter-pill`、`#filter-pills-more-wrap` 這些 id 原樣搬過來套用在伺服器分頁上）——因為卡片分頁與伺服器分頁的篩選列 DOM 在同一份頁面裡同時存在（只是用 `.show-server` / 一般狀態切換 `display`），若共用 id／class 加上 JS 用 `document.querySelector('.filter-pill')`／`getElementById('filter-pills-more-wrap')` 抓「第一個符合的節點」，兩邊的分類選取、溢出選單會互相打架。因此**視覺 token 完全共用，DOM 命名空間刻意分開**（`server-filter-bar` / `server-filter-pill` / `server-pills-more-wrap` / `server-pills-more-menu`），這是唯一的「不完全複製」之處，理由是避免狀態互相污染，不是偷懶另發明一套外觀。

### 3. 分類 pill 溢出策略：橫向捲動 + 「⋯」選單（比照卡片分頁）
- 新增 `.server-filter-pills-scroll` 容器包住每個分類 pill（原本用 `flex-wrap: wrap` 讓 pill 自動換行變成兩排以上，跟「整合成一排」的目標直接衝突）。
- 新增溢出選單 `#server-pills-more-wrap` / `#server-pills-more-menu`，複製卡片分頁「量實際捲動寬度、真的塞不下才顯示『⋯』」的判斷邏輯（`scroll.scrollWidth > scroll.clientWidth`），不是憑分類數量瞎猜一個門檻。
- JS 新增對應函式：`toggleServerFilterMore` / `closeServerFilterMore` / `pickServerCategoryFromMore` / `updateServerFilterPillsOverflow`，命名與行為對齊卡片分頁的 `toggleFilterMore` 系列，但各自綁定 `#server-view` 底下的節點，不共用選取器。
- 挑到分類後的高亮同步：`applyServerCategory()` 現在也會同步 `.server-filter-pills-more-item.active`，保證「⋯」選單裡的高亮跟捲動槽上的 pill 高亮一致（原本沒有這個同步，因為原本沒有溢出選單）。

### 4. 沒有動到搜尋行為
- `filterServerRows()` / `clearServerSearch()` / `applyServerSearch()` / `#server-search-input` / `#server-search-count` 全部原封不動，只調整了外層容器的 CSS（寬度、位置），沒有改任何函式簽名、id、hx-* 屬性。

### 5. 克制的地方
- 沒有幫伺服器分頁加卡片分頁才有的「篩選選單（sliders icon，狀態/has_external 等）」或「新增」按鈕——伺服器分頁的資料模型跟卡片不同（沒有 status / has_external 這些欄位可篩），硬加只會多出使用者用不到的入口，不符合「克制」的底線。
- 沒有把兩個分頁的 DOM／id 直接合併成同一份共用元件（雖然理論上可以做一個共用的「filter-bar with slot」元件），因為那屬於**結構性重構**，會動到卡片分頁既有穩定的程式碼與行為，風險與工作量都超出這次「整合搜尋框與分類到同一排」的範圍——如果 Dino 之後想要「兩個分頁篩選列共用同一套元件」，建議另外開一個任務評估，不在這次順手做。

## 產物位置
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\templates\partials\_server_list.html`（192-245 行：合併後的 `.server-filter-bar`）
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\css\dashboard.css`
  - 3279-3401 行：新的 `.server-filter-bar` / `.server-filter-pill` / `.server-filter-pills-scroll` / `.server-filter-pills-more-*`
  - 3436-3489 行：改寫後的 `.server-search`（固定寬度、focus 展寬、光暈）
  - 3550-3563 行：窄螢幕覆寫（`@media (max-width: 860px)`），比照卡片分頁 768px 覆寫的做法
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\js\dashboard.js`
  - `applyServerCategory()`：新增同步 `.server-filter-pills-more-item` 高亮
  - 新增 `toggleServerFilterMore` / `closeServerFilterMore` / `pickServerCategoryFromMore` / `updateServerFilterPillsOverflow`，以及對應的 outside-click / Escape / resize / DOMContentLoaded 監聽
  - `applyViewMode()`：切到伺服器分頁時補呼叫 `updateServerFilterPillsOverflow()`（分頁用 `display:none` 切換，切過去那一刻才量得到寬度）
  - `#server-view` 的 `htmx:afterSwap` 分支：重繪後也補呼叫一次 `updateServerFilterPillsOverflow()`

如何看：`python app.py` 起本機（`http://localhost:5050`），切到「伺服器」分頁即可看到新版一排式篩選列；縮小視窗到 860px 以下看窄螢幕收斂效果。

## 自審結果（web-design-guidelines 心法）
- **a11y**：分類 pill／溢出選單項目／搜尋框清除鈕都保留 `:focus-visible` outline（`2px solid var(--primary)`），溢出選單按鈕與搜尋清除鈕都有 `aria-label`；整排容器加了 `role="group" aria-label="搜尋與分類篩選"`。鍵盤 Tab 順序＝視覺順序（全部 → 分類 → 更多 → 搜尋），Escape 可關閉溢出選單。
- **狀態完整度**：hover / active / focus-visible 都補齊；搜尋框 focus 狀態新增了光暈與展寬（原本沒有），清除鈕沿用既有 `.has-query` 顯隱邏輯，沒有改動。
- **RWD**：≤860px 時分類 pill／捲動槽／溢出選單整組隱藏、搜尋框改滿版並移到第一順位（`order: -1`），行為對齊卡片分頁 768px 的既有覆寫模式；「全部」分類重置按鈕在窄螢幕上跟卡片分頁一樣不會出現——這是延續卡片分頁既有的已知取捨（窄螢幕靠 `<details>` 分類區塊本身瀏覽，不提供 pill 重置），不是這次新增的缺口。
- **對比**：pill 文字用 `var(--text-muted)` / `var(--text)`，跟既有 `.filter-pill` 對比策略一致，未動配色系統，沿用暗色模式既有對比已驗證過的組合。

## 後續建議
- 給 Bevis：這次只動視覺整合，沒有改變伺服器分頁的功能範圍，應該不影響產品方向判斷。
- 給 Ray：建議對「分類切換 + 搜尋同時使用」「切換卡片/伺服器分頁時分類高亮是否正確還原」「窄螢幕下\<details\>分組收合行為」跑一次 regression，因為這次改了分類 pill 高亮的同步邏輯（新增溢出選單同步）。
- 給 Andy：請記錄本次設計決策（伺服器分頁篩選列改版、對齊卡片分頁語彙、命名空間刻意分離的理由）。

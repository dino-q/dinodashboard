# Design: 伺服器分頁 — 拖曳掃過多選 ＋ 批次調整、封存連動提醒

## 任務意圖判定
- 屬於 ②「顧問」— 已有畫面（伺服器分頁）要加互動能力，且要融進既有版面，不是從零生成一頁。
- 選用 skill：`ui-ux-pro-max`（Windows 主機端正版，未走 fallback）。用途：批次操作/toast/確認提示的模式判斷（`--domain ux` 查過 Bulk Actions、Toast Notifications、Confirmation Messages 三類指引），對照「checkbox + 動作列」「toast 自動消失 3-5 秒」等既有共識，再依 Dino 的明確覆蓋指示調整（見下方「中途修正」）。

## ⚠️ 中途修正（務必記錄，避免下次重蹈）
第一版做了「每列一個 checkbox ＋ 表頭全選 checkbox ＋ 框選出一個矩形選取框」。Dino 看需求後直接推翻兩點：
1. **不要用 checkbox 表示選取狀態，改成整列換底色。**
2. **主要操作是「按住左鍵拖過去，一次掃過多列」，不是拉一個矩形選取框。**

於是整個重做：拿掉所有 `.server-select-box` / `.server-col-select` 新欄位、拿掉矩形 `.server-select-marquee`，改成「整列 `data-bat-key` ＋ `tabindex` ＋ 拖曳时按索引算範圍即時反白」。**教訓**：這類「互動範式」層級的東西（勾選框 vs 換色、矩形框選 vs 掃過）屬於核心操作手感，下次遇到「多選」需求，應該先用一句話問清楚「用勾選框還是整列反白」「是矩形框選還是掃過選取」，不要预設走最常見的 checkbox + marquee 模式就直接做兩三百行。

## 整體協調性檢視
- **退一步看整張畫面**：伺服器分頁目前的視覺語彙是「一列一個開關/勾選圖示（顯示、預設）＋ 右側一排小圖示按鈕（複製/本機/線上/封存）」，克制、沒有多餘裝飾。批次選取如果加一整欄新的 UI 元件（checkbox 欄），會讓每一列多一個「常駐但九成時間用不到」的視覺元素，這正是「為了塞新功能犧牲整體協調」的反例——所以最終版本刻意**不新增任何欄位**，選取狀態完全靠「整列變色」表達，沒有互動時列的長相跟改版前一模一樣。
- **批次操作列的位置與顯隱**：新增的 `.server-batch-bar` 插在「搜尋/分類篩選列」和「伺服器清單」之間，**平常 `hidden`、不佔版面**，只有真的選到東西才浮出、把清單往下推開——不是蓋在內容上面（見下方「不可用浮層」的落實）。
- **有沒有發現該整合的按鍵**：沒有。這次新增的是「批次動作」這個新的操作維度，跟既有的逐列操作（開關/封存按鈕）是互補關係，不是重複入口，不需要收斂既有控制項。

## 設計決策

### 1. 選取狀態＝整列換底色，不用 checkbox
- `.server-row.is-selected`：`border-color: var(--primary)` + `background: color-mix(in srgb, var(--primary) 10%, var(--surface))` + `box-shadow: inset 3px 0 0 var(--primary)`（左側一道色條，呼應「選取態」的常見語彙，同時避免只有背景微調在淺色模式下不夠明顯）。
- 沒有新增任何欄位、沒有動任何 `grid-template-columns`——只是在既有的 `.server-row` 上多切一個 class，橫向空間分配完全不變。
- 同時搭配 `aria-selected="true"/"false"`（原生 ARIA 選取狀態），螢幕報讀軟體念得到「已選取」，不是只有視覺變化。

### 2. 主要操作：按住滑鼠左鍵拖過去，即時反白，放開維持選取
- 實作在 `dashboard.js` 的 `serverSweepSelectSetup()` IIFE：`pointerdown` 記錄起點列的索引（`anchorIdx`），`pointermove` 即時算「起點到目前游標底下那一列」的索引範圍、整段套用選取，`pointerup` 結束。
- 拖曳範圍容器是 `.server-select-scope`（`#server-groups-scope` 涵蓋所有分類群組，可以跨分類一次掃到；封存區的 `.server-table-archived` 也有一份、獨立成另一個拖曳範圍）。
- 移動門檻 4px 才算「真的在拖」，單純點擊不會誤觸發拖曳邏輯。

### 3. 拖曳 vs 點一下開卡片詳情：怎麼區分
這是本次互動設計最容易出錯的地方，記錄清楚：
- 有卡片可開的列（`is-clickable`）：**單純點一下維持原行為（開詳情）**；一旦偵測到移動超過門檻（`dragMoved=true`），就在 `pointerup` 時設一個極短命的旗標 `window.__serverDragSuppressClick`，`serverRowOpen()`（既有函式，只加一行檢查）看到這個旗標就直接 return，不開 modal。旗標用 `setTimeout(...,0)` 在下一個 tick 就清掉，只擋這一次因拖曳觸發的 click，不影響後續正常點擊。
- 沒有卡片可開的列（手動新增的 bat、封存區的列）：本來單擊什麼都不會發生，這次讓單擊直接選取自己（清掉其他選取只選這一列）——沒有既有行為可搶，單擊自然變成「選取」的捷徑，不用非拖不可。
- **在互動元件裡拖曳，不能被當成整列拖曳選取**：開關、「預設」按鈕、改名稱/port 輸入框、複製/封存按鈕、本機/線上連結——`pointerdown` 一開始就用 `e.target.closest('input, button, a, select, textarea, form, [role="switch"]')` 排除，讓那些元件的原生行為（含在輸入框裡拖曳選字）不受影響。這點在「改名稱」小節有額外驗證（見下方）。

### 4. 批次操作列：不可用浮層蓋住內容
- `.server-batch-bar` 是**文件流裡的一般區塊**（沒有 `position: fixed/sticky/absolute`），從 `hidden` 變顯示時是把下面的分類清單「推開」一段距離，不是疊上去蓋住任何東西——沿用 Dino「討厭浮層蓋住內容，不是討厭固定本身」的既有偏好判準。
- **實測抓到的真 bug，記錄給下次參考**：一開始 `serverSelectSync()` 是「選取狀態＋批次列顯示」一次同步更新。拖曳選第一列的當下，批次列從 `hidden` 變成真的佔位，會把下面整份清單瞬間往下推幾十 px；如果拖曳邏輯每次 `pointermove` 都呼叫這個「全部同步」的函式，游標底下的列會在推移那一瞬間錯位（滑鼠沒動，但底下對到的列變了），選取範圍因此算錯。**修法**：拆成 `serverSelectSyncRows()`（只切列的反白）跟 `serverSelectSyncBar()`（只管批次列顯示/文字），拖曳過程中只呼叫前者，批次列的顯示/隱藏統一等 `pointerup`（`endDrag()`）那一刻才套用一次。單擊、鍵盤 Space 這些「瞬間完成」的操作沒有這個問題，繼續呼叫兩者都做的 `serverSelectSync()`。
- 六個動作（顯示／隱藏／設為預設／取消預設／封存／解除封存）用跟卡片分頁篩選 pill 一致的圓角按鈕語彙（`border-radius: 999px`），沒有另外發明危險色（封存不是破壞性操作，維持中性色，跟既有單列的封存按鈕語彙一致）。

### 5. 批次送出走既有的 `/api/server/batch`，用暫時 `<form>` 序列化
- 後端要 `bat_keys` 用同名多筆（`bat_keys=a&bat_keys=b`），`htmx.ajax` 的 `values` 物件選項不保證能產生重複欄位，所以改用一個不掛進畫面的暫時 `<form>`（塞多個同名 hidden input）當 `source`，交給 `htmx.ajax('POST', ..., {source: form, ...})` 序列化——這是原生表單多選提交的標準格式，不是自己另外編碼。

### 6. 封存連動提醒：擴充 toast，不是新蓋一個 modal
- 現有 `#toast-container` 只支援純文字（`toast.textContent = msg`）。這次新增 `showActionToast(msg, {confirmLabel, dismissLabel, onConfirm})`，用同一個容器（既有的、非遮擋的右下角位置）多產出一種「不自動消失、帶兩顆按鈕」的變體 `.toast.toast-action`。
- **為什麼不用 confirm() 或 modal**：這個提示不是「阻斷式的是非題」（不需要使用者立刻決定才能繼續操作，使用者可以完全忽略它、稍後這則提示自己被使用者按 X 關掉或乾脆放著），用跟既有系統一致的 toast 語彙比疊一個新的 modal 更輕、更不打斷操作節奏，也不會有 modal 遮住畫面其他內容的問題。
- **為什麼不自動消失**：一般成功訊息（例如「已改名」）3 秒消失沒關係，因為使用者不需要對它做任何決定；但這則是「要不要順便處理另一邊」的問題，使用者可能還在看畫面別的地方，3 秒內來不及反應就消失掉，等於這個功能形同虛設。所以 `.toast-action` 沒有 `setTimeout` 自動移除，只有按下「一起處理」或「不用，只改這邊」才會關掉。
- 兩個事件各自對應後端已經做好的兩支端點：
  - `askArchiveCard` → 按「一起封存卡片」呼叫 `POST /api/server/archive-card/<tool_id>`，`htmx.ajax` target `#server-view`（這個操作是從伺服器分頁發起的，回應也理所當然重繪伺服器分頁）。
  - `askArchiveServers` → 按「一起封存」呼叫 `POST /api/tool/<tool_id>/archive-servers`，`htmx.ajax` target `#tool-grid`（從卡片編輯表單發起，回應重繪卡片牆，含既有的 OOB 更新）。
- 沒有動 `routes/api.py` 的邏輯——確認過 `_card_link_prompt` / `_server_link_prompt` 已經在正確的路由（單列封存切換、卡片狀態更新）裡被呼叫、且刻意「只有狀態真的不一致才問」，批次動作（`/api/server/batch`）目前不會對每一列各自觸發詢問（避免一次封存 10 支 bat 跳 10 次提示的災難），這是後端既有設計，我沒有加也沒有動。

## 產物位置
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\templates\partials\_server_list.html`
  - `server_row` macro：新增 `data-bat-key` / `tabindex="0"` / `aria-selected`（只在 `is_editor` 才加）；「改名稱」輸入框從 `<form>` 包裹改成直接掛 `hx-trigger="blur changed"`（見下方獨立小節）
  - 批次操作列 `#server-batch-bar`、拖曳範圍容器 `#server-groups-scope.server-select-scope`
  - 封存區：`data-bat-key` / `tabindex` 加到 `.server-row-archived`
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\css\dashboard.css`
  - 檔案最後一段「伺服器分頁 — 拖曳掃過多選 ＋ 批次調整」：`.server-row[tabindex]` 游標／focus、`.server-row.is-selected`、`.server-batch-bar` 系列、`.toast.toast-action` 系列
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\js\dashboard.js`
  - `serverSelection` / `serverSelectSyncRows` / `serverSelectSyncBar` / `serverSelectSync` / `serverSelectClearAll` / `serverBatchAction`
  - `serverSweepSelectSetup()` IIFE（拖曳掃過邏輯）
  - 單擊委派（沒有卡片可開的列，單擊選取自己）／鍵盤委派（Space 選取、Enter 開詳情）
  - `serverRowOpen()` 加一行 drag-suppress 檢查
  - `showActionToast()` ／ `askArchiveCard` ／ `askArchiveServers` 事件監聽
  - 既有 `#server-view` 的 `htmx:afterSwap` 監聽補一行 `serverSelectClearAll()`（整塊重繪後選取狀態本來就會歸零，順手同步前端記憶體）

## 附帶修的小事：「改名稱」欄位改成 blur 自動存檔
- 現況是「只吃 form 的 submit（按 Enter）」，Dino 已經因為「改完點別的地方以為存到了，其實沒存」白改過一次。
- 改法：拿掉外層 `<form>`（避免 Enter 觸發瀏覽器原生表單送出、整頁跳轉），`hx-post`/`hx-target`/`hx-swap` 直接掛在 `<input>` 上，`hx-trigger="blur changed"`——**內容沒變就不送出**（`changed` 修飾詞比對值，滿足「點過去又點開不要每次都打 API」）。
- Enter 鍵透過 `onkeydown` 呼叫 `this.blur()`，統一走同一個 `blur changed` 觸發器，不另外疊加 `keyup[key=='Enter']`，避免同一次按鍵在部分瀏覽器下兩邊都各自觸發、送出兩次請求。
- 存檔成功的回饋沿用後端既有的 `_server_response(toast_msg=...)` → `showToast`，沒有另外疊加浮層或變色提示（`title` 提示文字已經同步改成準確的說法）。
- **跟拖曳選取的互動要點**：這個欄位在 `.server-select-scope` 範圍內，`pointerdown` 排除清單已經包含 `input`，在輸入框裡按住拖曳是選取文字，不會被誤判成整列拖曳選取（已用模擬測試驗證，見下方）。

## 自審結果（④ 心法）
- **a11y**：選取完全靠原生語意達成鍵盤可操作——列本身 `tabindex="0"` + `aria-selected`，Tab 走到列上按 Space 切換選取、Enter 開詳情（若該列可開），不依賴滑鼠拖曳這種天生只有滑鼠才做得到的手勢。拖曳掃過本身**沒有**鍵盤等價操作（這是合理限制，跟檔案總管的滑鼠框選一樣，鍵盤使用者改用 Tab+Space 逐列勾一樣能達到同樣結果，只是操作方式不同，不是功能被閹割）。批次操作列有 `role="toolbar"` / `aria-label`，動作按鈕都是原生 `<button>`。
- **狀態完整度**：選取態（換色＋色條）、hover、focus-visible（inset outline）、批次列 hidden/顯示都有涵蓋；封存連動提示用不自動消失的 toast 明確表達「需要你決定」的狀態，跟一般成功訊息的 3 秒消失做出區隔。
- **RWD**：主要拖曳互動本質上是滑鼠專屬手勢，`pointerdown` 明確排除 `pointerType==='touch'`——觸控裝置（含手機/平板）一律回退成「單擊選取單列」＋鍵盤 Space（若外接鍵盤），沒有另外做觸控版的框選手勢，理由：觸控的拖曳手勢本來就是用來捲動頁面的，硬要疊加拖曳選取只會跟捲動衝突，這是設計上刻意的取捨，不是遺漏。批次操作列與其按鈕在窄螢幕下改直式排列（`flex-direction: column`），不會擠壓或橫向溢出。
- **對比**：選取態的文字顏色沿用 `--text`（未改變），只調整背景與邊框，不影響文字對比度；沒有引入新的低對比配色。

## 自我除錯記錄（給下次做類似拖曳互動的人）
用 Playwright 對著真實載入的 `dashboard.js` + 模擬的 editor DOM 做行為驗證時（沒有 Dino 的登入帳密，無法用真的 editor session 互動，改用「載入真頁面＋真 JS，然後用 `page.evaluate()` 把 `#server-view` 換成 is_editor 模式會產生的真實 DOM 結構」這個折衷方式，完全不觸發任何後端寫入 API），抓到兩個必須修的真 bug：
1. **拖曳中途更新批次列顯示，會導致清單版面位移、選取範圍算錯**（見上方「批次操作列」小節）——這是這次測試抓到最重要的一個問題，純靠人眼看很難注意到（因為手速夠快時視覺上幾乎同時發生），要拆解成一步一步的座標紀錄才看得出來。
2. 拖曳時應該防止瀏覽器原生的文字選取手勢介入（`e.preventDefault()` 在 `pointerdown`、`document.body.style.userSelect='none'` 在確認開始拖曳時），否則長時間拖曳有機率跟文字選取搶焦點。

## 後續建議（第一版，2026-09-15 上午）
- 給 Bevis：這個設計符合「伺服器」分頁作為個人 CLI 管理工具的定位，批次調整跟封存連動都是效率型功能，沒有偏離產品方向。
- 給 Ray：**強烈建議用有 editor 權限的帳號做一次真人互動 regression**——這次的驗證受限於沒有登入憑證，用「模擬 fake DOM＋真實 JS」的方式驗證了拖曳範圍計算、拖曳與點擊的區分、鍵盤 Space/Enter、輸入框內拖曳不誤觸，但沒有機會在**真正的 `_server_list.html` 渲染結果**（含真實 CSS grid 欄寬、真實資料筆數、可能上百列的效能）上跑過，也沒有機會實際按下六個批次動作按鈕、實際觸發 `askArchiveCard`/`askArchiveServers` 兩個事件走一次真的後端流程。建議至少跑一次：登入 editor →拖曳選 3-5 列 → 按「隱藏」→ 確認清單正確重繪且選取歸零 → 找一支卡片來源的 bat 做單列封存 → 確認封存連動 toast 正確跳出且按鈕能動作。
- 給 Andy：請記錄這次設計決策，特別是「checkbox 改整列換色、矩形框選改拖曳掃過」這個中途需求修正，以及「批次列顯示時機要延後到 pointerup，否則會在拖曳中造成版面位移」這個踩雷經驗，供之後其他頁面做類似的多選/拖曳互動時參考。

---

# 2026-09-15 退件重做：選取視覺「太 AI 了」＋兩個互動缺口＋批次列改固定貼底

Dino 退回上面第一版，原話：「旁邊空白處也要可以拖曳選取，然後這個選取設計太AI了，要改，另外再選一次要能取消」。處理到一半又追加：「選取列放底部，要能一直在畫面上；然後可以按著Shift加選，或是減少一個」。這一節記錄第二輪的完整重做。

## 任務意圖判定
- 屬於 ②「顧問」——已經有能動的功能，這次是把互動細節補齊、把視覺從「堆疊出來的樣板感」改成有克制的專業感，不是從零生成新頁面。
- 開工前依 Dino 的硬性要求，先用 Skill 工具載入 `frontend-design`（避免 generic AI aesthetic 的方法論）與 `ui-ux-pro-max`（用 `scripts/search.py` 查了 `ux` domain 的「row selected state」「selection state color emphasis restraint」，資料庫沒有命中「選取態視覺克制」這麼細的規則，屬於一般設計判斷，改依「一次只做好一個訊號」的方法論原則自行決策，沒有假造搜尋結果）。都是 Windows 主機端正版，沒有走 fallback。

## 整體協調性檢視
- **退一步看整張畫面**：伺服器分頁原本已經有三種列狀態語彙（hover 中性灰、is-hidden-row 虛線淡出、server-row-archived opacity 稀釋），這次新增選取態，最大的風險就是「疊出第四種語彙後,四種混在一起分不清楚」。所以選取態刻意只動一個維度（背景色相＋亮度），跟另外三種各自獨立的維度（中性灰 vs 虛線邊框 vs 整體透明度）不會互相蓋掉，四種同時出現（測試腳本第 1、10 項有實際疊加驗證：隱藏+選取、封存+選取）看起來仍然分得清楚。
- **批次列從文件流改固定貼底,是不是走回「浮層蓋內容」的老路？** 不是。Dino 的規則講的是「討厭遮擋，不是討厭固定」（2026-06-16 罵過壓住內容的 sticky 導覽列，2026-09-02 又主動要固定的浮動書籤）。這次做法是「固定 + 主動讓出空間」：JS 量出批次列實際高度，即時把 `#server-view` 的 `padding-bottom` 加大等量，捲到最底時批次列底下對到的是特地留出來的空白，不是任何一列。驗收腳本第 11 項用 Dino 指定的方式驗證（`document.elementFromPoint()` 對最後一列取樣，斷言接到的不是批次列），不是隨口斷言「零 fixed」。
- **有沒有發現該整合的按鍵/入口？** 沒有新發現。批次列本身的六個動作、清除按鈕維持原樣，只動了「這條列怎麼定位」與「列怎麼顯示選取」兩件事，沒有新增或砍掉任何操作入口。

## 設計決策

### 1. 選取視覺：只留一個訊號——整列底色的明度/彩度位移
**退件原因診斷**：舊版是「邊框變色（border-color: primary）＋淡底（10% 混色）＋左側色條（inset box-shadow）」三件套同時做在同一個狀態上。這正是 Dino 說的「一看就是 AI 生的」——三個訊號各打五折，比一個訊號打滿分還廉價。

**新做法**：
```css
.server-row.is-selected { background: color-mix(in srgb, var(--primary) 16%, var(--surface)); }
.server-row.is-selected:hover { background: color-mix(in srgb, var(--primary) 22%, var(--surface)); }
```
只換整列底色，border-color 完全不動（未選取列本來的 `--border` 中性灰邊框，選取後還是它）。深色模式下 primary(#818CF8) 比 surface(#18181B) 亮非常多，混色同時墊高了整列的亮度，不是只換色相，色盲/低視力使用者也能靠亮度差異分辨；每一列另外有 `aria-selected`，不依賴任何視覺訊號。

**刻意沒用的（克制清單）**：
- ❌ 對比色邊框——邊框維持中性，不再讓選取態多一個「描邊」的視覺重量
- ❌ 左側色條 / box-shadow 裝飾——這是最典型的「儀表板套件感」來源，直接拿掉
- ❌ 讓其他未選取的列同步變暗退場——想過這個方向（讓選取的列相對浮出來），但這頁已經有兩種「變暗/變淡」的語彙（is-hidden-row 虛線、server-row-archived opacity），如果選取又加第三種「未選取的列集體變暗」，反而會讓使用者分不出「這行是暗色因為沒被選到」還是「暗色因為被隱藏/封存」。一個頁面三套淡化邏輯互相打架，比一個清楚的「被選到=亮」訊號更亂，所以放棄。
- ❌ checkbox——Dino 已經在第一輪明確否決過，不重提。

**跟既有三種列狀態的相容性**（實測見驗收腳本）：
| 疊加組合 | 表現 | 分得清楚嗎 |
|---|---|---|
| 選取 + is-hidden-row（隱藏） | 虛線邊框保留，底色蓋上選取色 | 分得清楚——虛線是「隱藏」的訊號，底色是「選取」的訊號，兩個維度沒有衝突 |
| 選取 + server-row-archived（封存） | opacity 稀釋整列，選取色在稀釋後的版本上疊加 | 分得清楚——opacity 是封存專屬語彙，色相變化是選取專屬語彙 |
| 選取 + is-clickable（可開卡片） | 底色變化 + hover 時卡片圖示浮現，兩者互不干擾 | 分得清楚 |
| 選取 + hover | hover 原本是中性灰 `--surface-hover`，選取是有彩度的 primary 底色，`.server-row.is-selected:hover` 用色相區分，不會被 hover 蓋掉變回中性灰 | 分得清楚 |

### 2. 空白處也能起拖
**問題**：舊版 `pointerdown` 一定要 `e.target.closest('.server-row[data-bat-key]')` 抓到列才會設定拖曳錨點，壓在列與列的間隙（`.server-table` 的 flex gap）、分類群組之間的間隙（`.server-group` 的 margin-bottom）都會直接被判定「沒有起點」而整個放棄。

**做法**：`pointerdown` 不再要求一定要壓在列上，只要還在 `.server-select-scope` 範圍內、不是互動元件、也不是 `<summary>`（分類標題本身要保留原生展開/收合，不能被拖曳搶走），就開始一次「待定」的拖曳；錨點（anchorIdx）留白，等 `pointermove` 真的碰到第一列時才決定錨點是哪一列——也就是說，不管你的滑鼠是從哪個空白角落按下去的，真正決定「選取從哪裡開始」的，是你的滑鼠拖曳路徑上**第一個碰到的列**。這個做法自然涵蓋 Dino 講的「群組與群組之間的空隙、分類標題下方」——凡是在 scope 容器範圍內的空白，都能起拖。

**沒有處理的邊界**：頁面級的左右留白（`.server-view` 外層容器的水平 padding）目前不在 `.server-select-scope` 範圍內，因為這頁的列本身就是 `.server-table`（flex column，子項預設 stretch）撐滿整個 scope 容器寬度，scope 容器本身沒有額外的水平留白可以利用。若之後外層版面改版、side 留出可視空白，同一套「只要在 scope 內、非互動元件」的判斷邏輯會自動涵蓋，不需要為了這句話而現在就動版面寬度。

### 3. 再選一次要能取消 ＋ Shift 加選/減選：統一成一套原則
把「再選一次取消」「Shift 加選/減選」「原本的點擊開卡片」「拖曳」四種手勢放在一起想，歸納成一條原則：

> **沒有 Shift（點擊、拖曳）＝「開一個全新的選取」，取代舊選取；有 Shift（Shift+點擊、Shift+拖曳）＝「調整」，保留舊選取，只動這一個/這一段。**

四種手勢對照表：

| 手勢 | 目標列狀態 | 結果 |
|---|---|---|
| 純點擊 | 未選取、**可開卡片**（is-clickable） | 開卡片詳情（原本行為，不變） |
| 純點擊 | **已選取**（不論可不可開卡片） | 取消這一列的選取，不開卡片（「再選一次要能取消」） |
| 純點擊 | 未選取、**不可開卡片** | 換成只選這一列，清掉其他既有選取（沿用第一版就有的「單擊即選」捷徑，跟純拖曳一樣是「開新選取」） |
| 純拖曳 | （範圍內的列） | 清掉舊選取，重新框出這次掃過的範圍（跟原本一致，沒有改） |
| Shift + 點擊 | 任一列 | 只切換這一列（已選取→移除／未選取→加入），完全不影響其他已選的列 |
| Shift + 拖曳 | （範圍內的列） | 把這次掃過的範圍「加」到拖曳前既有的選取上，不清掉拖曳前選好的列 |
| 鍵盤 Space | 任一列（Tab 到焦點） | 切換這一列，跟 Shift+點擊同一套「只動這一個」原則 |
| 鍵盤 Enter | is-clickable 列 | 呼叫 `row.click()`，走跟滑鼠點擊完全一樣的規則——**已選取的列按 Enter 一樣是取消選取、不開卡片**，這是刻意的一致性選擇，不是遺漏（想開卡片的話，先按 Space 取消選取，再按 Enter） |

**「已選取的列點擊＝取消」跟「原本點開卡片」的衝突怎麼分**：按 Dino 自己在需求裡給的方向定案——已選取狀態下點擊＝取消，未選取狀態下點擊＝開卡片。實作上 `serverRowOpen()`（is-clickable 列的 inline onclick）在真的要打 API 開卡片之前，先檢查 `ev.shiftKey` 跟 `serverSelection.has(key)`，符合任一個就直接處理選取、`return`，完全不會執行到後面的 `htmx.ajax(...)`。

**Shift+拖曳要不要做成整段加選？── 做了，理由**：跟上面的統一原則一致（Shift＝保留舊選取），使用者按住 Shift 拖曳掃過另一群列，直覺預期是「這群也加進去」而不是「取代掉我剛才選的」。實作是在 `pointerdown` 記一份 `preSelection`（拖曳前的既有選取快照），拖曳過程中 `applyRange()` 每次都是「清空→放回 preSelection→再放進這次掃過的範圍」，達成加選效果且不會把 preSelection 以外原本沒選的列誤加進來。

**拖曳掃過「已經被選取」的列時的行為──選了哪一種**：純拖曳（無 Shift）採用「整段重置成這次掃過的範圍」，不是「依起點列狀態決定整段加或減」。原因：後者（類似 Windows 檔案總管 Ctrl+拖曳的逐格反轉）在只有 4 支 bat 到幾十支 bat 的清單規模上是過度設計——使用者很難在拖曳當下記住「這幾格是加、那幾格是減」的中途狀態，「重置成掃過的範圍」則是所見即所得、拖到哪就選到哪，唯一在乎「保留舊選取」的情境（Shift+拖曳）已經有獨立的加選機制涵蓋，不需要在無 Shift 的情況下也做複雜的逐格判斷。

### 4. 批次操作列改成固定貼底，但不遮擋內容
第三輪追加需求：選取列要放底部、捲動時一直在畫面上。這乍看跟原本「批次列放文件流裡、不要浮層」的決定衝突，但 Dino 講清楚了界線：**討厭的是遮擋，不是固定本身**。

**做法**：
- `.server-batch-bar` 改 `position: fixed; left:50%; bottom:16px; transform:translateX(-50%)`，寬度跟著 `.section-inner` 同一個 `max-width: var(--container)` 邏輯置中，不是貼齊視窗邊緣的全寬工具列（維持這頁一直以來「內容置中、留白呼吸」的版面語彙，不要因為固定就變成一條頂到底的系統列）。
- 出現時用 `updateServerBatchBarSpacing()`（`dashboard.js`）量出這條列的實際渲染高度（`getBoundingClientRect().height`，含窄螢幕變直式排列後變高的情況），直接把 `#server-view` 的 inline `paddingBottom` 加大同樣的高度（`calc(48px + Npx + 16px)`）。用 inline style 而不是疊一條 CSS 規則，是刻意避開跟既有 `.projects-section.show-server .server-view { padding-bottom: 48px; }` 比選擇器優先權（那條有 3 個 class，我原本想疊的規則優先權不夠高，會被蓋掉）——inline style 保證生效，收起來時設回空字串也保證乾淨歸零，不會留一塊多餘空白。
- 視窗尺寸變化（例如窄螢幕觸發直式排列、高度變高）時，只要批次列還顯示中，`resize` 監聽會重新量一次高度，維持底部留白跟實際高度同步。
- 批次列出現時同步隱藏（`opacity:0; pointer-events:none`）右下角的「回到頂端」圓形按鈕——兩者的可視範圍在窄螢幕會疊在一起，批次列本身有取消選取按鈕，回頂端此時不是非用不可的功能，選取一結束自動恢復。
- z-index 排在 back-to-top（90）之上、toast（200）與 modal（100/300）之下，符合既有的浮動元素堆疊順序，沒有另外發明一套規則。

**驗收方式照 Dino 的規定寫**：不是斷言「頁面上沒有 fixed 元素」，而是「fixed 元素不能遮擋內容」——對畫面上最後一列的底部取樣一個點，`document.elementFromPoint()` 拿到的元素不能是批次列本身或它的子節點。腳本另外驗證：批次列出現時 `#server-view` 的 padding-bottom 不是空字串（真的留了空間）、取消選取後 padding-bottom 收回空字串（沒有留下一塊永久空白）。

## 產物位置
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\templates\partials\_server_list.html`
  - 批次列的說明註解更新（文件流 → 固定貼底 + 讓出空間）
  - 拖曳範圍容器的說明註解更新（空白處起拖）
  - **DOM 結構本身沒有變動**（沒加欄位、沒加 checkbox）
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\css\dashboard.css`
  - `:root` 新增 `--server-batch-bar-h` 變數
  - `.server-row.is-selected` / `:hover`：改成單一訊號（背景色相/亮度位移）
  - `.server-batch-bar`：改成 `position: fixed` 貼底置中，含窄螢幕媒體查詢調整寬度與底部間距
  - 新增 `body.has-server-batch-bar .back-to-top.visible`：批次列出現時讓路
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\js\dashboard.js`
  - `serverSelectSyncBar()` 補一行呼叫 `updateServerBatchBarSpacing()`
  - 新增 `updateServerBatchBarSpacing()`：量測批次列高度、切換 `body.has-server-batch-bar`、設定 `#server-view` inline padding-bottom
  - 新增一段 `resize` 監聽（debounce 120ms），批次列顯示中才重新量測
  - `serverSweepSelectSetup()` IIFE：`pointerdown` 不再要求一定壓在列上；新增 `dragShift` / `preSelection`，`applyRange()` 支援 Shift+拖曳的加選語意；`pointermove` 補上「起點在空白處時，等碰到第一列才決定錨點」的邏輯
  - 「沒有卡片可開的列」的 `click` 委派：改成 Shift 切換 / 已選取取消 / 未選取才清空重選 三分支
  - `serverRowOpen()`：新增選取相關的 Shift / 取消判斷，早於開卡片的 `htmx.ajax` 呼叫之前 return

## 自審結果（④ 心法）
- **a11y**：`aria-selected` 維持不依賴視覺訊號；選取態的亮度變化本身也不是純色相判斷（primary 比 surface 亮很多），色盲/低視力使用者仍可靠亮度差異辨識；Shift+點擊、Space 都是鍵盤可達的等價操作，拖曳（含 Shift+拖曳）本身沒有鍵盤等價操作，這點跟第一版一致、是合理限制，鍵盤使用者改用 Tab+Space 逐列切換一樣能達到同樣結果。
- **狀態完整度**：選取／隱藏／封存／可開卡片 四種狀態的兩兩疊加都各自測過（驗收腳本第 1、10 項），視覺上分得清楚；批次列本身的 hover/focus-visible 沒有改動。
- **RWD**：批次列窄螢幕（≤640px）維持直式排列，寬度改用 `calc(100% - 24px)`、`bottom: 12px`，`resize` 監聽確保切換斷點時底部留白高度同步更新，不會出現「批次列變高了但留白沒跟著變高、蓋住最後一列」的情況。
- **對比**：選取態的文字顏色沿用 `var(--text)` 沒有變動；背景混色最高只到 22%（hover 態），深色/淺色模式下都還在同一個色相家族內做亮度位移，沒有引入新的低對比配色。

## 後續建議（第二版，2026-09-15 追加修訂）
- 給 Bevis：選取視覺這次改成「只做一個訊號」，是往「克制」的方向收斂，符合這頁一路以來「資訊密度高但裝飾少」的調性，沒有偏離產品方向。
- 給 Ray：**驗收腳本已經把「空白處起拖」「再選一次取消」「Shift 加選/減選」「批次列固定貼底不遮擋」「四種列狀態疊加」都補進去且全數通過（21 項斷言）**，但一樣受限於沒有真的 editor session，建議用有權限的帳號至少跑一次：Shift+點擊連續選幾支 bat → 確認批次列一直在底部看得到、往下捲到清單最後一列 → 確認最後一列完整露出、沒被批次列蓋住 → 按「隱藏」→ 確認清單重繪後選取正確歸零、批次列跟著收起、`#server-view` 的留白也跟著收回去。
- 給 Andy：這次退件的核心教訓值得記一筆——「選取態同時做邊框＋淡底＋色條」是 AI 生成 UI 最容易掉進去的樣板陷阱，克制的做法是先問「這個狀態最少可以只靠一個訊號表達嗎」，答案通常是可以的；另外「固定 vs 遮擋是兩件事」這個判準（2026-06-16 反對過的是遮擋、不是固定）這次又用上一次，值得跟 `feedback_no_floating_sticky_overlay.md` 放在一起參照。

---

# 2026-09-15 第四輪：選取底色加強 ＋ Shift 多選模式 ＋ 說明文字斷行/配色統一

Dino 試用第二版後回饋兩點：「AI味消除了，但選取後底色不夠顯眼；然後我希望按著Shift的時候，就知道我是要多選了，不要再讓我點到修改名稱，很容易誤觸」。處理過程中又追加了同一段說明文字的兩個小問題（斷行位置、粗體字顏色跟內文不一致）。**設計方向本身（單訊號換色、拖曳掃過、批次列固定貼底）Dino 已經認可，這輪不推翻重做，只處理回饋的具體問題。**

## 任務意圖判定
- 屬於 ②「顧問」——已認可的設計方向做強度調整＋補一個互動細節，不是重新設計。
- 開工前依硬性要求載入 `frontend-design` 與 `ui-ux-pro-max`（Windows 主機端正版，沒有走 fallback）。用 `ui-ux-pro-max` 的 `search.py` 查過 `"selected row list background contrast emphasis" --domain ux`，資料庫沒有「選取底色該混多少 %」這種精確數值指引，只確認了「4.5:1 是文字對比的硬門檻」這條通用規則（Result 1），其餘強度/配色判斷屬於一般設計判斷，沒有假造搜尋結果。

## 整體協調性檢視
- **退一步看整張畫面**：這輪動到的三件事——選取底色、Shift 多選的視覺提示、說明文字——分別影響「列的狀態語彙」「使用者操作時的即時回饋」「頁面頂部的靜態說明」，三者互不重疊，也都沒有新增任何常駐 UI 元素（沒加圖示、沒加文字提示區塊），符合「加強不加料」的原則。
- **選取底色加強會不會破壞跟其他三種列狀態的區隔？** 這是本輪最大的風險點，已在下面「疊加狀態」小節逐一算過對比、並用 Playwright 的 canvas rasterize 實測驗證（不是憑印象）。結論：加強後四種狀態兩兩之間的區隔沒有變模糊，反而因為選取訊號更強，跟另外三種（中性灰 hover、虛線淡出、opacity 稀釋）的色相/亮度落差更清楚。
- **Shift 多選模式要不要疊加第二個視覺訊號（例如同時做游標＋外框）？** 判斷後只留游標一個訊號（見下方設計決策 2），沒有額外加外框/背景色，維持「一個狀態只用一個訊號」的既有原則，不因為這是「模式」而不是「單列狀態」就放寬標準。
- **有沒有發現該整合的按鍵/入口？** 沒有。這輪都是既有機制的強度/細節調整，沒有新增或砍掉任何操作入口。

## 設計決策

### 1. 選取底色加強：同一個訊號，強度加倍（16%/22% → 32%/40%）
Dino 的原話是「不夠顯眼」，不是「訊號不對」——所以不改變「整列換底色」這個唯一訊號的性質，只把強度拉高，同時處理另外兩個他點名的疊加場景。

**數值與實測**（`static/css/dashboard.css` 的 `.server-row.is-selected` 區塊）：
```css
.server-row.is-selected { background: color-mix(in srgb, var(--primary) 32%, var(--surface)); }
.server-row.is-selected:hover { background: color-mix(in srgb, var(--primary) 40%, var(--surface)); }
```
用 Playwright 把 computed `backgroundColor` rasterize 成實際 RGB（見下方「自審」的驗收方式）量到：深色模式一般列 `rgb(24,24,27)` → 選取後 `rgb(63,67,108)`，色差總和 163（原本 16% 換算約 71，加強後超過兩倍）；門檻設在「差異須 > 90」才算「真的跳出來」，實測遠超過門檻。

**為什麼不換訊號種類，只調強度**：Dino 明確說「AI味消除了」，代表「整列換底色、不疊邊框/色條」這個方向本身沒問題，問題純粹是「這個底色不夠濃」。如果這次又多加一個訊號（哪怕只是加深邊框或加一點陰影），等於是把已經被認可、走過一輪痛苦重做才拿掉的三件套又偷偷加回來一部分——所以刻意守住「只調同一個變數的數值」這條線。

### 2. 疊加狀態要分開處理，不能只靠「加強底色」一次解決
Dino 特別點名兩個疊加場景「都要顯眼」，逐一拆解原因、各自對症下藥：

**已隱藏＋選取**：CSS 特異度上 `.server-row.is-selected`（後宣告）本來就會贏過 `.server-row.is-hidden-row`（先宣告），兩者特異度相同、背景色數值其實跟「一般列選取」完全一樣——但「看起來比較不顯眼」的真正原因不是背景色被稀釋，而是這一列同時背著虛線框＋`--text-muted` 淡字兩個「已隱藏」訊號，文字視覺上仍然偏暗，讓整列讀起來還是「暗的」。算過 WCAG 對比：`--text-muted` 疊在新的 32% 選取底色上，深色模式只剩約 2.3:1、淺色模式更低，**低於 AA 的 4.5:1**，這是文字對比的真問題，不是背景強度問題。
```css
.server-row.is-hidden-row.is-selected .server-name-input,
.server-row.is-hidden-row.is-selected .server-col-name,
.server-row.is-hidden-row.is-selected .server-port-input {
  color: var(--text);
}
```
選取當下把文字暫時换回最亮的 `--text`（跟一般列選取時的文字色一致），虛線框保留、「這列被隱藏」的語彙沒有消失，只是文字重新可讀。這不是新增訊號，是「選取狀態底色變濃之後，原本就該搭配的文字對比修正」。

**封存＋選取**：`server-row-archived` 用 `opacity: .7` 稀釋整列（含背景色），32% 的選取底色套上去會被那層 opacity 再打七折，跳不出來。做法沿用一條**既有規則**，不是發明新數值：這頁的 `:hover` 早就會把 opacity 拉回 1（`.server-row-archived:hover { opacity: 1; }`），選取（比滑鼠移過去更明確的互動結果）比 hover 更該有同樣的待遇：
```css
.server-row.server-row-archived.is-selected { opacity: 1; }
```
實測：封存＋選取的一般背景色差跟「一般選取 vs 隱藏＋選取」只差 14（門檻 <20 視為沒有被稀釋），確認兩種疊加場景跟一般選取一樣顯眼。

### 3. Shift 多選模式：整份清單的互動元件暫時讓路給選取，游標是唯一的視覺提示
問題：Shift+點擊本來就能加選/減選單一列，但點在「改名稱」輸入框上時，滑鼠事件會先被輸入框接走（觸發 focus/進入編輯），不會變成選取——這就是 Dino 說的「很容易點到修改名稱，很容易誤觸」。

**判斷「其他會吃掉點擊的互動元件」的範圍**：不是只擋名稱輸入框，而是整列所有會吃掉點擊的控制項都擋——開關（顯示）、勾選（預設）、名稱輸入框、port 輸入框（連同外層 `<form>`，見下方實作注意）、複製按鈕、本機/線上連結、封存/解除封存按鈕。理由：使用者在「連續加選好幾支」的心流裡，Shift+點擊不小心點到任何一個控制項，都是同一種「誤觸」，不是只有改名稱風險高。批次操作列本身的按鈕、篩選列、手動新增表單都不在 `.server-select-scope` 容器內，不受影響——多選模式只作用在清單本身，不影響其他既有行為判斷。

```css
body.server-multiselect-active .server-select-scope .server-switch,
body.server-multiselect-active .server-select-scope .server-check,
body.server-multiselect-active .server-select-scope .server-name-input,
body.server-multiselect-active .server-select-scope .server-port-form,
body.server-multiselect-active .server-select-scope .server-copy-btn,
body.server-multiselect-active .server-select-scope .server-link-btn,
body.server-multiselect-active .server-select-scope .server-archive-btn,
body.server-multiselect-active .server-select-scope .server-unarchive-btn {
  pointer-events: none;
}
```
`pointer-events: none` 讓瀏覽器的點擊命中測試直接「跳過」這些元件，落在它們的父層（`.server-col-name` / `.server-col-port` 這些 `role="cell"` 容器，最終還是算在那一列身上）——原本的四手勢對照表完全不用改，因為點擊最終還是照既有的「Shift+點擊只切換這一列」規則走，只是「點擊真正命中的元素」從輸入框變成了列本身。

**視覺提示：只用游標，不疊加外框或背景色**——Dino 給了兩個方向（游標變化／清單整體的狀態暗示），選游標的理由：
- 這份清單常常比一個螢幕高（多分類、多列），如果用「容器外框」當提示，捲到清單中段時外框可能整個不在視野內，反而看不出「我在多選模式」；游標永遠跟著滑鼠所在位置，剛好就在使用者正要點擊的地方，回饋最即時。
- 游標的變化不是額外畫上去的裝飾，是 `pointer-events: none` 的**自然結果**：互動元件不接受事件之後，瀏覽器會把游標判定「穿透」給底下真正接收事件的列，看到的游標就是列本身的游標——這比另外疊一層視覺裝飾更誠實，也更「克制」。
```css
body.server-multiselect-active .server-select-scope .server-row[tabindex] { cursor: copy; }
```
從平常的 `cell`（可拖曳選取／可能開卡片／可能輸入）換成 `copy`（作業系統慣例的「＋」號，代表「加入某個集合」），跟「選取底色」用的是完全不同的訊號管道（游標 vs 背景色），兩者不會疊加成第二個視覺噪音。

**實作注意（Shift 狀態重置）**：`keydown`/`keyup` 監聽 Shift 只負責同步「現在是不是按著」這一件事：
```js
document.addEventListener('keydown', (e) => { if (e.key === 'Shift') setServerMultiselectActive(true); });
document.addEventListener('keyup', (e) => { if (e.key === 'Shift') setServerMultiselectActive(false); });
window.addEventListener('blur', () => setServerMultiselectActive(false));
document.addEventListener('visibilitychange', () => { if (document.hidden) setServerMultiselectActive(false); });
```
`window.blur` 與 `visibilitychange` 是為了處理「使用者按著 Shift 切去別的視窗，在別的地方放開」的情境——這個分頁永遠不會收到那次 `keyup`，不重置的話多選模式會卡住、整份清單的控制項會一直點不到。兩個事件都直接呼叫同一個 `setServerMultiselectActive(false)`，冪等（已經是 false 就不做事），不會跟正常的 keyup 路徑打架。

**踩雷記錄（測試階段抓到，跟正式功能無關但值得記）**：驗收腳本用 Playwright 對輸入框做過拖曳選字的模擬測試，會在瀏覽器留下真的 `window.getSelection()` 內容；`serverRowOpen()` 原本就有「正在選字就不開卡片」的防呆（`if (window.getSelection && String(window.getSelection())) return;`），這個殘留選字會讓後面的多選模式測試誤判成「點擊被擋下」。這不是產品程式碼的 bug，是測試之間的殘留狀態污染，修法是在新測試開始前 `window.getSelection().removeAllRanges()`，跟「拖曳中途版面位移」一樣，記錄下來給下次寫類似測試時參考。

### 4. 說明文字：斷行位置照 Dino 指定 ＋ 粗體字顏色統一成灰
兩個獨立小問題，同一段文字（`.server-view-hint`）：

**斷行**：原本交給瀏覽器自動 reflow，在某些寬度下會斷在「用不到的按」之後、把粗體的「封存」跟前面的「按」拆開兩行，讀起來卡。Dino 指定要在「顯示」那句的分號後強制斷成兩句。三個做法選了哪一個：
- ❌ 純粹加大 `<br>`：沒有考慮「按封存」被拆開的問題，治標不治本。
- ❌ 兩個 `display:block` 區塊：功能跟 `<br>` 完全一樣，但多寫一層 DOM 沒有額外好處，這裡沒有「兩區塊要各自加樣式」的需求，選它只是繞遠路。
- ✅ **`<br>` 強制斷成兩句 ＋ 把「按封存」包一個 `white-space: nowrap` 的 span，兩個問題分開解決**：`<br>` 解決「Dino 要的斷行位置」，`.keep-together` 解決「按封存不能被拆開」——這是兩個不同層次的問題（一個是句子級的斷行、一個是詞組級的不可拆），用兩個對應的機制各自處理，比硬找一個機制同時解決兩件事更清楚。
```html
<span class="zh">清單自動從各卡片的「bat」啟動指令生成，分類跟著卡片走。<b>顯示</b>＝要不要出現在本機總管；<br><b>預設</b>＝總管一打開就先勾起來（開機會自動開）；用不到的<span class="keep-together">按<b>封存</b></span>收起來。</span>
```
**沒有加窄螢幕覆寫（沒有讓 `<br>` 在 mobile 消失）**：實測 390px 寬度下，兩個分句各自還會再自然換行成兩小行（共約 4 行），"按封存" 仍然完整在同一行，沒有出現「兩三個字獨占一行」的孤兒行或任何比原本更差的斷行——因為兩個分句本身長度夠短（換算約 450-515px），在手機寬度下重新排版時每個分句都還是完整的語意單位，不會因為多了一次強制斷行就變差。所以判斷不需要用媒體查詢覆寫拿掉這個 `<br>`；如果之後文案改得更長、手機上真的出現孤兒行，再補窄螢幕覆寫。
英文版 `<span class="en">` Dino 說不用比照，維持原樣（自動換行沒有這個問題）。

**顏色**：`.server-view-hint b` 原本疊了 `color: var(--text)`（近白），跟本文的 `--text-muted`（灰）並存，讀起來「灰白相間」。判斷後選擇**保留 `<b>` 但拿掉顏色疊加**，只留 `font-weight: 700` 做強調：
```css
.server-view-hint b { font-weight: 700; }
```
沒有選「拿掉 `<b>` 完全不強調」——這是一段 13px、line-height 1.7 的說明文字，字重從 400 到 700 的差異在同一個灰階下依然看得出來（實測 `getComputedStyle` 確認兩者現在同色 `rgb(113,113,122)`，`font-weight` 分別是一般與 700），沒有必要為了「消除灰白混雜」連強調本身都拿掉；也沒有另外挑一個新的灰階色階來強調（例如用更深一階的灰），避免又製造出「這個灰跟那個灰哪裡不一樣」的新疑惑——統一用同一個 `--text-muted`，只在字重上做文章，是最少變動、最不會製造新問題的做法。

## 產物位置
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\css\dashboard.css`
  - `.server-row.is-selected` / `:hover`：混色比例 16%/22% → 32%/40%
  - 新增 `.server-row.is-hidden-row.is-selected` 文字色覆寫、`.server-row.server-row-archived.is-selected { opacity: 1; }`
  - 新增 Shift 多選模式區塊：`body.server-multiselect-active .server-select-scope .server-row[tabindex]`（游標）＋一組 `pointer-events: none` 選擇器
  - `.server-view-hint b` 拿掉顏色疊加、新增 `.server-view-hint .keep-together`
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\js\dashboard.js`
  - 新增 `serverMultiselectActive` / `setServerMultiselectActive()`，掛 `keydown`/`keyup`/`blur`/`visibilitychange` 四個監聽
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\templates\partials\_server_list.html`
  - `.server-view-hint` 的中文說明：插入 `<br>`、把「按封存」包進 `.keep-together`

## 自審結果（④ 心法）
- **a11y**：文字對比是這輪的重點——`.server-row.is-hidden-row.is-selected` 的文字色從 `--text-muted`（疊加後只剩約 2.3:1）改回 `--text`（換算後深色/淺色模式都在 9:1 以上），沒有讓對比隨著底色加強而變差，符合任務要求「文字對比不能被犧牲」。Shift 多選模式沒有拿掉任何鍵盤可達的操作——`pointer-events:none` 只影響滑鼠點擊的命中測試，Tab 順序與鍵盤 Space/Enter 完全不受影響（`pointer-events` 不影響 focus 與鍵盤事件）。
- **狀態完整度**：選取／隱藏／封存／可開卡片 四種狀態的兩兩疊加，這次不只肉眼看、也用 Playwright 的 canvas rasterize 量出實際 RGB 差異做斷言（一般選取 vs 隱藏＋選取的背景差異僅 14，證明沒有被稀釋；封存＋選取的 opacity 確認回到 1）。Shift 多選模式的四個狀態轉換（按下進入／放開恢復／視窗失焦重置／模式中點擊落到列上）都各自驗證過。
- **RWD**：說明文字的 `<br>` 在 390px 手機寬度實測過，沒有產生孤兒行或比原本更差的斷行；Shift 多選模式是滑鼠鍵盤裝置專屬的操作（觸控裝置本來就沒有實體 Shift 鍵這個概念，不受影響，維持原本「觸控回退成逐列點擊」的設計）。
- **對比**：本輪唯一的顏色決策改動（`.server-view-hint b`）是刻意「降低」視覺複雜度（拿掉一個顏色），不是新增，兩個顏色統一成一個之後兩者對比完全相同，不存在對比不足的風險。

## 後續建議（第四輪，2026-09-15）
- 給 Bevis：選取底色加強、疊加狀態修正、Shift 多選模式，都是同一個既有設計方向的強度/細節調整，沒有偏離已認可的產品方向；說明文字的斷行/配色是純文案排版修正，不影響功能。
- 給 Ray：**驗收腳本已補上 4 項新斷言（多選模式擋下輸入框點擊、放開 Shift 恢復正常、視窗失焦重置多選模式、選取底色與一般列的實際背景色差 > 90）＋原有 21 項全數維持通過，共 25 項**；一樣建議找有 editor 權限的帳號實測一次「按住 Shift 連續點好幾支 bat 加選」的真實手感，畢竟游標變化這種細節，模擬測試能驗證「有沒有生效」，驗證不了「使用者是否真的會注意到」。

---

## 第五輪（2026-09-16）：淺色主題語意色對比度補值 ＋ 常用工具標題調亮

### 任務意圖判定
- (A) 淺色主題語意色看不見 → 屬於 ④「審查/合規缺口」性質的 bug（對比度不足），但修法是補 token，動的正是 design token 層。
- (B) 常用工具標題太重 → 屬於 ②「顧問」的視覺調校（既有畫面局部調亮）。
- 兩者都動 `:root` / `[data-theme="light"]` 的 token 定義，依 Dino 指名載入 `ui-ux-pro-max`（對比度/色彩判斷）＋ `design-system`（三層 token 方法論：primitive 色階 → 語意 token → 這次新增的 `--warning-title` 屬於 component 層，特意跟語意層 `--warning` 脫鉤）。Windows 主機端兩支皆為正版，未走 fallback。

### 根因
淺色主題 `[data-theme="light"]` 從建立以來只覆寫了 bg/surface/border/text/primary/code/shadow，`--success` / `--warning` / `--danger` / `--accent` / `--accent-2` 五組語意色從未被覆寫，等於淺色主題全程沿用深色主題調校過的高亮值（例如 `--warning: #FBBF24`），直接鋪在白底上（`.cmd-env.bat` 的「BAT」標籤、常用工具標題、狀態徽章…）對比度全部不足，Dino 點名的「伺服器的啟動指令看不到字」只是這個缺口裡最顯眼的一個。

### 整體協調性檢視
- **退一步看整張畫面**：這不是「一個角落壞了」，是一整組語意色（黃/綠/紅/藍）在淺色主題下全部沒有值，影響 15＋11＋7＋4 處使用點；只修 `.cmd-env.bat` 那一行沒有意義，同一個 `--warning` 換了色，星星圖示、狀態徽章、常用工具分組標題、路徑連結全部會同時改變觀感——所以這次是**在 token 層一次補齊**，而不是在各個選擇器上分別貼 `!important` 或另開一批新 class（那樣才是「硬塞」）。
- **有沒有發現該整合的按鍵/入口**：沒有，這次是純視覺 token 缺口，不涉及操作動線或控制項數量。

### 設計決策

**1）淺色主題語意色（用同色相家族的 Tailwind 700/800 深階，取代深色主題的 400 淺階）**

| Token | 深色（不變） | 淺色（新增） | 對白底文字對比度 | 說明 |
|---|---|---|---|---|
| `--warning` | `#FBBF24`（amber-400） | `#92400E`（amber-800） | **7.09:1** | 徽章/圖示用，字級多在 11-12px，需要最大可讀性，选比 700 更深一階的 800 |
| `--warning-bg` | `rgba(251,191,36,.12)` | `rgba(217,119,6,.12)` | — | 底色改用 amber-600 調的淡tint，跟新的深色文字仍保持 6:1＋（不是只換前景不換底） |
| `--warning-title`（新 token） | `#FCD34D`（amber-300，新增） | `#B45309`（amber-700） | 深 12.29:1／淺 5.02:1 | 詳見下方第 2 點 |
| `--success` | `#34D399` | `#047857`（emerald-700） | 5.48:1 | |
| `--success-bg` | `rgba(52,211,153,.12)` | `rgba(16,185,129,.12)` | — | |
| `--danger` | `#F87171` | `#B91C1C`（red-700） | 6.47:1 | |
| `--danger-bg` | `rgba(248,113,113,.12)` | `rgba(239,68,68,.12)` | — | |
| `--accent` | `#38BDF8` | `#0369A1`（sky-700） | 5.93:1 | |
| `--accent-2` | `#A78BFA` | `#6D28D9`（violet-700） | 7.10:1 | CSS 裡目前沒有引用點，補值只為兩主題定義一致，不算這次的 bug 範圍 |

所有對比度都是先手算（WCAG 相對亮度公式）、再用 Playwright 實際量 computed style 覆核，兩邊數字吻合（見下方驗收）。**語意沒有換色相**：黃還是警告/常用/待處理、綠還是成功、紅還是危險、藍還是資訊——只是深淺主題各自用同一色相裡對比度夠的階層，不是碰運氣換另一種顏色。

**2）常用工具標題：新增獨立 token `--warning-title`，不直接改 `--warning`**

Dino 原話「太重了可以亮一點點」，但 `--warning` 同時被星星圖示、狀態徽章「開發中」、路徑連結標籤共用 15 處——直接調亮 `--warning` 會讓這些完全不相干的地方一起變亮/變淡，其中徽章字級只有 11px，對比度餘裕比標題小很多，禁不起同方向調整。所以新增一顆語意下的 component 級 token 專門給這個用途：
- 深色：`#FCD34D`（amber-300，比 `--warning` 亮一階，對 `--surface` 對比度 12.29:1，`--warning` 本身是 10.61:1——原本餘裕就很大，亮一階仍遠高於 4.5:1 下限，符合「亮一點點」而非「換個顏色」）。
- 淺色：`#B45309`（amber-700，比徽章用的 `--warning`＝amber-800 亮一階、對白底 5.02:1，仍 ≥ 4.5:1）。
- 兩個主題都是「亮一階」而不是「改色相/降飽和」，星星圖示與徽章的 `--warning` 完全沒動，實測截圖（見下）兩者色調有明顯區隔但同屬金色家族，不會讓人覺得「不同語意」。

### 產物位置
- `C:\Users\AG_Di\Desktop\automation\Claude_code\side_project\DinoDashboard\static\css\dashboard.css`
  - `:root`：新增 `--warning-title: #FCD34D;`（第 26-28 行附近）
  - `[data-theme="light"]`：新增 `--accent` / `--accent-2` / `--success` / `--success-bg` / `--warning` / `--warning-bg` / `--warning-title` / `--danger` / `--danger-bg` 九個 token（原本完全缺席）
  - `.project-card:has(.star-btn.starred) .card-name`：`color: var(--warning)` 改成 `color: var(--warning-title)`

### 自審結果（④ 心法）
- **a11y / 對比**：這輪的核心就是對比度——14 項斷言（7 個目標元素 × 2 主題）全部 ≥ 4.5:1（文字）或 ≥ 3:1（星星圖示，非文字元件門檻），數字最低的是淺色主題常用工具標題 5.02:1，餘裕還有 0.5 才會低於 AA，屬於刻意壓在「夠亮但仍安全」的位置，沒有為了亮度犧牲下限。
- **狀態完整度**：語意色被 4 種語意（成功/警告/危險/資訊）× 2 主題共用在 15＋11＋7＋4 處，這次是補 token 缺口而非新增狀態，沒有遺留新的空狀態/錯誤狀態需求。
- **RWD**：純色彩 token 改動，不影響版面斷點。
- 唯一的量測近似：`.star-btn.starred` 實際疊在卡片縮圖（相片）上，Playwright 用 DOM 祖先鏈算出的背景色是 `.project-card` 的 `--surface`，不是相片本身顏色——這是已知近似，圖示本身有 `drop-shadow` 兜底可讀性，且這次沒有改變它在兩個主題下的可讀性策略，只是提醒下次如果要嚴格驗證疊圖上的圖示對比，需要換成實際截圖取色而非 DOM 合成。

### 驗收
新增 `C:\Users\AG_Di\Desktop\automation\Playwright\dinodashboard_ui_check\check_theme_contrast.py`，7 個目標元素 × 2 主題＝14 項對比度斷言全部通過（訪客身分抓不到的 `.status-wip` / `.status-pending` / `.detail-link-path` 用 `page.evaluate()` 注入對應 class 的節點量測，同一個 CSS selector 若畫面上有真實元素會優先抓到真實的，兩種情況共用同一套斷言邏輯，沒有呼叫任何寫入型 API）；另截圖 `shots\theme_dark_semantic.png` / `theme_light_semantic.png`（常用工具卡片標題）與 `theme_dark_hero.png` / `theme_light_hero.png`（啟動指令標籤所在的「快捷啟動」區塊）供人眼覆核。另外重跑三支既有回歸腳本（`check_batch_select_sim.py` 25 項、`verify_server_tab.py`、`check_server_filter_bar.py`）全數通過，確認本次 token 改動沒有波及伺服器分頁的選取/篩選功能。
- 給 Andy：這輪的教訓——「同一個訊號加強度」跟「疊加另一個訊號」是兩件完全不同的事，前者是本輪該做的（Dino 要的是『更濃』不是『更多種』），後者是上一輪剛被退件的做法，兩者很容易在「使用者說不夠顯眼」的當下被混為一談，做之前先問清楚是「不夠濃」還是「看不出來是什麼意思」。另外「pointer-events:none 讓游標自然穿透」這個技巧值得記一筆：不用額外寫游標邏輯，把互動元件設成不接受事件，游標與點擊命中會自動一起正確運作。

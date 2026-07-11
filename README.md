# ✈️ Google Flights 機票降價追蹤通知器 (Flight Tracker)

這是一個基於 Python 開發的**機票降價監控與自動通知系統**。系統能透過 [SerpApi (Google Flights)](https://serpapi.com/google-flights-api) 查詢即時航班票價，並結合本地端 SQLite 資料庫進行歷史低價比對。當票價創歷史新低或低於理想預算時，會自動透過 **LINE Messaging API** 發送精美格式的私訊通知到您的 LINE 帳號。

---

## 🌟 系統功能

1. **雙重搜尋模式**：
   * **單一日期模式 (`single`)**：針對特定去回程日期進行點對點追蹤。
   * **區間彈性搜尋模式 (`range`)**：設定一段長日期區間與旅遊天數（N 天），程式將自動算出區間內所有排列組合（例如：出發日 10/3 ~ 10/9，去 5 天，自動計算 10/3-10/8, 10/4-10/9 等組合），並自動進行批量票價查詢。
2. **自動排序與推薦**：
   * 在區間模式下，自動將所有查詢結果依票價由低到高排序，並篩選出前 $K$ 個最便宜的起迄日組合。
3. **歷史票價追蹤 (SQLite)**：
   * 整合 SQLite 本地資料庫 (`flights_history.db`)，每當查詢時會自動記錄時間、航線、起訖日、票價與 Google Flights 連結。
   * 自動進行**同日期組合**的歷史票價比對，判斷是否降價。
4. **LINE 自動推播通知**：
   * 當查到票價低於您的預設「理想預算」或「低於該日期的歷史最低價」時，系統會自動透過 LINE Messaging API 發送降價警報。
   * 區間搜尋下會整合多個推薦組合為一則訊息，並附上每組的 Google Flights 直達訂票連結，避免洗版。

---

## 🛠️ 使用技術

* **開發語言**：Python 3.12+
* **即時票價數據來源**：[SerpApi](https://serpapi.com/) 的 `google_flights` 搜尋引擎。
* **資料儲存**：SQLite（Python 內建資料庫，免安裝設定）。
* **通知通道**：LINE Messaging API (Push Message)。
* **第三方套件**：
  * `requests`：用於發送 API 網路請求。

---

## 🔑 環境變數設定 (`.env`)

本專案使用環境變數管理所有配置設定與 API 密鑰。請在專案根目錄下建立 `.env` 檔案，並填入以下內容：

```ini
# ================= 密鑰與權限設定 =================
# SerpApi API Key (請至 https://serpapi.com/ 註冊取得免費額度)
API_KEY=您的_SERPAPI_API_KEY

# LINE 官方帳號 Messaging API 設定
# 1. 管道存取權杖 (Channel Access Token)
LINE_ACCESS_TOKEN=您的_LINE_CHANNEL_ACCESS_TOKEN
# 2. 您的 User ID (請登入 LINE Developers Console，在 Messaging API 頁籤最下方取得 "Your user ID")
LINE_USER_ID=您的_LINE_USER_ID

# ================= 航線與模式設定 =================
# 出發地機場代碼 (如：TPE 代表桃園機場)
FLY_FROM=TPE
# 目的地機場代碼 (如：DAD 代表峴港機場)
FLY_TO=DAD

# 模式選擇: "single" (單一日期) 或 "range" (區間天數)
SEARCH_MODE=range

# 1. [單一模式參數] 去程與回程日期 (YYYY-MM-DD)
DATE_FROM=2026-10-03
DATE_TO=2026-10-09

# 2. [區間模式參數] 搜尋區間起點、終點、旅遊天數 (晚數) 與前幾名便宜的推薦數
RANGE_START=2026-10-03
RANGE_END=2026-10-09
TRAVEL_DURATION=5
TOP_N_RESULTS=3

# ================= 通知與資料庫 =================
# 理想預算門檻 (只要票價低於此價格就會發送通知)
PRICE_THRESHOLD=8000
# 本地 SQLite 資料庫名稱
DB_NAME=flights_history.db
```

---

## 🚀 快速開始

### 1. 安裝必要套件
本專案只依賴 `requests` 來發送 HTTP 請求：
```bash
pip install requests
```

### 2. 配置環境變數
請參考 [環境變數設定](#-環境變數設定-env) 建立您的 `.env` 檔案，填入真實的 API 金鑰與 LINE ID。

### 3. 執行程式
執行以下指令開始追蹤票價：
```bash
python flight_tracker.py
```

### 4. 訊息通知範例
當觸發降價條件時，您的 LINE 就會收到如下的即時通知：

```text
✈️ 【機票降價通知 (區間搜尋)】
航線：TPE ➡️ DAD (旅遊天數: 5天)
最便宜的前幾名組合：

1. 2026-10-03 ➡️ 2026-10-08
   票價：NT$ 6492 (歷史最低: NT$ 6492)
   連結：https://www.google.com/travel/flights...

2. 2026-10-04 ➡️ 2026-10-09
   票價：NT$ 11233 (歷史最低: NT$ 11233)
   連結：https://www.google.com/travel/flights...
```

---

## 🤖 GitHub Actions 自動化部署 (`tracker.yml`)

本專案支援使用 GitHub Actions 進行定時自動監控（Cron Job），自動在雲端執行並將降價資訊推播至您的 LINE，並且會將最新的票價歷史資料庫同步儲存回 GitHub 專案中，達到免實體主機、零成本的完全自動化。

### 1. GitHub 變數設定

在執行工作流之前，請登入您的 GitHub 專案，前往 **Settings** -> **Secrets and variables** -> **Actions**，並在裡面設定以下項目：

#### 🔒 Secrets (機密金鑰，不可公開)
請至 **Secrets** 分頁中新增以下三個儲存庫機密：
* `API_KEY`：您的 SerpApi 帳號金鑰。
* `LINE_ACCESS_TOKEN`：您的 LINE Channel Access Token。
* `LINE_USER_ID`：您的 LINE 帳號 User ID。

#### ⚙️ Variables (常規設定，明文變數)
請至 **Variables** 分頁中新增以下變數（當排程自動執行，或手動執行時欄位留空，會自動套用此處的設定作為預設值）：
* `FLY_FROM`：出發機場 (例如 `TPE`)
* `FLY_TO`：目的地機場 (例如 `DAD`)
* `SEARCH_MODE`：搜尋模式 (`range` 或 `single`)
* `RANGE_START`：區間開始日期 (例如 `2026-10-03`)
* `RANGE_END`：區間結束日期 (例如 `2026-10-09`)
* `TRAVEL_DURATION`：旅遊天數 (例如 `5`)
* `TOP_N_RESULTS`：推薦票價組數 (例如 `5`)
* `PRICE_THRESHOLD`：LINE 通知價格門檻 (例如 `8000`)

---

### 2. 如何執行與管理

#### 📅 定時自動排程 (Cron)
目前 [.github/workflows/tracker.yml](file:///d:/NCNU_AI_CLASS/project/flights_freedom/.github/workflows/tracker.yml) 設定為**每兩天執行一次**。它會全自動在雲端以您設定的 GitHub Variables 做為搜尋條件執行。

#### ⚡ 手動即時執行 (自訂參數)
如果您想臨時修改目的地、出發日或價格門檻來查詢，完全不需要修改任何程式碼：
1. 前往 GitHub 專案頁面的 **Actions** 頁籤。
2. 點擊左側選單的 **Flight Tracker Cron Job**。
3. 點選右側的 **Run workflow** 下拉按鈕。
4. **直接在網頁表單中輸入您這次想查詢的條件**（若全部留空，則會自動套用您設定的 GitHub Variables 預設值）。
5. 點擊綠色的 **Run workflow** 按鈕即可開始執行。

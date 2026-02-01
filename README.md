# 📊 籌碼 K 線 (Taiwan Stock Chip Analysis Tool)

這是一個基於 Python 與 Streamlit 開發的台灣股市籌碼分析工具。它整合了技術分析（K線、均線、指標）與深度籌碼數據（分點進出、三大法人、融資券、集保分佈、主力買賣超），並提供互動式的圖表介面，幫助投資人進行全方位的個股分析。

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)

## ✨ 主要功能

本應用程式包含多個分析分頁，涵蓋了從技術面到籌碼面的詳細數據：

### 1. 📈 K線 (Technical Analysis)
* **互動式圖表**：使用 `streamlit-lightweight-charts` 繪製高效能 TradingView 風格圖表。
* **多週期支援**：日K、週K、月K，以及分時走勢（5分/15分/30分/60分）。
* **技術指標**：
    * 均線 (MA5, MA10, MA20, MA60, MA120, MA240)
    * 布林通道 (Bollinger Bands)
    * 副圖指標：成交量、KDJ、MACD、RSI。
* **籌碼副圖**：可將外資、投信、主力買賣超、分點買賣超直接疊加於 K 線副圖觀察。

### 2. 🏦 分點 (Broker Branch Analysis)
* **關鍵券商追蹤**：自動統計指定區間內的 **買超前 15 大** 與 **賣超前 15 大** 券商分點。
* **明細查詢**：點擊特定券商，即可查看該分點在該檔股票的歷史進出明細與累積損益圖表。
* **視覺化表格**：紅綠顏色標示買賣超狀態與平均成本。

### 3. 👥 法人與主力 (Institutional & Main Force)
* **三大法人**：外資、投信、自營商的每日買賣超與累積持倉趨勢。
* **主力數據**：整合「玩股網」數據，顯示主力買賣超與買賣家數差（判斷籌碼集中度）。

### 4. 📉 融資券 (Margin Trading)
* 追蹤融資與融券的每日增減與餘額，判斷散戶多空情緒。

### 5. 🐳 大戶 (Shareholder Distribution)
* **集保股權分散表**：抓取每週集保數據。
* **大戶 vs 散戶**：可自訂「大戶」（如 400 張以上）與「散戶」（如 50 張以下）標準，繪製持股比例消長圖，一眼看穿籌碼流向。

### 6. 🏆 類股排行 (Sector Ranking)
* 列出上市櫃每週「大戶持股增加」排行榜 Top 100，快速尋找潛力股。

### 7. ⚡ 飆股篩選 (Stock Screener)
* **自動掃描**：系統會自動掃描市場，篩選同時符合以下條件的強勢股：
    1.  大戶籌碼顯著增加（入榜）。
    2.  法人連續買超 3 日。
    3.  主力近期呈現買超狀態。

### 8. 📊 多股比較 (Multi-Stock Comparison)
* 同時輸入多檔股票代號，在同一畫面比較其走勢與特定指標（如成交量、KDJ、主力買賣超等）。

---

## 🛠️ 安裝與執行 (Installation)

### 1. 環境需求
* **Python**: 建議使用 Python 3.9 或以上版本。
* **Google Chrome**: 本程式使用 Selenium 爬蟲，請確保電腦已安裝 Google Chrome 瀏覽器。

### 2. 安裝依賴套件
請確認目錄下有 `requirements.txt`，然後執行：

```bash
pip install -r requirements.txt

3. 執行程式
在終端機 (Terminal) 執行以下指令啟動 Streamlit：

Bash
streamlit run app.py
(請將 app.py 替換為您的主程式檔名)

⚙️ 技術細節
資料來源：

股價：yfinance

籌碼/分點：透過 selenium 爬取富邦證券 (Fubon eBroker) 與神秘金字塔 (Norway) 等公開資訊。

主力：透過 seleniumbase 爬取玩股網 (Wantgoo)，具備繞過 Cloudflare 驗證的機制。

爬蟲機制：使用 Headless Chrome (無頭模式) 進行背景抓取，並包含快取機制 (@st.cache_data) 以減少重複請求並加快載入速度。

介面優化：支援深色 (Dark) 與淺色 (Light) 模式切換，並針對 CSS 進行了排版優化。

⚠️ 免責聲明 (Disclaimer)
本工具僅供技術研究與程式教學用途，所有數據來源皆為網路公開資訊。

本工具不提供任何投資建議。股市投資具有風險，使用者應自行判斷並承擔風險。

爬蟲功能依賴於第三方網站的結構，若目標網站改版可能會導致部分功能失效。

Happy Trading! 🚀


---

### 2. 請在 GitHub 專案中新增 `requirements.txt` 檔案

為了讓別人（或您換電腦時）能一鍵安裝所有套件，請建立一個名為 `requirements.txt` 的檔案，內容如下：

```text
streamlit
pandas
yfinance
selenium
webdriver-manager
requests
twstock
numpy
streamlit-lightweight-charts
pytz
lxml
seleniumbase

# 📊 籌碼 K 線 (Chip K-Line) - 台股主力籌碼分析工具

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Selenium](https://img.shields.io/badge/Selenium-Web%20Scraping-green)

這是一個基於 Python 與 Streamlit 開發的互動式網頁應用程式，專為台灣股市投資人設計。透過即時爬蟲技術，抓取富邦證券的主力進出資料，並結合 `yfinance` 股價數據，視覺化呈現特定券商分點與股價走勢的關聯。

## ✨ 主要功能

* **主力買賣超排行**：即時爬取指定股票在特定區間（1日 ~ 240日）的買超與賣超前 15 大券商分點。
* **視覺化數據**：透過 Plotly 繪製互動式圖表，清楚呈現買賣超張數與平均成本。
* **分點深度追蹤**：
    * 選定特定券商分點，追蹤其過去 2 年的每日進出明細。
    * 結合 K 線圖（Candlestick）與均線（MA5, MA10, MA20, MA60）。
    * 雙軸圖表：同時觀察股價走勢與該分點的累計庫存變化。
* **智慧快取機制**：內建快取系統（TTL=7天），避免重複爬取，提升查詢速度並降低伺服器負擔。
* **雲端相容**：特別優化 Selenium 驅動邏輯，可直接部署於 Streamlit Cloud。

## 🛠️ 技術架構

* **Frontend**: [Streamlit](https://streamlit.io/)
* **Data Source**: 
    * [yfinance](https://pypi.org/project/yfinance/) (股價資料)
    * Selenium Web Scraping (富邦證券主力進出表)
* **Visualization**: [Plotly](https://plotly.com/)
* **Browser Automation**: Selenium + Chromium (Headless)

## 📂 檔案結構

專案目錄應包含以下檔案，以確保在雲端環境正常運作：

```text
.
├── main.py            # 主程式碼 (Streamlit App)
├── requirements.txt   # Python 套件依賴清單
├── packages.txt       # 系統級依賴 (用於安裝 Chrome/Chromium)
└── README.md          # 專案說明檔

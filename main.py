import streamlit as st
import pandas as pd
import yfinance as yf
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from io import StringIO
import time
import re
import math
import requests
from datetime import datetime, timedelta
import pytz
from urllib.parse import urlparse, parse_qs
import shutil
import twstock
import copy
import numpy as np
import os

# ✅ [NEW] 新增 SeleniumBase 相關引用
import nest_asyncio
from seleniumbase import SB
from pyvirtualdisplay import Display

# ✅ TradingView 圖表套件
from streamlit_lightweight_charts import renderLightweightCharts

# 應用 nest_asyncio 以解決 Colab/Streamlit 環境下的 Event Loop 問題
nest_asyncio.apply()

# ================= 1. 系統設定 =================

st.set_page_config(layout="wide", page_title="籌碼K線", initial_sidebar_state="auto")

# ✅ CSS 設定 (整合：隱藏 Header + 手機版優化 + 介面樣式)
st.markdown("""
    <style>
    /* ================= 隱藏 Streamlit 預設 Header 與 GitHub 圖示 ================= */
    header[data-testid="stHeader"] {
        visibility: hidden;
    }
    /* 隱藏部署按鈕 (保險起見) */
    .stDeployButton {
        display: none;
    }
    /* 修正頂部留白 (因為隱藏了 Header，把內容往上推) */
    .block-container {
        padding-top: 1rem !important;
    }

    /* ================= 通用字體設定 ================= */
    html, body, [class*="css"] { font-size: 18px !important; }
    .stDataFrame { font-size: 16px !important; }
      
    /* ================= 數據卡片樣式 ================= */
    .metric-container {
        display: flex;
        justify-content: space-between;
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
        margin-top: 5px;
        flex-wrap: wrap;
    }
    .metric-item {
        text-align: center;
        width: 48%;
        min-width: 100px;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #aaa;
        white-space: nowrap;
    }
    .metric-value {
        font-size: 1.2rem;
        font-weight: bold;
    }

    /* ================= 手機版 RWD (螢幕 < 768px) ================= */
    @media (max-width: 768px) {
        html, body, [class*="css"] { font-size: 15px !important; }
        .stDataFrame { font-size: 14px !important; }
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.3rem !important; }
        .metric-container { padding: 8px; gap: 5px; }
        .metric-label { font-size: 0.8rem; }
        .metric-value { font-size: 1rem; }
        
        /* 手機時：隱藏包含 desktop-marker 的容器 */
        div[data-testid="stVerticalBlock"]:has(> .element-container .desktop-marker) {
            display: none !important;
        }

        /* ✅ [FIX] 手機版 Radio Button 優化：縮小間距與內距，確保單行顯示 */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 2px !important; /* 縮小按鈕間距 */
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] label {
            padding: 6px 8px !important; /* 縮小點擊範圍內距 */
            font-size: 14px !important; /* 稍微縮小字體 */
        }
    }

    /* ================= 電腦版 RWD (螢幕 > 768px) ================= */
    @media (min-width: 769px) {
        /* 電腦時：隱藏包含 mobile-marker 的容器 */
        div[data-testid="stVerticalBlock"]:has(> .element-container .mobile-marker) {
            display: none !important;
        }
    }

    /* ================= [CSS 強制修正] Radio Button 樣式 ================= */
    
    /* 1. 隱藏 Radio 的圓圈輸入框 */
    div[data-testid="stRadio"] > div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }

    /* 2. 調整 Radio Group 容器 - 透明背景，只在選項區域下方顯示線條 */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: transparent;
        border: none;
        box-shadow: none;
        padding: 0;
        gap: 10px; /* 選項間距 */
        display: flex;
        flex-direction: row;
        
        /* ✅ [FIX] 強制不換行，並允許橫向捲動 (手機版關鍵修正) */
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        white-space: nowrap !important;
        
        margin-bottom: 5px;
        /* 這裡加上一條全長的淡線當作軌道 (可選) */
        border-bottom: 1px solid rgba(255, 255, 255, 0.1); 
        width: 100%; /* 佔滿寬度 */
        
        /* 隱藏捲軸 */
        scrollbar-width: none; 
        -ms-overflow-style: none;
    }
    
    /* 隱藏 Chrome/Safari 捲軸 */
    div[data-testid="stRadio"] > div[role="radiogroup"]::-webkit-scrollbar {
        display: none;
    }

    /* 3. 設定每個選項 (Label) 的基礎樣式 */
    div[data-testid="stRadio"] > div[role="radiogroup"] label {
        background-color: transparent !important;
        border: none;
        border-radius: 6px 6px 0 0; /* 上方圓角 */
        color: #8b92a2 !important; /* 未選中：灰色 */
        padding: 8px 16px !important; /* 增加點擊範圍 */
        margin: 0 !important;
        font-weight: 500;
        font-size: 16px;
        transition: all 0.15s ease-in-out;
        border-bottom: 3px solid transparent; /* 預留底線位置 */
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto; /* ✅ [FIX] 防止項目被壓縮 */
    }

    /* 4. ✅ 滑鼠懸停效果 (Hover) */
    div[data-testid="stRadio"] > div[role="radiogroup"] label:hover {
        color: #ffffff !important;
        background-color: rgba(255, 255, 255, 0.05) !important; /* 懸停時淡淡的灰 */
    }

    /* 5. ✅ [關鍵修正] 選中狀態 (Active) */
    div[data-testid="stRadio"] > div[role="radiogroup"] label:has(input:checked) {
        color: #ef5350 !important; /* 文字變紅 */
        border-bottom: 3px solid #ef5350 !important; /* 底部紅線 */
        background-color: rgba(239, 83, 80, 0.15) !important; /* 背景淡紅 */
        font-weight: bold !important;
    }
    
    div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding-top: 2px !important; /* 垂直微調 */
        
        /* 👇 這裡控制左右位置，負數往左 */
        transform: translateX(-5px) !important; 
        
        /* ✅ [FIX] 確保文字不換行 */
        white-space: nowrap !important;
    }
    
    /* 修正內部文字顏色與對齊，確保被選中時文字真的變紅且置中 */
    div[data-testid="stRadio"] > div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: #ef5350 !important;
        font-weight: bold !important;
        margin: 0 !important;
        /* ✅ [微調] 增加一點點上邊距，人工修正視覺基準線，確保文字在紅框中完美垂直置中 */
        padding-top: 2px !important; 
    }
    </style>
    """, unsafe_allow_html=True)

COLOR_UP = '#ef5350' # 紅色 (上漲)
COLOR_DOWN = '#26a69a' # 綠色 (下跌)

# ================= 2. 輔助函式 =================

def normalize_name(name):
    return str(name).strip().replace(" ", "").replace("　", "")

# ✅ [Refactor] 共用日期解析函式
def is_roc_date(s: str) -> bool:
    return re.match(r"\d{2,3}/\d{1,2}/\d{1,2}", str(s).strip()) is not None

def roc_to_datestr(d_str: str) -> str | None:
    parts = re.split(r"[/-]", str(d_str).strip())
    if len(parts) < 2:
        return None
    y = int(parts[0])
    y = y + 1911 if y < 1911 else y
    m = int(parts[1])
    d = int(parts[2]) if len(parts) > 2 else 1
    return f"{y:04d}-{m:02d}-{d:02d}"

# ✅ 獲取所有股票選單 (代號 + 名稱)
@st.cache_data
def get_all_stock_options():
    stock_options = []
    # 使用 twstock 內建代碼表
    for code, info in twstock.codes.items():
        if info.type == "股票": 
            stock_options.append(f"{code} {info.name}")
    return stock_options

def get_stock_name(stock_id):
    try:
        if stock_id in twstock.codes:
            return twstock.codes[stock_id].name
        return ""
    except:
        return ""

# ✅ [MODIFIED] 修改 render_broker_table 以支援互動選取
def render_broker_table(df, sum_data, color_hex, title, key_id):
    if "買超" in title:
        label_total = "🔴 合計買超張數"
        label_avg = "🔴 平均買超成本"
    else:
        label_total = "🟢 合計賣超張數"
        label_avg = "🟢 平均賣超成本"

    full_config = {
        "broker": "券商分點",
        "buy": st.column_config.NumberColumn("買進", format="%d"),
        "sell": st.column_config.NumberColumn("賣出", format="%d"),
        "net": st.column_config.NumberColumn("買賣超", format="%d"),
        "pct": "佔比"
    }
    
    # ✅ 使用 on_select 啟用選擇功能
    event = st.dataframe(
        df.style.map(lambda x: f'color: {color_hex}; font-weight: bold', subset=['net']),
        use_container_width=True, 
        height=500, 
        hide_index=True, 
        column_config=full_config,
        on_select="rerun", # 點擊後重新執行 (由 Streamlit 內部觸發)
        selection_mode="single-row", # 單選模式
        key=key_id
    )
    
    st.markdown(f"""
    <div class="metric-container" style="border-left: 5px solid {color_hex};">
        <div class="metric-item">
            <div class="metric-label">{label_total}</div>
            <div class="metric-value" style="color: {color_hex};">{sum_data['total']}</div>
        </div>
        <div class="metric-item">
            <div class="metric-label">{label_avg}</div>
            <div class="metric-value">{sum_data['avg']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 若有選取，回傳選中的券商名稱
    if len(event.selection.rows) > 0:
        selected_idx = event.selection.rows[0]
        return df.iloc[selected_idx]['broker']
    return None

# ✅ 輔助函式：計算 KD, MACD, BB, RSI, MA
def calculate_technical_indicators(df):
    df = df.copy()
    
    # 1. 布林通道
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Low'] = df['BB_Mid'] - 2 * df['BB_Std']

    # 2. 計算 KD (9, 3, 3)
    rsv_period = 9
    df['9_High'] = df['High'].rolling(window=rsv_period).max()
    df['9_Low'] = df['Low'].rolling(window=rsv_period).min()
    df['RSV'] = 100 * ((df['Close'] - df['9_Low']) / (df['9_High'] - df['9_Low']))
    df['RSV'] = df['RSV'].fillna(50)
    
    k_list = []
    d_list = []
    k_prev = 50
    d_prev = 50
    for rsv in df['RSV']:
        if pd.isna(rsv):
            k_now = k_prev
            d_now = d_prev
        else:
            k_now = (2/3) * k_prev + (1/3) * rsv
            d_now = (2/3) * d_prev + (1/3) * k_now
        k_list.append(k_now)
        d_list.append(d_now)
        k_prev = k_now
        d_prev = d_now
        
    df['K'] = k_list
    df['D'] = d_list

    # 3. 計算 MACD (12, 26, 9)
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = 2 * (df['DIF'] - df['DEA'])

    # 4. [NEW] 計算 RSI (6日)
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=5, adjust=False).mean() # com=5 means span=6
    ema_down = down.ewm(com=5, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))

    # 5. [NEW] 計算更多均線
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['MA240'] = df['Close'].rolling(window=240).mean()
    
    return df

# ✅ [NEW] 週期轉換函式 (日 -> 週/月)
def resample_data(df, period):
    if period == '日K':
        return df
    
    df = df.copy()
    # 確保索引是 datetime
    df.index = pd.to_datetime(df['DateStr'])
    
    # 設定 Resample 規則: 週K(W-MON:週一為始), 月K(ME:月底)
    rule = 'W-MON' if period == '週K' else 'ME'
    
    # 定義聚合邏輯
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    
    # 執行轉換
    resampled = df.resample(rule).agg(agg_dict).dropna()
    resampled['DateStr'] = resampled.index.strftime('%Y-%m-%d')
    resampled = resampled.reset_index(drop=True)
    
    # 重新計算技術指標 (因為均線、KD等要在新週期下計算才正確)
    resampled = calculate_technical_indicators(resampled)
    return resampled

# ================= 3. 爬蟲核心 =================

@st.cache_resource
def get_driver_path():
    return ChromeDriverManager().install()

def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    if shutil.which("chromium"):
        options.binary_location = shutil.which("chromium")
    elif shutil.which("chromium-browser"):
        options.binary_location = shutil.which("chromium-browser")
        
    if shutil.which("chromedriver"):
        service = Service(shutil.which("chromedriver"))
    else:
        service = Service(get_driver_path())

    driver = webdriver.Chrome(service=service, options=options)
    return driver

# ✅ [NEW] Wantgoo 爬蟲函式 (使用 SeleniumBase)
@st.cache_data(persist="disk", ttl=3600)
def get_wantgoo_trend_data(stock_id):
    url = f"https://www.wantgoo.com/stock/{stock_id}/major-investors/main-trend"
    
    # 啟動虛擬螢幕 (防止在無頭模式下報錯)
    try:
        display = Display(visible=0, size=(1920, 1080))
        display.start()
    except Exception as e:
        print(f"Virtual Display Start Error (Ignorable on some envs): {e}")

    result_data = []

    try:
        # 使用 SeleniumBase (UC Mode)
        with SB(uc=True, test=True, headless=True, locale_code="zh-TW") as sb:
            print(f"正在前往: {url}")
            sb.uc_open_with_reconnect(url, reconnect_time=3)
            
            # --- 破解 Cloudflare ---
            print("正在等待 Cloudflare 驗證...")
            for _ in range(3):
                if "Just a moment" in sb.get_title() or "Access denied" in sb.get_title():
                    print("偵測到驗證頁面，正在嘗試繞過...")
                    sb.uc_gui_click_captcha()
                    sb.sleep(5)
                else:
                    break
            
            # --- 抓取資料 ---
            print("正在等待表格載入...")
            
            try:
                # 等待表格出現
                sb.wait_for_element("main table", timeout=15)
                rows = sb.find_elements("main table tbody tr")
                
                for row in rows:
                    cols = row.find_elements(by="tag name", value="td")
                    if len(cols) >= 6:
                        date_val = cols[0].text.strip() # e.g. "01/12"
                        buy_sell = cols[2].text.strip().replace(',', '')
                        count_diff = cols[3].text.strip().replace(',', '')
                        con_5 = cols[4].text.strip().replace('%', '')
                        con_20 = cols[5].text.strip().replace('%', '')
                        
                        # 日期處理：Wantgoo 只有月/日，需加上年份
                        # 簡單邏輯：假設資料是最近的，若月份比當前月份大很多，可能是去年
                        try:
                            now = datetime.now()
                            dt_temp = datetime.strptime(date_val, "%m/%d")
                            year = now.year
                            # 如果現在是 1月，但資料是 12月，則年份減 1
                            if now.month == 1 and dt_temp.month == 12:
                                year -= 1
                            # 如果現在是 12月，但資料是 1月 (不太可能發生，除非未來)，則年份加 1
                            
                            date_str = f"{year}-{dt_temp.month:02d}-{dt_temp.day:02d}"
                        except:
                            date_str = None

                        if date_str:
                            result_data.append({
                                "DateStr": date_str,
                                "買賣超": float(buy_sell) if buy_sell.replace('-','').isdigit() else 0,
                                "家數差": float(count_diff) if count_diff.replace('-','').isdigit() else 0,
                                "5日集中": float(con_5) if con_5.replace('-','').replace('.','').isdigit() else 0,
                                "20日集中": float(con_20) if con_20.replace('-','').replace('.','').isdigit() else 0
                            })
                            
            except Exception as e:
                print(f"表格讀取錯誤: {e}")

    except Exception as e:
        print(f"SeleniumBase 執行錯誤: {e}")
    
    finally:
        try:
            display.stop()
        except:
            pass

    if result_data:
        return pd.DataFrame(result_data).sort_values("DateStr")
    return None

def calculate_date_range(stock_id, days):
    try:
        adj_days = days
        if days >= 120:
            adj_days = days - 1
            
        ticker = f"{stock_id}.TW"
        df = yf.Ticker(ticker).history(period=f"{max(adj_days + 60, 200)}d")
        
        if df.empty:
            ticker = f"{stock_id}.TWO"
            df = yf.Ticker(ticker).history(period=f"{max(adj_days + 60, 200)}d")
            
        if df.empty:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=adj_days * 1.5)
            return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
            
        df_target = df.tail(adj_days)
        start_date = df_target.index[0].strftime('%Y-%m-%d')
        end_date = df_target.index[-1].strftime('%Y-%m-%d')
        return start_date, end_date
    except:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

# ✅ 爬取三大法人資料
@st.cache_data(persist="disk", ttl=21600)
def get_institutional_data(stock_id, start_date, end_date):
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[8]/td[1]")))
        html = driver.page_source
        tables = pd.read_html(StringIO(html))
        
        target_df = None
        for df in tables:
            if df.astype(str).apply(lambda x: x.str.contains('外資買賣超', na=False)).any().any():
                target_df = df
                break
        
        if target_df is not None:
            if len(target_df.columns) >= 4:
                clean_df = target_df.iloc[:, [0, 1, 2, 3]].copy()
                clean_df.columns = ['日期', '外資買賣超', '投信買賣超', '自營商買賣超']
                
                clean_df = clean_df[clean_df['日期'].apply(is_roc_date)]
                
                for col in ['外資買賣超', '投信買賣超', '自營商買賣超']:
                    clean_df[col] = clean_df[col].astype(str).str.replace(',', '').str.replace('+', '').str.replace('nan', '0')
                    clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)

                clean_df['DateStr'] = clean_df['日期'].apply(roc_to_datestr)
                return clean_df.dropna(subset=['DateStr'])
    except:
        pass
    finally:
        driver.quit()
    return None

# ✅ 爬取融資融券資料
@st.cache_data(persist="disk", ttl=21600)
def get_margin_data(stock_id, start_date, end_date):
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcn/zcn.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[8]/td[1]")))
        html = driver.page_source
        tables = pd.read_html(StringIO(html))
        
        target_df = None
        for df in tables:
            if df.astype(str).apply(lambda x: x.str.contains('融資餘額', na=False)).any().any():
                target_df = df
                break
        
        if target_df is not None:
            if len(target_df.columns) >= 13:
                clean_df = target_df.iloc[:, [0, 4, 5, 11, 12]].copy()
                clean_df.columns = ['日期', '融資餘額', '融資增減', '融券餘額', '融券增減']
                
                clean_df = clean_df[clean_df['日期'].apply(is_roc_date)]
                
                for col in ['融資餘額', '融資增減', '融券餘額', '融券增減']:
                    clean_df[col] = clean_df[col].astype(str).str.replace(',', '').str.replace('+', '').str.replace('nan', '0')
                    clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
                
                clean_df['DateStr'] = clean_df['日期'].apply(roc_to_datestr)
                return clean_df.dropna(subset=['DateStr'])
    except:
        pass
    finally:
        driver.quit()
    return None

# ✅ [FIX] 將 get_real_data_matrix 移到最上方
@st.cache_data(persist="disk", ttl=604800)
def get_real_data_matrix(stock_id, start_date, end_date, refresh_nonce=0):
    driver = get_driver()
    base_url = "https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco.djhtm"
    url = f"{base_url}?a={stock_id}&e={start_date}&f={end_date}"

    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '買超券商')]"))
            )
        except:
            return None, None, None, None, None, url

        html = driver.page_source
        tables = pd.read_html(StringIO(html), match="買超券商")
        if not tables: return None, None, None, None, None, url
        df = tables[0]
        
        header_row = -1
        for i, row in df.iterrows():
            row_str = row.astype(str).values
            if "買超券商" in row_str and "賣超券商" in row_str:
                header_row = i
                break
        if header_row == -1: return None, None, None, None, None, url

        broker_info = {}
        try:
            links = driver.find_elements(By.XPATH, "//table//a[contains(@href, 'zco0/zco0.djhtm')]")
            for link in links:
                name = normalize_name(link.text)
                href = link.get_attribute('href')
                if name and href:
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    if 'b' in params and 'BHID' in params:
                        broker_info[name] = {'b': params['b'][0], 'BHID': params['BHID'][0]}
        except: pass

        sum_buy = {"total": "0", "avg": "0"}
        sum_sell = {"total": "0", "avg": "0"}
        
        try:
            total_buy_elem = driver.find_element(By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[22]/td[2]")
            sum_buy['total'] = total_buy_elem.text.strip()
            avg_buy_elem = driver.find_element(By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[23]/td[2]")
            sum_buy['avg'] = avg_buy_elem.text.strip()
            total_sell_elem = driver.find_element(By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[22]/td[4]")
            sum_sell['total'] = total_sell_elem.text.strip()
            avg_sell_elem = driver.find_element(By.XPATH, "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[23]/td[4]")
            sum_sell['avg'] = avg_sell_elem.text.strip()
        except: pass

        df_clean = df.iloc[header_row+1:].copy()
        df_buy = df_clean.iloc[:, [0, 1, 2, 3, 4]].copy()
        df_buy.columns = ['broker', 'buy', 'sell', 'net', 'pct']
        df_sell = df_clean.iloc[:, [5, 6, 7, 8, 9]].copy()
        df_sell.columns = ['broker', 'buy', 'sell', 'net', 'pct']

        def clean_sub_df(d):
            d = d.dropna(subset=['broker'])
            mask = d['broker'].astype(str).str.contains("合計|平均|買超券商|賣超券商", na=False)
            d = d[~mask]
            for col in ['buy', 'sell', 'net']:
                d[col] = d[col].astype(str).str.replace(',', '', regex=False).str.replace('+', '', regex=False).str.replace('nan', '', regex=False)
                d[col] = pd.to_numeric(d[col], errors='coerce').fillna(0).astype(int)
            return d

        df_buy = clean_sub_df(df_buy)
        df_sell = clean_sub_df(df_sell)
        df_buy = df_buy[df_buy['net'] > 0].sort_values('net', ascending=False).head(15).reset_index(drop=True)
        df_sell['abs_net'] = df_sell['net'].abs()
        df_sell = df_sell.sort_values('abs_net', ascending=False).head(15).drop(columns=['abs_net']).reset_index(drop=True)

        return df_buy, df_sell, sum_buy, sum_sell, broker_info, url
    except:
        return None, None, None, None, None, url
    finally:
        driver.quit()

@st.cache_data(persist="disk", ttl=604800)
def get_specific_broker_daily(stock_id, broker_key, start_date, end_date, refresh_nonce=0):
    BHID, b, c_val = broker_key
    driver = get_driver()
    base_url = "https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0/zco0.djhtm"
    target_url = f"{base_url}?A={stock_id}&BHID={BHID}&b={b}&C={c_val}&D={start_date}&E={end_date}&ver=V3"
    table_xpath = "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[6]/td/table"

    try:
        driver.get(target_url)
        all_dfs = []
        page_count = 0
        while page_count < 60:
            try:
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, table_xpath)))
            except: break

            try:
                target_table = driver.find_element(By.XPATH, table_xpath)
                table_html = target_table.get_attribute('outerHTML')
                tables = pd.read_html(StringIO(table_html))
                current_df = tables[0] if tables else None
            except:
                html = driver.page_source
                tables = pd.read_html(StringIO(html), match="日期")
                current_df = tables[0] if tables else None

            if current_df is not None: all_dfs.append(current_df)
            
            try:
                next_links = driver.find_elements(By.XPATH, "//a[contains(text(), '下一頁')]")
                if next_links and next_links[0].is_enabled():
                    next_links[0].click()
                    time.sleep(0.5) 
                    page_count += 1
                else: break 
            except: break

        if not all_dfs: return None, target_url

        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip().replace(" ", "") for c in df.columns]
        
        if '買賣超' not in df.columns and len(df.columns) >= 4:
            df = df.iloc[:, :4]
            df.columns = ['日期', '買進', '賣出', '買賣超']
            
        df = df[df['日期'] != '日期']
        for col in ['買進', '賣出', '買賣超']:
             df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('+', '').str.replace('nan', ''), errors='coerce').fillna(0)

        df['買賣超_Calc'] = df['買進'] - df['賣出']
        df['DateStr'] = df['日期'].apply(roc_to_datestr)
        df = df.dropna(subset=['DateStr']).sort_values('DateStr', ascending=True)
        return df, target_url
    except:
        return None, target_url
    finally:
        driver.quit()

# ✅ [FIX] 使用 Selenium + XPATH 爬取 Norway 神秘金字塔 StockHolders.aspx
@st.cache_data(persist="disk", ttl=604800)
def get_shareholding_data(stock_id: str):
    driver = get_driver()
    url = f"https://norway.twsthr.info/StockHolders.aspx?STOCK={stock_id}"
    
    try:
        driver.get(url)
        # 等待頁面載入
        time.sleep(2)
        
        # 1. 抓取【明細】表格 (Summary Table)
        # 使用使用者提供的 XPath (明細表格容器)
        # 目標: .../div[1]/table
        summary_xpath = "/html/body/form/div[4]/div/div[2]/div/div[2]/div/table/tbody/tr[4]/td/table/tbody/tr[2]/td/div[1]/table"
        summary_df = None
        try:
            tbl_summary = driver.find_element(By.XPATH, summary_xpath)
            summary_df = pd.read_html(StringIO(tbl_summary.get_attribute("outerHTML")))[0]
        except Exception:
            pass
            
        # 2. 抓取【分級比例】表格 (Ratio Table)
        # 先點擊【分級比例】頁籤 (li[3])
        # XPath: .../ul/li[3]/a/span
        ratio_df = None
        try:
            tab_ratio = driver.find_element(By.XPATH, "/html/body/form/div[4]/div/div[2]/div/div[2]/div/table/tbody/tr[4]/td/table/tbody/tr[1]/td/div/ul/li[3]/a/span")
            driver.execute_script("arguments[0].click();", tab_ratio)
            time.sleep(1) # 等待切換
            
            # 抓取分級比例表格
            # 目標: .../div[3]/table
            ratio_xpath = "/html/body/form/div[4]/div/div[2]/div/div[2]/div/table/tbody/tr[4]/td/table/tbody/tr[2]/td/div[3]/table"
            tbl_ratio = driver.find_element(By.XPATH, ratio_xpath)
            ratio_df = pd.read_html(StringIO(tbl_ratio.get_attribute("outerHTML")))[0]
        except Exception:
            pass

        return {"summary": summary_df, "ratio": ratio_df}

    except Exception:
        return {"summary": None, "ratio": None}
    finally:
        driver.quit()

# ✅ [FIX] 處理分級比例數據
def process_shareholding_df(ratio_df: pd.DataFrame, large_threshold: int, retail_threshold: int) -> pd.DataFrame | None:
    if ratio_df is None or ratio_df.empty: return None
    
    df = ratio_df.copy()
    
    # 根據用戶提供的資訊，分級比例表的欄位順序固定
    # Col 2: 資料日期
    # Col 3: 小於1張
    # Col 4: 1-5張
    # ...
    # Col 17: 1000張以上
    
    # 檢查是否至少有這麼多欄
    if df.shape[1] < 18: return None
    
    # 欄位映射 (Index -> 上界張數)
    # Col 3 (<1) -> 1
    # Col 4 (1-5) -> 5
    # Col 5 (5-10) -> 10
    # ...
    col_map = {
        3: 1, 4: 5, 5: 10, 6: 15, 7: 20, 8: 30, 9: 40, 10: 50,
        11: 100, 12: 200, 13: 400, 14: 600, 15: 800, 16: 1000, 17: 99999999 # 1000以上
    }
    
    # 找出日期欄位索引 (通常是 Col 2，索引為 2)
    # 我們遍歷每一列，嘗試解析日期
    out = []
    
    # 從資料列開始 (跳過標題，如果 read_html 沒抓對標題)
    # 假設前幾列可能是標題，找符合 YYYY-MM-DD 或 YYYYMMDD 的
    for i, row in df.iterrows():
        try:
            d_val = str(row.iloc[2]) # 假設日期在第 3 欄
            d_str = d_val.replace("/", "").replace("-", "")
            
            # 簡單驗證日期格式
            if not re.match(r"^\d{8}$", d_str): continue
            
            date_fmt = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
            
            large_ratio = 0.0
            retail_ratio = 0.0
            
            for col_idx, upper in col_map.items():
                val_str = str(row.iloc[col_idx]).replace("%", "").replace(",", "")
                val = float(val_str) if val_str != 'nan' else 0.0
                
                # 修正判斷邏輯：使用區間下界來判斷比較準確
                lower = 0
                if col_idx == 3: lower = 0
                elif col_idx == 4: lower = 1
                elif col_idx == 5: lower = 5
                elif col_idx == 6: lower = 10
                elif col_idx == 7: lower = 15
                elif col_idx == 8: lower = 20
                elif col_idx == 9: lower = 30
                elif col_idx == 10: lower = 40
                elif col_idx == 11: lower = 50
                elif col_idx == 12: lower = 100
                elif col_idx == 13: lower = 200
                elif col_idx == 14: lower = 400
                elif col_idx == 15: lower = 600
                elif col_idx == 16: lower = 800
                elif col_idx == 17: lower = 1000
                
                # 散戶條件：持股 < 散戶門檻
                # 只有當整個區間都在門檻之下才算 (即 上界 <= 門檻)
                if upper <= retail_threshold:
                    retail_ratio += val
                
                # 大戶條件：持股 >= 大戶門檻
                # 只有當整個區間都在門檻之上才算 (即 下界 >= 門檻)
                if lower >= large_threshold:
                    large_ratio += val
            
            out.append({
                "DateStr": date_fmt,
                "日期": date_fmt,
                "大戶持股(%)": round(large_ratio, 2),
                "散戶持股(%)": round(retail_ratio, 2),
                # 分級比例表沒有人數，設為 0
                "大戶人數": 0,
                "散戶人數": 0
            })
            
        except:
            continue
            
    if not out: return None
    return pd.DataFrame(out).sort_values("DateStr")

@st.cache_data(ttl=21600)
def get_stock_price(stock_id, refresh_nonce=0):
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    df = None
    for ticker in tickers_to_try:
        try:
            stock = yf.Ticker(ticker)
            temp_df = stock.history(period="2y")
            if not temp_df.empty:
                df = temp_df
                break
        except: continue
    if df is None or df.empty: return None

    try:
        df.index = df.index.tz_localize(None)
        df['DateStr'] = df.index.strftime('%Y-%m-%d')
        df = calculate_technical_indicators(df)
        return df
    except: return None

# ✅ 獲取所有股票選單
@st.cache_data
def get_all_stock_options():
    stock_options = []
    for code, info in twstock.codes.items():
        if info.type == "股票": 
            stock_options.append(f"{code} {info.name}")
    return stock_options

def get_stock_name(stock_id):
    try:
        if stock_id in twstock.codes:
            return twstock.codes[stock_id].name
        return ""
    except: return ""

# ================= 4. 介面邏輯 =================

# ✅ [FIX] 移除標題中的 (TradingView 風格)
st.title(f"📊 籌碼K線")

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

if "search_counts" not in st.session_state:
    st.session_state.search_counts = {}

# ✅ 統計天數選項（移出 sidebar，改由分點頁面控制）
days_map = {"1日": 1, "5日": 5, "10日": 10, "20日": 20, "40日": 40, "60日": 60, "120日": 120, "240日": 240}
if "days_label" not in st.session_state:
    st.session_state.days_label = "20日" # [FIX] 將預設改為 20日
if "selected_days" not in st.session_state:
    st.session_state.selected_days = days_map.get(st.session_state.days_label, 20) # [FIX] 同步將預設值改為 20

# ✅ [UI REFACTOR] 將側邊欄的輸入移至主畫面頂部的 Expander，確保手機版可見
with st.expander("🔍 股票搜尋與參數設定 (點擊收合)", expanded=True):
    all_stocks = get_all_stock_options()
    
    def get_sort_key(stock_str):
        code = stock_str.split()[0]
        count = st.session_state.search_counts.get(code, 0)
        return -count

    sorted_stocks = sorted(all_stocks, key=get_sort_key)
    
    # ✅ [FIX START] 修正股票選擇器重置問題
    # 檢查是否有上次選過的股票紀錄
    target_index = 0
    current_selection = st.session_state.get("stock_selector")
    
    if current_selection and current_selection in sorted_stocks:
        # 如果有上次的選擇，使用該選擇的索引
        target_index = sorted_stocks.index(current_selection)
    else:
        # 第一次執行或找不到時，預設找 2313
        for idx, s in enumerate(sorted_stocks):
            if s.startswith("2313"):
                target_index = idx
                break
                
    # 加上 key 參數以保持狀態
    stock_selection = st.selectbox(
        "搜尋股票", 
        options=sorted_stocks, 
        index=target_index, 
        placeholder="請輸入股票代號...",
        key="stock_selector"
    )
    # ✅ [FIX END]
    
    if stock_selection: stock_input = stock_selection.split()[0]
    else: stock_input = ""
    
    # 使用欄位排列按鈕
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔎 查詢", type="primary", use_container_width=True):
            if stock_input: st.session_state.search_counts[stock_input] = st.session_state.search_counts.get(stock_input, 0) + 1
            st.rerun()
            
    with col_btn2:
        if "refresh_nonce" not in st.session_state: st.session_state.refresh_nonce = 0
        if st.button("🔄 強制更新籌碼資料", use_container_width=True):
            st.session_state.refresh_nonce = int(time.time())
            st.rerun()

    st.caption(f"🕒 資料抓取時間: {current_time}")

if stock_input:
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    # ✅ 使用 session_state 的統計天數（由分點頁面控制）
    current_days_label = st.session_state.days_label
    selected_days = days_map.get(current_days_label, 20)
    st.session_state.selected_days = selected_days

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    with st.spinner(f"正在分析 {stock_display} ..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce)
        
    df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
    
    # ✅ [NEW] 預先定義 df_price 為日資料，確保所有分頁都能存取到基礎資料
    df_price = df_price_daily.copy() if df_price_daily is not None else None
    
    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date})")

        if 'current_page' not in st.session_state:
            st.session_state.current_page = "K線"
            
        # ✅ [NEW] 新增 "家數差" 分頁
        selected_page = st.radio(
            "功能分頁", 
            ["K線", "分點", "法人", "融資券", "大戶", "家數差"], 
            horizontal=True,
            label_visibility="collapsed",
            key="current_page"
        )

        def make_opts(height, title=None, time_visible=True, scale_mode="normal"):
            opts = {
                "layout": {"textColor": "white", "background": {"type": "solid", "color": "#131722"}},
                "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
                "grid": {"vertLines": {"color": "rgba(42, 46, 57, 0.5)"}, "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}},
                "timeScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)", 
                    "visible": time_visible, 
                    "timeVisible": False,
                },
                "rightPriceScale": {"borderColor": "rgba(197, 203, 206, 0.8)", "visible": True, "minimumWidth": 75},
                "crosshair": {
                    "mode": 1,
                    "vertLine": {"visible": True, "style": 0, "width": 1, "color": 'rgba(255, 255, 255, 0.4)', "labelVisible": True},
                    "horzLine": {
                        "visible": True, 
                        "labelVisible": True,
                        "labelBackgroundColor": '#1E88E5'
                    }
                },
                "height": height,
            }
            if scale_mode == "rsi":
                opts["rightPriceScale"] = {"visible": True, "autoScale": False, "mode": 0, "maxValue": 100, "minValue": 0, "minimumWidth": 75}
            if title:
                opts["watermark"] = {"visible": True, "fontSize": 20, "horzAlign": 'left', "vertAlign": 'top', "color": 'rgba(255, 255, 255, 0.2)', "text": title}
            
            return opts

        # ==================== Tab 1: K線 ====================
        if selected_page == "K線":
            kline_period = st.selectbox("K 線週期", ["日K", "週K", "月K"])
            
            if df_price_daily is not None:
                df_price = resample_data(df_price_daily, kline_period)

            ma_options_list = ["MA5", "MA10", "MA20", "MA60", "MA120", "MA240", "BB"]
            ma_default = ["MA5", "MA10", "MA20", "MA60"]
            
            selected_mas = st.multiselect(
                "選擇均線 / 布林通道",
                options=ma_options_list,
                default=ma_default
            )
            
            show_ma5 = "MA5" in selected_mas
            show_ma10 = "MA10" in selected_mas
            show_ma20 = "MA20" in selected_mas
            show_ma60 = "MA60" in selected_mas
            show_ma120 = "MA120" in selected_mas
            show_ma240 = "MA240" in selected_mas
            show_bb = "BB" in selected_mas
            
            if df_price is not None and not df_price.empty:
                charts_payload = []
                plot_df = df_price.copy()
                plot_df.index.name = None
                plot_df["Date"] = pd.to_datetime(plot_df["DateStr"], errors="coerce")
                plot_df = plot_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

                candlestick_data, ma5_data, ma10_data, ma20_data, ma60_data, ma120_data, ma240_data, bb_up_data, bb_low_data = [], [], [], [], [], [], [], [], []
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Open']) and not pd.isna(row['Close']):
                        candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                    if show_ma5 and not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                    if show_ma10 and not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                    if show_ma20 and not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})
                    if show_ma60 and not pd.isna(row['MA60']): ma60_data.append({"time": row['DateStr'], "value": float(row['MA60'])})
                    if show_ma120 and not pd.isna(row['MA120']): ma120_data.append({"time": row['DateStr'], "value": float(row['MA120'])})
                    if show_ma240 and not pd.isna(row['MA240']): ma240_data.append({"time": row['DateStr'], "value": float(row['MA240'])})
                    if show_bb and not pd.isna(row['BB_Up']): bb_up_data.append({"time": row['DateStr'], "value": float(row['BB_Up'])})
                    if show_bb and not pd.isna(row['BB_Low']): bb_low_data.append({"time": row['DateStr'], "value": float(row['BB_Low'])})

                ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False, "priceLineVisible": False}}]
                if show_ma5: main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
                if show_ma10: main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
                if show_ma20: main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})
                if show_ma60: main_series.append({"type": "Line", "data": ma60_data, "options": {**ma_opts, "color": "lime", "lineWidth": 2, "title": "MA60"}})
                if show_ma120: main_series.append({"type": "Line", "data": ma120_data, "options": {**ma_opts, "color": "gray", "title": "MA120"}})
                if show_ma240: main_series.append({"type": "Line", "data": ma240_data, "options": {**ma_opts, "color": "blue", "title": "MA240"}})
                if show_bb:
                    main_series.append({"type": "Line", "data": bb_up_data, "options": {**ma_opts, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB上"}})
                    main_series.append({"type": "Line", "data": bb_low_data, "options": {**ma_opts, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB下"}})
                
                charts_payload.append({"chart": make_opts(400, "股價", True), "series": main_series})

                vol_data = []
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Volume']): vol_data.append({"time": row['DateStr'], "value": float(row['Volume']), "color": COLOR_UP if row['Close']>=row['Open'] else COLOR_DOWN})
                charts_payload.append({"chart": make_opts(150, "成交量", False), "series": [{"type": "Histogram", "data": vol_data, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": "right", "title": "成交量", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}]})

                k_data, d_data = [], []
                if 'K' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['K']): k_data.append({"time": row['DateStr'], "value": float(row['K'])})
                        if not pd.isna(row['D']): d_data.append({"time": row['DateStr'], "value": float(row['D'])})
                    charts_payload.append({"chart": make_opts(150, "KD", False), "series": [
                        {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": d_data, "options": {"color": "cyan", "lineWidth": 1, "title": "D", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                    ]})

                dif_data, dea_data, hist_data = [], [], []
                if 'DIF' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['DIF']): dif_data.append({"time": row['DateStr'], "value": float(row['DIF'])})
                        if not pd.isna(row['DEA']): dea_data.append({"time": row['DateStr'], "value": float(row['DEA'])})
                        if not pd.isna(row['MACD_Hist']): hist_data.append({"time": row['DateStr'], "value": float(row['MACD_Hist']), "color": COLOR_UP if row['MACD_Hist']>=0 else COLOR_DOWN})
                    charts_payload.append({"chart": make_opts(150, "MACD", False), "series": [
                        {"type": "Histogram", "data": hist_data, "options": {"title": "柱", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": dif_data, "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": dea_data, "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                    ]})

                rsi_data, rsi_80, rsi_20 = [], [], []
                if 'RSI' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['RSI']): 
                            rsi_data.append({"time": row['DateStr'], "value": float(row['RSI'])})
                            rsi_80.append({"time": row['DateStr'], "value": 80})
                            rsi_20.append({"time": row['DateStr'], "value": 20})
                    charts_payload.append({"chart": make_opts(150, "RSI", False, scale_mode="rsi"), "series": [
                        {"type": "Line", "data": rsi_data, "options": {"color": "#AB47BC", "lineWidth": 1, "title": "RSI(6)", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": rsi_80, "options": {"color": "red", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}},
                        {"type": "Line", "data": rsi_20, "options": {"color": "green", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}}
                    ]})
                
                renderLightweightCharts(charts_payload, key="tab1_kline")

        # ==================== Tab 2: 分點 ====================
        if selected_page == "分點":
            col_chart, col_table = st.columns([3, 1])
            if "active_broker" not in st.session_state:
                st.session_state.active_broker = None
            if "last_buy" not in st.session_state: st.session_state.last_buy = None
            if "last_sell" not in st.session_state: st.session_state.last_sell = None

            with col_table:
                default_index = 3 
                try:
                    default_index = list(days_map.keys()).index(st.session_state.days_label)
                except:
                    default_index = 3

                st.selectbox(
                    "統計天數",
                    list(days_map.keys()),
                    index=default_index,
                    key="days_label" 
                )
                
                st.markdown("##### 區間前 15 大")
                t1, t2 = st.tabs(["🔴 買超", "🟢 賣超"])
                
                sel_buy = None
                sel_sell = None
                
                with t1: 
                    sel_buy = render_broker_table(df_buy, sum_buy, COLOR_UP, "🔴 買超前 15 大", key_id="buy_table")
                        
                with t2: 
                    sel_sell = render_broker_table(df_sell, sum_sell, COLOR_DOWN, "🟢 賣超前 15 大", key_id="sell_table")
                
                if sel_buy and sel_buy != st.session_state.last_buy:
                    st.session_state.active_broker = sel_buy
                    st.session_state.last_buy = sel_buy
                elif sel_sell and sel_sell != st.session_state.last_sell:
                    st.session_state.active_broker = sel_sell
                    st.session_state.last_sell = sel_sell

            with col_chart:
                c1, c2 = st.columns([1, 2])
                target_broker = st.session_state.active_broker
                if not target_broker:
                    brokers_list = list(dict.fromkeys(df_buy['broker'].tolist() + df_sell['broker'].tolist()))
                    if brokers_list:
                        target_broker = brokers_list[0]
                        st.session_state.active_broker = target_broker
                
                if target_broker:
                    st.markdown(f"### 目前檢視：{target_broker}")
                    merged_df = None
                    target_key = normalize_name(target_broker)
                    broker_params = None
                    if broker_info:
                        if target_key in broker_info: broker_params = broker_info[target_key]
                        else:
                            for k, v in broker_info.items():
                                if target_key in k or k in target_key:
                                    broker_params = v
                                    break
                                    
                    if broker_params:
                        long_start_date = df_price['DateStr'].iloc[0] 
                        long_end_date = df_price['DateStr'].iloc[-1] 
                        broker_key = (broker_params['BHID'], broker_params['b'], broker_params.get('C', '1'))
                        merged_key = (stock_input, broker_key, st.session_state.refresh_nonce, selected_days)

                        if st.session_state.get('merged_key') != merged_key:
                            with st.spinner(f"正在爬取 {target_broker} ..."):
                                broker_daily_df, detail_url = get_specific_broker_daily(stock_input, broker_key, long_start_date, long_end_date, st.session_state.refresh_nonce)
                                if broker_daily_df is not None and not broker_daily_df.empty:
                                    broker_daily_df = broker_daily_df.drop_duplicates(subset=["DateStr"], keep="last").sort_values('DateStr')
                                    merged_df = pd.merge(df_price, broker_daily_df, on='DateStr', how='left')
                                    merged_df['買賣超_Final'] = merged_df['買賣超_Calc'].fillna(0)
                                    st.session_state['merged_df'] = merged_df
                                    st.session_state['merged_key'] = merged_key
                                else:
                                    st.session_state.pop('merged_df', None)
                                    st.session_state['merged_key'] = merged_key
                                    st.warning("⚠️ 該券商明細抓取失敗")
                        else:
                            merged_df = st.session_state.get('merged_df')

                    charts_payload_broker = []
                    plot_df = merged_df if merged_df is not None else df_price
                    plot_df = plot_df.copy()
                    plot_df.index.name = None
                    plot_df["Date"] = pd.to_datetime(plot_df["DateStr"], errors="coerce")
                    plot_df = plot_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
                    if '買賣超_Final' in plot_df.columns: plot_df['cumulative_chip'] = plot_df['買賣超_Final'].fillna(0).cumsum()

                    candlestick_data = []
                    ma5_data, ma10_data, ma20_data = [], [], []
                    
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['Open']):
                            is_in_range = rank_start_date <= row['DateStr'] <= rank_end_date
                            item = {
                                "time": row['DateStr'],
                                "open": float(row['Open']),
                                "high": float(row['High']),
                                "low": float(row['Low']),
                                "close": float(row['Close'])
                            }
                            if row['Close'] >= row['Open']:
                                base_color = COLOR_UP
                                fade_color = 'rgba(239, 83, 80, 0.3)'
                            else:
                                base_color = COLOR_DOWN
                                fade_color = 'rgba(38, 166, 154, 0.3)'

                            if is_in_range:
                                item["color"] = base_color
                                item["borderColor"] = base_color
                                item["wickColor"] = base_color
                            else:
                                item["color"] = fade_color
                                item["borderColor"] = fade_color
                                item["wickColor"] = fade_color
                                
                            candlestick_data.append(item)
                            
                            if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                            if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                            if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})
                    
                    main_chart_series = []
                    main_chart_series.append({
                        "type": "Candlestick",
                        "data": candlestick_data,
                        "options": {
                            "upColor": COLOR_UP, 
                            "downColor": COLOR_DOWN, 
                            "borderUpColor": COLOR_UP, 
                            "borderDownColor": COLOR_DOWN, 
                            "wickUpColor": COLOR_UP, 
                            "wickDownColor": COLOR_DOWN, 
                            "lastValueVisible": False
                        }
                    })
                    
                    ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                    main_chart_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
                    main_chart_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
                    main_chart_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

                    charts_payload_broker.append({"chart": make_opts(400, "股價 (淺色為統計區間外)", True), "series": main_chart_series})
                    
                    if '買賣超_Final' in plot_df.columns:
                        chip_data, chip_cumulative_data = [], []
                        for i, row in plot_df.iterrows():
                            val = row.get('買賣超_Final')
                            is_in_range = rank_start_date <= row['DateStr'] <= rank_end_date
                            
                            if not pd.isna(val): 
                                if val > 0:
                                    c = COLOR_UP if is_in_range else 'rgba(239, 83, 80, 0.3)'
                                else:
                                    c = COLOR_DOWN if is_in_range else 'rgba(38, 166, 154, 0.3)'
                                    
                                chip_data.append({"time": row['DateStr'], "value": float(val), "color": c})
                                
                            cum_val = row.get('cumulative_chip')
                            if not pd.isna(cum_val): chip_cumulative_data.append({"time": row['DateStr'], "value": float(cum_val)})
                        
                        charts_payload_broker.append({"chart": make_opts(200, f"{target_broker} 買賣 (淺色為統計區間外)", False), "series": [
                            {"type": "Histogram", "data": chip_data, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                            {"type": "Line", "data": chip_cumulative_data, "options": {"title": "累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                        ]})
                    
                    renderLightweightCharts(charts_payload_broker, key=f"tab2_broker_{target_broker}")

        # ==================== Tab 3: 法人 ====================
        if selected_page == "法人":
            long_start_date = df_price['DateStr'].iloc[0] 
            long_end_date = df_price['DateStr'].iloc[-1] 
            inst_df = get_institutional_data(stock_input, long_start_date, long_end_date)
            plot_df = df_price.copy()
            plot_df.index.name = None 
            if inst_df is not None:
                plot_df = pd.merge(plot_df, inst_df, on='DateStr', how='left')
                for col in ['外資買賣超', '投信買賣超', '自營商買賣超']:
                    if col in plot_df.columns: plot_df[col] = plot_df[col].fillna(0)
                plot_df['cum_foreign'] = plot_df['外資買賣超'].cumsum()
                plot_df['cum_trust'] = plot_df['投信買賣超'].cumsum()
                plot_df['cum_dealer'] = plot_df['自營商買賣超'].cumsum()
                plot_df['total_inst'] = plot_df['外資買賣超'] + plot_df['投信買賣超'] + plot_df['自營商買賣超']
                plot_df['cum_total'] = plot_df['total_inst'].cumsum()

            charts_payload_inst = []
            candlestick_data = []
            ma5_data, ma10_data, ma20_data = [], [], []
            
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})

            ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
            main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

            charts_payload_inst.append({"chart": make_opts(400, "股價", True), "series": main_series})

            if '外資買賣超' in plot_df.columns:
                f_hist, f_line = [], []
                t_hist, t_line = [], []
                d_hist, d_line = [], []
                total_line, total_hist = [], []
                for i, row in plot_df.iterrows():
                    f_val, f_cum = row['外資買賣超'], row['cum_foreign']
                    t_val, t_cum = row['投信買賣超'], row['cum_trust']
                    d_val, d_cum = row['自營商買賣超'], row['cum_dealer']
                    total_val, total_cum = row['total_inst'], row['cum_total']
                    
                    f_hist.append({"time": row['DateStr'], "value": float(f_val), "color": COLOR_UP if f_val>0 else COLOR_DOWN})
                    f_line.append({"time": row['DateStr'], "value": float(f_cum)})
                    t_hist.append({"time": row['DateStr'], "value": float(t_val), "color": COLOR_UP if t_val>0 else COLOR_DOWN})
                    t_line.append({"time": row['DateStr'], "value": float(t_cum)})
                    d_hist.append({"time": row['DateStr'], "value": float(d_val), "color": COLOR_UP if d_val>0 else COLOR_DOWN})
                    d_line.append({"time": row['DateStr'], "value": float(d_cum)})
                    total_hist.append({"time": row['DateStr'], "value": float(total_val), "color": COLOR_UP if total_val>0 else COLOR_DOWN})
                    total_line.append({"time": row['DateStr'], "value": float(total_cum)})

                charts_payload_inst.append({"chart": make_opts(200, "三大法人合計", False), "series": [
                    {"type": "Histogram", "data": total_hist, "options": {"title": "合計買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": total_line, "options": {"title": "合計累", "color": "white", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                
                charts_payload_inst.append({"chart": make_opts(150, "外資", False), "series": [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": f_line, "options": {"title": "累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "投信", False), "series": [
                    {"type": "Histogram", "data": t_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": t_line, "options": {"title": "累積", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "自營商", False), "series": [
                    {"type": "Histogram", "data": d_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": d_line, "options": {"title": "累積", "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
            renderLightweightCharts(charts_payload_inst, key="tab3_inst")

        # ==================== Tab 4: 融資券 ====================
        if selected_page == "融資券":
            long_start_date = df_price['DateStr'].iloc[0] 
            long_end_date = df_price['DateStr'].iloc[-1] 
            margin_df = get_margin_data(stock_input, long_start_date, long_end_date)
            plot_df = df_price.copy()
            plot_df.index.name = None 
            if margin_df is not None:
                plot_df = pd.merge(plot_df, margin_df, on='DateStr', how='left')
                plot_df['融資餘額'] = plot_df['融資餘額'].ffill()
                plot_df['融券餘額'] = plot_df['融券餘額'].ffill()
                plot_df['融資增減'] = plot_df['融資增減'].fillna(0)
                plot_df['融券增減'] = plot_df['融券增減'].fillna(0)

            charts_payload_margin = []
            candlestick_data = []
            ma5_data, ma10_data, ma20_data = [], [], []

            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})

            ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
            main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

            charts_payload_margin.append({"chart": make_opts(400, "股價", True), "series": main_series})

            if '融資餘額' in plot_df.columns:
                ml_bal, ml_diff, ms_bal, ms_diff = [], [], [], []
                for i, row in plot_df.iterrows():
                    val_mb = row.get('融資餘額')
                    val_md = row.get('融資增減')
                    val_sb = row.get('融券餘額')
                    val_sd = row.get('融券增減')
                    if not pd.isna(val_mb): ml_bal.append({"time": row['DateStr'], "value": float(val_mb)})
                    if not pd.isna(val_md): 
                        color = COLOR_UP if val_md > 0 else (COLOR_DOWN if val_md < 0 else "gray")
                        ml_diff.append({"time": row['DateStr'], "value": float(val_md), "color": color})
                    if not pd.isna(val_sb): ms_bal.append({"time": row['DateStr'], "value": float(val_sb)})
                    if not pd.isna(val_sd): 
                        color = COLOR_UP if val_sd > 0 else (COLOR_DOWN if val_sd < 0 else "gray")
                        ms_diff.append({"time": row['DateStr'], "value": float(val_sd), "color": color})

                charts_payload_margin.append({"chart": make_opts(150, "融資", False), "series": [
                    {"type": "Histogram", "data": ml_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": ml_bal, "options": {"title": "餘額", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_margin.append({"chart": make_opts(150, "融券", False), "series": [
                    {"type": "Histogram", "data": ms_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": ms_bal, "options": {"title": "餘額", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})

            renderLightweightCharts(charts_payload_margin, key="tab4_margin")
            
            if margin_df is not None and not margin_df.empty:
                st.markdown("#### 近 10 日融資融券詳細數據")
                display_margin = margin_df.sort_values("DateStr").tail(10).iloc[::-1]
                display_margin = display_margin[['日期', '融資餘額', '融資增減', '融券餘額', '融券增減']]
                def highlight_margin(df):
                    attr = pd.DataFrame('', index=df.index, columns=df.columns)
                    c_up = f'color: {COLOR_UP}'   
                    c_down = f'color: {COLOR_DOWN}'
                    mask_m_up = df['融資增減'] > 0
                    mask_m_down = df['融資增減'] < 0
                    attr.loc[mask_m_up, ['融資增減']] = c_up
                    attr.loc[mask_m_down, ['融資增減']] = c_down
                    mask_s_up = df['融券增減'] > 0
                    mask_s_down = df['融券增減'] < 0
                    attr.loc[mask_s_up, ['融券增減']] = c_up
                    attr.loc[mask_s_down, ['融券增減']] = c_down
                    return attr

                st.dataframe(display_margin.style.apply(highlight_margin, axis=None), use_container_width=True, hide_index=True)

        # ==================== Tab 5: 大戶 (集保分佈) ====================
        if selected_page == "大戶":
            LOT_CHOICES = [10, 50, 100, 200, 400, 600, 800, 1000]
            if "retail_lot" not in st.session_state: st.session_state.retail_lot = 50
            if "large_lot" not in st.session_state: st.session_state.large_lot = 400

            valid_large_opts = [x for x in LOT_CHOICES if x > st.session_state.retail_lot]
            if not valid_large_opts: valid_large_opts = [1000] 
            
            valid_retail_opts = [x for x in LOT_CHOICES if x < st.session_state.large_lot]
            if not valid_retail_opts: valid_retail_opts = [10] 

            c1, c2 = st.columns(2)
            with c1:
                current_large = st.session_state.large_lot
                if current_large not in valid_large_opts: current_large = valid_large_opts[0]
                st.session_state.large_lot = st.selectbox(
                    "大戶持股標準 (>= 張)", 
                    options=valid_large_opts, 
                    index=valid_large_opts.index(current_large),
                    key="sb_large"
                )

            with c2:
                current_retail = st.session_state.retail_lot
                if current_retail not in valid_retail_opts: current_retail = valid_retail_opts[0]
                st.session_state.retail_lot = st.selectbox(
                    "散戶持股標準 (< 張)", 
                    options=valid_retail_opts, 
                    index=valid_retail_opts.index(current_retail),
                    key="sb_retail"
                )

            raw_holder_df = get_shareholding_data(stock_input)
            
            if raw_holder_df is None or (isinstance(raw_holder_df, dict) and raw_holder_df.get('ratio') is None):
                st.warning("⚠️ 查無集保分佈資料，可能為 ETF 或資料來源暫時無法存取。")
            else:
                df_ratio = raw_holder_df.get("ratio")
                holder_df = process_shareholding_df(df_ratio, st.session_state.large_lot, st.session_state.retail_lot)
                
                if holder_df is not None and not holder_df.empty:
                    display_df = holder_df.copy()
                    display_df['大戶增減'] = display_df['大戶持股(%)'].diff()
                    display_df['散戶增減'] = display_df['散戶持股(%)'].diff()
                    
                    display_df_show = display_df.sort_values("日期", ascending=False).reset_index(drop=True)
                    
                    def highlight_changes(df):
                        attr = pd.DataFrame('', index=df.index, columns=df.columns)
                        c_up = f'color: {COLOR_UP}'
                        c_down = f'color: {COLOR_DOWN}'
                        mask_up = df['大戶增減'] > 0
                        mask_down = df['大戶增減'] < 0
                        attr.loc[mask_up, ['大戶持股(%)', '大戶增減']] = c_up
                        attr.loc[mask_down, ['大戶持股(%)', '大戶增減']] = c_down
                        mask_up_r = df['散戶增減'] > 0
                        mask_down_r = df['散戶增減'] < 0
                        attr.loc[mask_up_r, ['散戶持股(%)', '散戶增減']] = c_up
                        attr.loc[mask_down_r, ['散戶持股(%)', '散戶增減']] = c_down
                        return attr

                    st.markdown("#### 集保戶股權分散表")
                    st.dataframe(
                        display_df_show[['日期', '大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']]
                        .style.apply(highlight_changes, axis=None)
                        .format("{:.2f}", subset=['大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']), 
                        use_container_width=True, 
                        height=400,
                        hide_index=True
                    )
                    
                    df_price_daily['_dt'] = pd.to_datetime(df_price_daily['DateStr'])
                    holder_df['_dt'] = pd.to_datetime(holder_df['DateStr'])
                    
                    holder_df = holder_df.sort_values('_dt')
                    df_price_daily = df_price_daily.sort_values('_dt')
                    
                    chart_df = pd.merge_asof(
                        holder_df,
                        df_price_daily[['_dt', 'Close']], 
                        on='_dt',
                        direction='backward' 
                    )
                    
                    l_data, r_data, p_data = [], [], []
                    for i, row in chart_df.iterrows():
                        if not pd.isna(row['大戶持股(%)']): l_data.append({"time": row['DateStr'], "value": row['大戶持股(%)']})
                        if not pd.isna(row['散戶持股(%)']): r_data.append({"time": row['DateStr'], "value": row['散戶持股(%)']})
                        if not pd.isna(row['Close']): p_data.append({"time": row['DateStr'], "value": row['Close']})
                        
                    holder_payload = []
                    holder_series = [
                        {"type": "Line", "data": l_data, "options": {"title": f"大戶(>{st.session_state.large_lot})%", "color": "red", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": False, "priceLineVisible": False}},
                        {"type": "Line", "data": r_data, "options": {"title": f"散戶(<{st.session_state.retail_lot})%", "color": "green", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": False, "priceLineVisible": False}},
                        {"type": "Line", "data": p_data, "options": {"title": "股價", "color": "white", "lineWidth": 1, "priceScaleId": "right", "lineStyle": 2, "lastValueVisible": False, "priceLineVisible": False}} 
                    ]
                    
                    holder_opts = make_opts(400, "籌碼分佈 vs 股價", True)
                    holder_opts["leftPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    holder_opts["rightPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    
                    holder_payload.append({"chart": holder_opts, "series": holder_series})
                    renderLightweightCharts(holder_payload, key="tab5_holder")

        # ==================== Tab 6: 家數差 (Wantgoo) ====================
        if selected_page == "家數差":
            with st.spinner("正在讀取買賣家數差資料 (可能需要幾秒鐘繞過驗證)..."):
                wg_df = get_wantgoo_trend_data(stock_input)
            
            if wg_df is not None and not wg_df.empty:
                # 合併股價資料
                plot_df = df_price.copy()
                plot_df.index.name = None 
                
                plot_df = pd.merge(plot_df, wg_df, on='DateStr', how='left')
                
                # 繪圖數據準備
                charts_payload_wg = []
                candlestick_data = []
                diff_hist = []
                con5_line, con20_line = [], []
                ma5_data = []

                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Open']): 
                        candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                    
                    if not pd.isna(row['MA5']): 
                        ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})

                    # 家數差數據
                    val_diff = row.get('家數差')
                    if not pd.isna(val_diff):
                        # 邏輯：家數差 > 0 (買的人多，籌碼散) -> 綠色(壞) ? 
                        # 或者：家數差 > 0 (紅色)? 這裡沿用 Wantgoo 習慣：正數紅色，負數綠色 (但需注意解讀)
                        # 通常：家數差為負數代表籌碼集中(好)，為正數代表籌碼發散(壞)
                        color = COLOR_UP if val_diff > 0 else COLOR_DOWN
                        diff_hist.append({"time": row['DateStr'], "value": float(val_diff), "color": color})

                    val_c5 = row.get('5日集中')
                    val_c20 = row.get('20日集中')
                    if not pd.isna(val_c5): con5_line.append({"time": row['DateStr'], "value": float(val_c5)})
                    if not pd.isna(val_c20): con20_line.append({"time": row['DateStr'], "value": float(val_c20)})

                # 1. 主圖：K線 + MA5
                ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
                main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
                
                charts_payload_wg.append({"chart": make_opts(400, "股價", True), "series": main_series})

                # 2. 副圖：家數差
                charts_payload_wg.append({"chart": make_opts(150, "買賣家數差", False), "series": [
                    {"type": "Histogram", "data": diff_hist, "options": {"title": "家數差", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                ]})

                # 3. 副圖：集中度
                charts_payload_wg.append({"chart": make_opts(150, "籌碼集中度(%)", False), "series": [
                    {"type": "Line", "data": con5_line, "options": {"title": "5日集中", "color": "#FFD700", "lineWidth": 1, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": con20_line, "options": {"title": "20日集中", "color": "#00FFFF", "lineWidth": 1, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})

                renderLightweightCharts(charts_payload_wg, key="tab6_wg")

                st.markdown("#### 買賣家數差與籌碼集中度明細")
                # 顯示表格 (倒序)
                display_wg = wg_df.sort_values("DateStr", ascending=False).reset_index(drop=True)
                
                # 樣式設定
                def highlight_wg(df):
                    attr = pd.DataFrame('', index=df.index, columns=df.columns)
                    c_up = f'color: {COLOR_UP}'
                    c_down = f'color: {COLOR_DOWN}'
                    
                    mask_up = df['家數差'] > 0
                    mask_down = df['家數差'] < 0
                    attr.loc[mask_up, ['家數差']] = c_up
                    attr.loc[mask_down, ['家數差']] = c_down
                    
                    mask_up_5 = df['5日集中'] > 0
                    mask_down_5 = df['5日集中'] < 0
                    attr.loc[mask_up_5, ['5日集中']] = c_up
                    attr.loc[mask_down_5, ['5日集中']] = c_down
                    
                    return attr

                st.dataframe(
                    display_wg.style.apply(highlight_wg, axis=None).format("{:.2f}", subset=['5日集中', '20日集中']),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("⚠️ 無法取得家數差資料，請稍後再試或確認該股票是否有資料。")

    else:
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n2. 股票代號輸入錯誤。\n3. Yahoo API 暫時連線失敗，請稍後再試。")

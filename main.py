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
import subprocess
import sys
import os
import tempfile
import random
import traceback

# ✅ TradingView 圖表套件
from streamlit_lightweight_charts import renderLightweightCharts

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

# ✅ [FIX] Move make_opts to Global Scope to avoid NameError
def make_opts(height, title=None, time_visible=True, scale_mode="normal"):
    opts = {
        "layout": {"textColor": "white", "background": {"type": "solid", "color": "#131722"}},
        "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
        "grid": {"vertLines": {"color": "rgba(42, 46, 57, 0.5)"}, "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}},
        "timeScale": {
            "borderColor": "rgba(197, 203, 206, 0.8)", 
            "visible": time_visible, 
            "timeVisible": True, # 分時資料需要顯示時間
            "secondsVisible": False
        },
        # ✅ [FIX] Add autoScale: True to solve 'cut off' issue for small heights
        "rightPriceScale": {"borderColor": "rgba(197, 203, 206, 0.8)", "visible": True, "minimumWidth": 75, "autoScale": True},
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

# ✅ 爬取融資融券資料 (完全複製您的版本)
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

# ✅ [MODIFIED] 將 Stock Price 恢復為 10 年
@st.cache_data(ttl=21600)
def get_stock_price(stock_id, refresh_nonce=0):
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    df = None
    for ticker in tickers_to_try:
        try:
            stock = yf.Ticker(ticker)
            temp_df = stock.history(period="10y") # 修正回 10年
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

# ✅ [NEW] 獲取分時 K 線資料 (5m, 15m, 30m, 60m)
@st.cache_data(ttl=300) # 快取時間短一點，因為是盤中資料
def get_intraday_data(stock_id, interval):
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    df = None
    
    # Mapping selector to yfinance interval
    interval_map = {
        "5分": "5m",
        "15分": "15m",
        "30分": "30m",
        "60分": "60m"
    }
    yf_interval = interval_map.get(interval)
    if not yf_interval: return None

    for ticker in tickers_to_try:
        try:
            stock = yf.Ticker(ticker)
            # intraday data only available for last 60 days
            temp_df = stock.history(period="60d", interval=yf_interval)
            if not temp_df.empty:
                df = temp_df
                break
        except: continue
        
    if df is None or df.empty: return None

    try:
        # 分時資料需要保留時間資訊
        # yfinance index usually is tz-aware
        if df.index.tz is not None:
             df.index = df.index.tz_convert('Asia/Taipei').tz_localize(None)
        
        df['DateStr'] = df.index.strftime('%Y-%m-%d %H:%M')
        df = calculate_technical_indicators(df)
        return df
    except: return None

# ✅ [NEW] 新增玩股網「主力買賣超與家數差」爬蟲 (修正版：Permission Denied Fix + Subprocess)
@st.cache_data(ttl=21600, show_spinner=False)
def get_wantgoo_data(stock_id, refresh_nonce):
    """
    爬取玩股網主力買賣超資料。
    修正 Permission Denied: 自動在 /tmp/sb_lib 安裝 seleniumbase，
    並強制子程序載入該路徑，確保 uc_driver 可寫入。
    """
    
    # 0. 準備可寫入的 Library 路徑 (解決 Streamlit Cloud 唯讀權限問題)
    SB_LIB_PATH = "/tmp/sb_lib"
    os.makedirs(SB_LIB_PATH, exist_ok=True)
    
    # 檢查是否已安裝 seleniumbase 到暫存區，若無則安裝
    # 注意：使用 --no-deps 避免安裝依賴導致時間過長，假設 pandas/lxml 系統已有或另外裝
    # 但為了保險，這裡只指定 target
    if not os.path.exists(os.path.join(SB_LIB_PATH, "seleniumbase")):
        try:
            # 安裝 seleniumbase 到 /tmp/sb_lib
            subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "seleniumbase", "pandas", "lxml", 
                "-t", SB_LIB_PATH, 
                "--no-cache-dir", "--quiet"
            ], check=True)
        except subprocess.CalledProcessError:
            pass # 嘗試繼續，也許系統已經有了

    # 1. 建立爬蟲腳本字串
    # 關鍵修正：在 import 之前，將 SB_LIB_PATH 加入 sys.path
    scraper_script = r"""
import sys
import os

# ✅ [CRITICAL FIX] 強制優先載入 /tmp/sb_lib 中的 seleniumbase
# 這樣它就會去 /tmp/sb_lib/seleniumbase/drivers 下找驅動，而我們對該路徑有寫入權限
sb_lib_path = "/tmp/sb_lib"
if sb_lib_path not in sys.path:
    sys.path.insert(0, sb_lib_path)

import pandas as pd
# 嘗試 import SB，如果失敗可能是安裝問題
try:
    from seleniumbase import SB
except ImportError:
    # Fallback: 如果 /tmp 載入失敗，嘗試系統預設
    try:
        from seleniumbase import SB
    except ImportError:
        sys.stderr.write("SeleniumBase not found in /tmp or system.\n")
        sys.exit(1)

from io import StringIO
import random
import time
import tempfile
import traceback

# 從環境變數或參數獲取
stock_id = "{stock_id}"
url = f"https://www.wantgoo.com/stock/{stock_id}/major-investors/main-trend"
MAX_RETRY = 4

def log_err(msg):
    sys.stderr.write(f"[ChildProcess] {msg}\n")

def main():
    try:
        # 使用 SeleniumBase (uc=True) 繞過防護
        # headless=True 在 Streamlit Cloud 是必須的
        with SB(uc=True, headless=True, locale_code="zh-TW") as sb:
            for attempt in range(1, MAX_RETRY + 1):
                try:
                    # 使用更強的連線方式
                    sb.uc_open_with_reconnect(url, reconnect_time=4)
                    
                    # 嘗試偵測常見的 Cloudflare 標題
                    if "Just a moment" in sb.get_title():
                        log_err("Detected Cloudflare interstitial, waiting...")
                        sb.sleep(6)
                    
                    # ✅ [關鍵] 等待表格出現
                    try:
                        sb.wait_for_element("table", timeout=15)
                    except:
                        log_err("Table element not found instantly, waiting more...")
                        sb.sleep(3)

                    html = sb.get_page_source()
                    
                    # 解析表格
                    try:
                        dfs = pd.read_html(StringIO(html))
                    except ValueError:
                        dfs = []

                    target_df = None
                    for df in dfs:
                        # 檢查關鍵欄位 (模糊比對，去除空白)
                        cols = [str(c).strip() for c in df.columns]
                        if any("買賣超" in c for c in cols) and any("家數差" in c for c in cols):
                            target_df = df
                            break
                    
                    if target_df is not None and not target_df.empty:
                        # ✅ [關鍵] 寫入暫存檔，避免 stdout 汙染
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', encoding='utf-8-sig') as tmp:
                            target_df.to_csv(tmp.name, index=False)
                            # 只印出檔案路徑到 stdout
                            print(tmp.name)
                            return # 成功，結束
                    else:
                        log_err(f"Attempt {attempt}: Table not found or empty.")
                        sb.sleep(random.uniform(2, 5))
                        
                except Exception as inner_e:
                    log_err(f"Attempt {attempt} failed: {str(inner_e)}")
                    sb.sleep(3)

            # 如果重試多次都失敗
            raise RuntimeError("Max retries reached, unable to extract table.")

    except Exception as e:
        # 將錯誤印到 stderr，讓主程式捕捉
        log_err(traceback.format_exc())
        sys.exit(1) # 非 0 退出碼代表失敗

if __name__ == "__main__":
    main()
"""
    # 替換股票代碼
    scraper_script = scraper_script.replace("{stock_id}", str(stock_id))

    # 2. 寫入暫存檔
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(scraper_script)
            
        # 3. 執行 Subprocess
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 4. 處理結果
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown subprocess error"
            raise RuntimeError(f"Subprocess failed: {error_msg}")
            
        csv_path = result.stdout.strip()
        
        if not csv_path or not os.path.exists(csv_path):
            raise RuntimeError(f"No CSV path returned. Stderr: {result.stderr}")

        try:
            df = pd.read_csv(csv_path)
            os.remove(csv_path)
            
            # 資料清洗
            df.columns = [str(c).strip() for c in df.columns]
            buy_col = next((c for c in df.columns if "買賣超" in c), None)
            diff_col = next((c for c in df.columns if "家數差" in c), None)
            date_col = next((c for c in df.columns if "日期" in c), None)
            
            if buy_col and diff_col and date_col:
                clean_df = df[[date_col, buy_col, diff_col]].copy()
                clean_df.columns = ['日期', '買賣超', '家數差']
                for col in ['買賣超', '家數差']:
                    clean_df[col] = pd.to_numeric(clean_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                clean_df['DateStr'] = clean_df['日期'].astype(str).str.replace('/', '-')
                return clean_df.sort_values('DateStr')
            else:
                raise ValueError("Parsed CSV missing required columns")
                
        except Exception as e:
            raise RuntimeError(f"Failed to read/parse output CSV: {e}")

    except Exception as e:
        raise e
        
    finally:
        if os.path.exists(path):
            os.remove(path)

# ✅ [NEW] 抓取神秘金字塔排行 (Norawy StockHoldersTopWeek)
@st.cache_data(ttl=21600)
def get_norway_rank_data():
    driver = get_driver()
    url = "https://norway.twsthr.info/StockHoldersTopWeek.aspx"
    
    try:
        driver.get(url)
        # 等待表格載入
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//table[contains(., '大股東持有張數增減')]"))
        )
        
        # ✅ [FIX] 使用 header=None 讀取，避免 MultiIndex 亂碼，改用 iloc 指定索引
        html = driver.page_source
        dfs = pd.read_html(StringIO(html), header=None)
        
        target_df = None
        for df in dfs:
            # 檢查是否為目標表格 (欄位數量足夠且包含特定特徵)
            if len(df.columns) > 10 and len(df) > 20:
                # 簡單判斷：看是否包含 "大股東持有" 字樣
                if df.apply(lambda x: x.astype(str).str.contains('大股東持有').any()).any():
                    target_df = df
                    break
        
        if target_df is None and len(dfs) > 0:
             target_df = max(dfs, key=len)

        if target_df is not None:
            # 清理資料：取前 100 名
            # 我們需要找到 Header 所在的那一列，以及 Data 開始的那一列
            
            # 1. 找 Header 列 (包含日期的那列，例如 '20251205')
            header_idx = -1
            data_start_idx = -1
            
            for idx, row in target_df.iterrows():
                row_str = row.astype(str).values
                # 檢查是否為資料列 (第3欄 - index 3 是代號，例如 '3006晶豪科')
                if re.search(r'\d{4}', str(row[3])):
                    data_start_idx = idx
                    break
            
            # 如果找不到資料列，就回傳 None
            if data_start_idx == -1: return None
            
            # Header 通常在資料列的前面幾列
            # 我們往回找包含日期的列 (通常是 index 5-10)
            for idx in range(max(0, data_start_idx - 5), data_start_idx):
                row = target_df.iloc[idx]
                # 檢查第 5 欄是否像日期 (純數字且長度 >= 4)
                if re.match(r'^\d{4,}$', str(row[5])):
                    header_idx = idx
                    break
            
            # 擷取資料 (從 data_start_idx 開始，取 100 筆)
            raw_data = target_df.iloc[data_start_idx:data_start_idx+100].copy()
            
            # 準備欄位名稱
            # 3: 名稱, 5~10: 日期, 13: 總增減, 15: 上週%
            col_indices = [3, 5, 6, 7, 8, 9, 10, 13, 15]
            
            final_cols = ["股票代號/名稱"]
            if header_idx != -1:
                # 從 header row 抓取日期
                date_headers = target_df.iloc[header_idx, 5:11].tolist()
                final_cols.extend([str(d) for d in date_headers])
            else:
                # 抓不到就用預設
                final_cols.extend([f"Date_{i}" for i in range(1, 7)])
                
            final_cols.extend(["總增減", "上週持有%"])
            
            # 篩選欄位
            result_df = raw_data.iloc[:, col_indices]
            result_df.columns = final_cols
            
            # ✅ [FIX] 轉換數值以利顏色樣式 (先去除所有非數字字元，只保留 . -)
            # 但先轉為字串比較安全，因為要套用 style
            result_df = result_df.astype(str)
            
            return result_df

    except Exception:
        return None
    finally:
        driver.quit()
    return None

# ✅ 獲取所有股票選單
@st.cache_data
def get_all_stock_options():
    stock_options = []
    for code, info in twstock.codes.items():
        if info.type == "股票": 
            stock_options.append(f"{code} {info.name}")
    return stock_options

st.title(f"📊 籌碼K線")

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

# ✅ [FIX] 類股排行點擊後的跳轉：必須在任何 widget 建立前套用
if "__jump_stock_code" in st.session_state:
    code = st.session_state.pop("__jump_stock_code")
    # 找到 selectbox 對應的選項字串（例如 "3006 晶豪科"）
    for s in get_all_stock_options():
        if s.startswith(code):
            st.session_state["stock_selector"] = s
            break

if "__jump_page" in st.session_state:
    st.session_state["current_page"] = st.session_state.pop("__jump_page")


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
    
    # ✅ [FIX] 移除 target_index 計算與 index 參數，改為初始化 session_state
    if "stock_selector" not in st.session_state:
        # 預設找 2313
        default_index = 0
        for idx, s in enumerate(sorted_stocks):
            if s.startswith("2313"):
                default_index = idx
                break
        if sorted_stocks:
            st.session_state["stock_selector"] = sorted_stocks[default_index]
                
    # 加上 key 參數以保持狀態
    stock_selection = st.selectbox(
        "搜尋股票", 
        options=sorted_stocks, 
        # index=target_index,  <-- REMOVE THIS
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

# ✅ [FIX] 移除 st.tabs，改用 st.radio 模擬分頁
if 'current_page' not in st.session_state:
    st.session_state.current_page = "K線"

# ✅ [NEW] 新增 "主力" 與 "類股排行" 選項
selected_page = st.radio(
    "功能分頁", 
    ["K線", "分點", "法人", "融資券", "主力", "大戶", "類股排行", "多股比較"], 
    horizontal=True,
    label_visibility="collapsed",
    key="current_page"
)

# ==================== Tab: 主力 (New) ====================
if selected_page == "主力":
    if stock_input:
        stock_name = get_stock_name(stock_input)
        stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input
        st.subheader(f"⚡ {stock_display} 主力買賣超與家數差 (玩股網)")
        
        # 嘗試安裝/使用 seleniumbase 抓取
        wg_df = None
        
        with st.spinner("正在抓取主力數據 (使用 SeleniumBase)..."):
            try:
                # ✅ [FIX] 呼叫爬蟲，如果失敗這裡會拋出例外，不會被快取
                wg_df = get_wantgoo_data(stock_input, st.session_state.refresh_nonce)
            except Exception as e:
                st.warning(f"⚠️ 無法取得玩股網主力數據，可能被阻擋或無資料。\n(錯誤訊息: {str(e)})")
                st.info("💡 建議點擊上方「強制更新籌碼資料」重試。")
                wg_df = None
        
        if wg_df is not None and not wg_df.empty:
            # 準備 K 線圖資料 (只顯示有主力數據的日期)
            # 先抓股價
            if 'df_price_daily' not in locals() or df_price_daily is None:
                df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
            
            if df_price_daily is not None:
                # Merge to ensure dates match
                merged_wg = pd.merge(df_price_daily, wg_df, on='DateStr', how='inner')
                
                # Charts
                candlestick_data = []
                ma5_data, ma20_data = [], []
                net_buy_data = []
                diff_data = []
                
                for i, row in merged_wg.iterrows():
                    # K-Line
                    candlestick_data.append({
                        "time": row['DateStr'], 
                        "open": row['Open'], "high": row['High'], 
                        "low": row['Low'], "close": row['Close']
                    })
                    # MA
                    if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": row['MA5']})
                    if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": row['MA20']})
                    
                    # Net Buy (主力買賣超)
                    nb = row['買賣超']
                    net_buy_data.append({
                        "time": row['DateStr'], 
                        "value": nb, 
                        "color": COLOR_UP if nb > 0 else COLOR_DOWN
                    })
                    
                    # Diff (家數差) - Note: Negative diff often implies concentration (Good -> Red)
                    # Positive diff implies dispersion (Bad -> Green)
                    df_val = row['家數差']
                    # Logic: if diff < 0 (Concentrated) -> Red, else Green
                    diff_color = COLOR_UP if df_val < 0 else COLOR_DOWN
                    diff_data.append({
                        "time": row['DateStr'], 
                        "value": df_val, 
                        "color": diff_color
                    })

                # Plot 1: K-Line
                chart1 = {
                    "chart": make_opts(350, "股價", True),
                    "series": [
                        {"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN}},
                        {"type": "Line", "data": ma5_data, "options": {"color": "orange", "lineWidth": 1}},
                        {"type": "Line", "data": ma20_data, "options": {"color": "#ff00ff", "lineWidth": 1}}
                    ]
                }
                
                # Plot 2: Net Buy
                chart2 = {
                    "chart": make_opts(150, "主力買賣超", False),
                    "series": [
                        {"type": "Histogram", "data": net_buy_data, "options": {"priceScaleId": "right"}}
                    ]
                }
                
                # Plot 3: Broker Diff
                chart3 = {
                    "chart": make_opts(150, "買賣家數差 (負值=集中=紅)", False),
                    "series": [
                        {"type": "Histogram", "data": diff_data, "options": {"priceScaleId": "right"}}
                    ]
                }
                
                renderLightweightCharts([chart1, chart2, chart3], key="wg_charts")
                
                # Data Table
                st.markdown("#### 詳細數據")
                # Sort desc for table
                display_df = wg_df.sort_values('DateStr', ascending=False)
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
            else:
                st.warning("無法取得股價資料以繪製對照圖表。")
                st.dataframe(wg_df)

# ==================== Tab 6: 類股排行 (新增功能) ====================
elif selected_page == "類股排行":
    st.subheader("🏆 大股東持股排行榜 (Top 100)")
    
    # ✅ [FIX] 移除 st.spinner，直接執行
    rank_df = get_norway_rank_data()
    
    if rank_df is not None and not rank_df.empty:
        # ✅ [FIX] 重設索引並加入 KEY，確保選取功能正常運作
        rank_df = rank_df.reset_index(drop=True)
        
        # ✅ [NEW] 樣式函式：漲紅跌綠
        def highlight_val(val):
            try:
                # 移除可能的非數字字元 (例如 %)
                clean_val = str(val).replace('%', '').replace(',', '').strip()
                v = float(clean_val)
                if v > 0:
                    return f'color: {COLOR_UP}' # 紅
                elif v < 0:
                    return f'color: {COLOR_DOWN}' # 綠
            except:
                pass
            return ''
            
        # 套用樣式 (排除第一欄股票名稱)
        styled_df = rank_df.style.map(highlight_val, subset=rank_df.columns[1:])
        
        event = st.dataframe(
            styled_df, # 使用有樣式的 DF
            use_container_width=True, 
            hide_index=True,
            on_select="rerun", 
            selection_mode="single-row",
            key="rank_table" # 關鍵修正：加入固定 Key
        )
        
        # 處理點擊事件
        if len(event.selection.rows) > 0:
            selected_row_idx = event.selection.rows[0]
            # 取得選中列的資料 (第一欄就是股票名稱/代號)
            stock_str = str(rank_df.iloc[selected_row_idx, 0])
            
            if stock_str:
                # 提取代號 (4碼數字)
                match = re.search(r'(\d{4})', stock_str)
                if match:
                    code = match.group(1)
                    
                    # ✅ [FIX] 改用暫存變數控制跳轉，避免在 widget 建立後修改 key 導致失效
                    st.session_state["__jump_stock_code"] = code
                    st.session_state["__jump_page"] = "K線"
                    
                    # 更新搜尋次數 (這不是 widget key，可以直接改)
                    st.session_state.search_counts[code] = st.session_state.search_counts.get(code, 0) + 1
                    
                    st.rerun()

    else:
        st.warning("⚠️ 無法取得排行資料，請稍後再試。")

# ==================== Tab 7: 多股比較 (New) ====================
elif selected_page == "多股比較":
    st.subheader("📈 多股 K 線比較")
    
    # Inputs for comparison
    with st.expander("⚙️ 設定比較股票與指標", expanded=True):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        stock_inputs = []
        with c1: stock_inputs.append(st.text_input("股票 1", placeholder="2330"))
        with c2: stock_inputs.append(st.text_input("股票 2", placeholder="2317"))
        with c3: stock_inputs.append(st.text_input("股票 3", placeholder="2454"))
        with c4: stock_inputs.append(st.text_input("股票 4", placeholder=""))
        with c5: stock_inputs.append(st.text_input("股票 5", placeholder=""))
        with c6: stock_inputs.append(st.text_input("股票 6", placeholder=""))
        
        indicator_type = st.selectbox(
            "選擇副圖指標", 
            ["成交量", "KD", "MACD", "RSI", "外資買賣超", "投信買賣超", "自營商買賣超"]
        )
    
    # Process each stock
    valid_stocks = [s.strip() for s in stock_inputs if s.strip()]
    num_stocks = len(valid_stocks)
    
    if num_stocks > 0:
        # Determine grid cols and height
        if num_stocks == 1:
            cols_per_row = 1
            chart_height = 600
        elif num_stocks == 2:
            cols_per_row = 2
            chart_height = 500
        else:
            cols_per_row = 2
            # ✅ [MODIFIED] Changed to 400 per user request
            chart_height = 400
        
        # Calculate needed rows
        rows = math.ceil(num_stocks / cols_per_row)
        
        for r in range(rows):
            cols = st.columns(cols_per_row)
            for c in range(cols_per_row):
                idx = r * cols_per_row + c
                if idx < num_stocks:
                    code = valid_stocks[idx]
                    name = get_stock_name(code)
                    display_title = f"{code} {name}" if name else code
                    
                    with cols[c]:
                        # Fetch Data
                        df = get_stock_price(code, st.session_state.refresh_nonce)
                        
                        if df is not None and not df.empty:
                            # Prepare Data
                            chart_data = []
                            ma5, ma20 = [], []
                            
                            # 1. Main Chart (K-Line + MA)
                            for _, row in df.iterrows():
                                if not pd.isna(row['Open']):
                                    chart_data.append({
                                        "time": row['DateStr'], 
                                        "open": row['Open'], "high": row['High'], 
                                        "low": row['Low'], "close": row['Close']
                                    })
                                if not pd.isna(row['MA5']): ma5.append({"time": row['DateStr'], "value": row['MA5']})
                                if not pd.isna(row['MA20']): ma20.append({"time": row['DateStr'], "value": row['MA20']})
                            
                            # ✅ [FIX] Remove horizontal dashed lines (priceLineVisible, lastValueVisible) for MAs
                            main_series = [
                                {"type": "Candlestick", "data": chart_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False, "priceLineVisible": False}},
                                {"type": "Line", "data": ma5, "options": {"color": "orange", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}},
                                {"type": "Line", "data": ma20, "options": {"color": "#ff00ff", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}}
                            ]
                            
                            payload = [{"chart": make_opts(chart_height, display_title, False), "series": main_series}]
                            
                            # 2. Sub Chart
                            sub_data = []
                            sub_series = []
                            
                            # ✅ [FIX] Remove horizontal dashed lines for Sub-charts
                            common_opts = {"lastValueVisible": False, "priceLineVisible": False}
                            
                            if indicator_type == "成交量":
                                for _, row in df.iterrows():
                                     if not pd.isna(row['Volume']):
                                         sub_data.append({"time": row['DateStr'], "value": row['Volume'], "color": COLOR_UP if row['Close'] >= row['Open'] else COLOR_DOWN})
                                sub_series = [{"type": "Histogram", "data": sub_data, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": "right", **common_opts}}]
                                
                            elif indicator_type in ["KD", "MACD", "RSI"]:
                                 # Reuse existing indicators in df
                                 if indicator_type == "KD":
                                     k, d = [], []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['K']): k.append({"time": row['DateStr'], "value": row['K']})
                                         if not pd.isna(row['D']): d.append({"time": row['DateStr'], "value": row['D']})
                                     sub_series = [
                                         {"type": "Line", "data": k, "options": {"color": "orange", "lineWidth": 1, **common_opts}},
                                         {"type": "Line", "data": d, "options": {"color": "cyan", "lineWidth": 1, **common_opts}}
                                     ]
                                 elif indicator_type == "RSI":
                                     rsi = []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['RSI']): rsi.append({"time": row['DateStr'], "value": row['RSI']})
                                     sub_series = [{"type": "Line", "data": rsi, "options": {"color": "#AB47BC", "lineWidth": 1, **common_opts}}]
                                 elif indicator_type == "MACD":
                                     dif, dea, hist = [], [], []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['DIF']): dif.append({"time": row['DateStr'], "value": row['DIF']})
                                         if not pd.isna(row['DEA']): dea.append({"time": row['DateStr'], "value": row['DEA']})
                                         if not pd.isna(row['MACD_Hist']): hist.append({"time": row['DateStr'], "value": row['MACD_Hist'], "color": COLOR_UP if row['MACD_Hist'] >= 0 else COLOR_DOWN})
                                     sub_series = [
                                         {"type": "Histogram", "data": hist, "options": {**common_opts}},
                                         {"type": "Line", "data": dif, "options": {"color": "#FFD700", "lineWidth": 1, **common_opts}},
                                         {"type": "Line", "data": dea, "options": {"color": "#00FFFF", "lineWidth": 1, **common_opts}}
                                     ]

                            elif indicator_type in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
                                # Need extra fetch
                                s_date = df['DateStr'].iloc[0]
                                e_date = df['DateStr'].iloc[-1]
                                inst_df = get_institutional_data(code, s_date, e_date)
                                if inst_df is not None:
                                    # Merge
                                    m_df = pd.merge(df, inst_df, on='DateStr', how='left').fillna(0)
                                    col_map = {"外資買賣超": "外資買賣超", "投信買賣超": "投信買賣超", "自營商買賣超": "自營商買賣超"}
                                    target_col = col_map[indicator_type]
                                    
                                    bar_data = []
                                    line_data = []
                                    cum_val = 0
                                    for _, row in m_df.iterrows():
                                        val = row[target_col]
                                        cum_val += val
                                        bar_data.append({"time": row['DateStr'], "value": val, "color": COLOR_UP if val > 0 else COLOR_DOWN})
                                        line_data.append({"time": row['DateStr'], "value": cum_val})
                                        
                                    sub_series = [
                                        {"type": "Histogram", "data": bar_data, "options": {"priceScaleId": "right", **common_opts}},
                                        {"type": "Line", "data": line_data, "options": {"color": "white", "lineWidth": 2, "priceScaleId": "left", **common_opts}}
                                    ]
                            
                            if sub_series:
                                # Append sub chart
                                chart_opts = make_opts(150, indicator_type, True)
                                if indicator_type == "RSI": chart_opts["rightPriceScale"] = {"visible":True, "autoScale":False, "mode":0, "maxValue":100, "minValue":0}
                                payload.append({"chart": chart_opts, "series": sub_series})
                            
                            renderLightweightCharts(payload, key=f"compare_{idx}_{code}")
                        else:
                            st.warning(f"⚠️ {code} 無資料")


elif stock_input:
    # ... (其餘原有的股票顯示邏輯，只有當不是 "類股排行" 時才執行) ...
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    # ✅ 使用 session_state 的統計天數（由分點頁面控制）
    # ✅ 關鍵：這裡直接讀取 st.session_state.days_label，如果 widget 有變動，streamlit 重新執行時這裡就會拿到新的值
    current_days_label = st.session_state.days_label
    selected_days = days_map.get(current_days_label, 20) # [FIX] 將 fallback 改為 20
    st.session_state.selected_days = selected_days # 同步更新

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    # 只有在需要個別股票資料的分頁才執行這些爬蟲，節省資源
    df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = None, None, None, None, None, None
    
    # ✅ 預先抓取基本資料 (除了類股排行外都共用)
    with st.spinner(f"正在分析 {stock_display} ..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce)
        
    df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
    
    # ✅ [NEW] 預先定義 df_price 為日資料，確保所有分頁都能存取到基礎資料
    df_price = df_price_daily.copy() if df_price_daily is not None else None
    
    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date})")
        #st.caption(f"資料來源：{target_url}")

        # ... (選單已移至上方，這裡不需要再次呼叫 st.radio) ...
        # 這裡直接使用 selected_page 變數判斷

        # 共用 opts (crosshair: horzLine.labelVisible=True -> 右側顯示價格)
        # [FIX] 調整 labelBackgroundColor 為亮色 (#4c525e)
        # ✅ [REVERTED] 恢復 make_opts 到未嘗試縮放前的狀態 (移除 barSpacing/rightOffset/data_len)
        def make_opts(height, title=None, time_visible=True, scale_mode="normal"):
            opts = {
                "layout": {"textColor": "white", "background": {"type": "solid", "color": "#131722"}},
                "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
                "grid": {"vertLines": {"color": "rgba(42, 46, 57, 0.5)"}, "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}},
                "timeScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)", 
                    "visible": time_visible, 
                    "timeVisible": True, # 分時資料需要顯示時間
                    "secondsVisible": False
                },
                # ✅ [FIX] 強制設定右側座標軸最小寬度，以對齊所有圖表
                "rightPriceScale": {"borderColor": "rgba(197, 203, 206, 0.8)", "visible": True, "minimumWidth": 75},
                "crosshair": {
                    "mode": 1,
                    "vertLine": {"visible": True, "style": 0, "width": 1, "color": 'rgba(255, 255, 255, 0.4)', "labelVisible": True},
                    "horzLine": {
                        "visible": True, 
                        "labelVisible": True,
                        "labelBackgroundColor": '#1E88E5' # ✅ [FIX] 改為更亮的藍色以提高對比度
                    }
                },
                "height": height,
            }
            if scale_mode == "rsi":
                # ✅ [FIX] RSI 模式下也要保留 minimumWidth，並將 visible 設為 True (否則無法對齊)
                opts["rightPriceScale"] = {"visible": True, "autoScale": False, "mode": 0, "maxValue": 100, "minValue": 0, "minimumWidth": 75}
            if title:
                opts["watermark"] = {"visible": True, "fontSize": 20, "horzAlign": 'left', "vertAlign": 'top', "color": 'rgba(255, 255, 255, 0.2)', "text": title}
            
            return opts

        # ==================== Tab 1: K線 ====================
        if selected_page == "K線":
            # ✅ [NEW] 將 K 線週期選擇器移至此處，並加入分時選項
            kline_period = st.selectbox("K 線週期", ["日K", "週K", "月K", "5分", "15分", "30分", "60分"])
            
            # ✅ [NEW] 根據選擇的週期重新採樣 (Resample) 資料或抓取分時資料
            plot_df = None
            if kline_period in ["日K", "週K", "月K"]:
                if df_price_daily is not None:
                    plot_df = resample_data(df_price_daily, kline_period)
            else:
                # 抓取分時資料
                with st.spinner(f"正在載入 {kline_period} 資料..."):
                    plot_df = get_intraday_data(stock_input, kline_period)
                    if plot_df is None:
                        st.warning("⚠️ 無法取得分時資料（可能是週末或資料源暫時無法存取）")
                        plot_df = df_price_daily.copy() # Fallback

            # ✅ [FIX] 改用 st.multiselect 取代多個 Checkbox
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
            
            if plot_df is not None and not plot_df.empty:
                charts_payload = []
                plot_df.index.name = None
                # 分時資料的 DateStr 已經包含時間，且是排序好的字串
                plot_df = plot_df.sort_values("DateStr").reset_index(drop=True)

                candlestick_data, ma5_data, ma10_data, ma20_data, ma60_data, ma120_data, ma240_data, bb_up_data, bb_low_data = [], [], [], [], [], [], [], [], []
                
                # ✅ [FIX] 判斷是否為分時資料 (Intraday)
                is_intraday = kline_period in ["5分", "15分", "30分", "60分"]
                
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Open']) and not pd.isna(row['Close']):
                        # ✅ [FIX] 如果是分時資料，時間必須轉為 Unix Timestamp (秒) 才能正確顯示
                        if is_intraday:
                            try:
                                # 解析字串並轉為時間戳記
                                dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                                time_val = int(dt_obj.timestamp())
                            except:
                                time_val = row['DateStr']
                        else:
                            # 日K/週K/月K 使用字串即可
                            time_val = row['DateStr']
                            
                        candlestick_data.append({"time": time_val, "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                    
                    # 處理均線與指標
                    t_val = time_val # 使用相同的時間格式
                    
                    if show_ma5 and not pd.isna(row['MA5']): ma5_data.append({"time": t_val, "value": float(row['MA5'])})
                    if show_ma10 and not pd.isna(row['MA10']): ma10_data.append({"time": t_val, "value": float(row['MA10'])})
                    if show_ma20 and not pd.isna(row['MA20']): ma20_data.append({"time": t_val, "value": float(row['MA20'])})
                    if show_ma60 and not pd.isna(row['MA60']): ma60_data.append({"time": t_val, "value": float(row['MA60'])})
                    if show_ma120 and not pd.isna(row['MA120']): ma120_data.append({"time": t_val, "value": float(row['MA120'])})
                    if show_ma240 and not pd.isna(row['MA240']): ma240_data.append({"time": t_val, "value": float(row['MA240'])})
                    if show_bb and not pd.isna(row['BB_Up']): bb_up_data.append({"time": t_val, "value": float(row['BB_Up'])})
                    if show_bb and not pd.isna(row['BB_Low']): bb_low_data.append({"time": t_val, "value": float(row['BB_Low'])})

                # ✅ [FIX] 禁用固定標籤
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
                
                # ✅ [MODIFIED] 移除 data_len
                charts_payload.append({"chart": make_opts(400, "股價", True), "series": main_series})

                vol_data = []
                for i, row in plot_df.iterrows():
                    # ✅ [FIX] 同樣處理成交量的時間格式
                    if is_intraday:
                        try:
                            dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                            time_val = int(dt_obj.timestamp())
                        except:
                            time_val = row['DateStr']
                    else:
                        time_val = row['DateStr']
                        
                    if not pd.isna(row['Volume']): vol_data.append({"time": time_val, "value": float(row['Volume']), "color": COLOR_UP if row['Close']>=row['Open'] else COLOR_DOWN})
                # ✅ [FIX] 禁用固定標籤
                charts_payload.append({"chart": make_opts(150, "成交量", False), "series": [{"type": "Histogram", "data": vol_data, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": "right", "title": "成交量", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}]})

                # ✅ [修正錯誤] 這裡原本 k_data, d_data = [] 會導致 ValueError，改為 [], []
                k_data, d_data = [], []
                if 'K' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        # ✅ [FIX] 處理 KD 指標時間
                        if is_intraday:
                            try:
                                dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                                time_val = int(dt_obj.timestamp())
                            except:
                                time_val = row['DateStr']
                        else:
                            time_val = row['DateStr']
                            
                        if not pd.isna(row['K']): k_data.append({"time": time_val, "value": float(row['K'])})
                        if not pd.isna(row['D']): d_data.append({"time": time_val, "value": float(row['D'])})
                    # ✅ [FIX] 禁用固定標籤
                    charts_payload.append({"chart": make_opts(150, "KD", False), "series": [
                        {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": d_data, "options": {"color": "cyan", "lineWidth": 1, "title": "D", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                    ]})

                dif_data, dea_data, hist_data = [], [], []
                if 'DIF' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        # ✅ [FIX] 處理 MACD 指標時間
                        if is_intraday:
                            try:
                                dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                                time_val = int(dt_obj.timestamp())
                            except:
                                time_val = row['DateStr']
                        else:
                            time_val = row['DateStr']
                            
                        if not pd.isna(row['DIF']): dif_data.append({"time": time_val, "value": float(row['DIF'])})
                        if not pd.isna(row['DEA']): dea_data.append({"time": time_val, "value": float(row['DEA'])})
                        if not pd.isna(row['MACD_Hist']): hist_data.append({"time": time_val, "value": float(row['MACD_Hist']), "color": COLOR_UP if row['MACD_Hist']>=0 else COLOR_DOWN})
                    # ✅ [FIX] 禁用固定標籤
                    charts_payload.append({"chart": make_opts(150, "MACD", False), "series": [
                        {"type": "Histogram", "data": hist_data, "options": {"title": "柱", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": dif_data, "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": dea_data, "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                    ]})

                rsi_data, rsi_80, rsi_20 = [], [], []
                if 'RSI' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        # ✅ [FIX] 處理 RSI 指標時間
                        if is_intraday:
                            try:
                                dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                                time_val = int(dt_obj.timestamp())
                            except:
                                time_val = row['DateStr']
                        else:
                            time_val = row['DateStr']
                            
                        if not pd.isna(row['RSI']): 
                            rsi_data.append({"time": time_val, "value": float(row['RSI'])})
                            rsi_80.append({"time": time_val, "value": 80})
                            rsi_20.append({"time": time_val, "value": 20})
                    # ✅ [FIX] 禁用固定標籤
                    charts_payload.append({"chart": make_opts(150, "RSI", False, scale_mode="rsi"), "series": [
                        {"type": "Line", "data": rsi_data, "options": {"color": "#AB47BC", "lineWidth": 1, "title": "RSI(6)", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": rsi_80, "options": {"color": "red", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}},
                        {"type": "Line", "data": rsi_20, "options": {"color": "green", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}}
                    ]})
                
                renderLightweightCharts(charts_payload, key="tab1_kline")

        # ==================== Tab 2: 分點 ====================
        if selected_page == "分點":
            # ✅ [LAYOUT CHANGE] 改為左圖右表 (Left: Charts, Right: Tables)
            col_chart, col_table = st.columns([3, 1])
            
            # 初始化 session_state
            if "active_broker" not in st.session_state:
                st.session_state.active_broker = None
            if "last_buy" not in st.session_state: st.session_state.last_buy = None
            if "last_sell" not in st.session_state: st.session_state.last_sell = None

            # --- 右側：排行表 (優先處理以捕捉事件，但不調用 rerun) ---
            with col_table:
                # ✅ [LAYOUT CHANGE] 將統計天數選單移至此處 (右側欄位上方)
                # 使用 key="days_label" 直接綁定到 st.session_state.days_label
                # 這樣修改時 Streamlit 會自動 rerun，並且保留在當前分頁
                
                # ✅ [FIX] 強制設定 index 為 "20日" (索引為 3)，讓預設選單正確顯示
                # ["1日", "5日", "10日", "20日", ...] -> 20日是 index 3
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
                    # ✅ 捕捉點擊事件
                    sel_buy = render_broker_table(df_buy, sum_buy, COLOR_UP, "🔴 買超前 15 大", key_id="buy_table")
                        
                with t2: 
                    # ✅ 捕捉點擊事件
                    sel_sell = render_broker_table(df_sell, sum_sell, COLOR_DOWN, "🟢 賣超前 15 大", key_id="sell_table")
                
                # ✅ 判斷是否有新的選取 (使用 last_buy/sell 避免衝突)
                if sel_buy and sel_buy != st.session_state.last_buy:
                    st.session_state.active_broker = sel_buy
                    st.session_state.last_buy = sel_buy
                elif sel_sell and sel_sell != st.session_state.last_sell:
                    st.session_state.active_broker = sel_sell
                    st.session_state.last_sell = sel_sell

            # --- 左側：圖表區 (讀取更新後的 active_broker) ---
            with col_chart:
                c1, c2 = st.columns([1, 2])
                
                # ✅ 決定目標券商 (從點擊狀態或預設第一筆)
                target_broker = st.session_state.active_broker
                if not target_broker:
                    brokers_list = list(dict.fromkeys(df_buy['broker'].tolist() + df_sell['broker'].tolist()))
                    if brokers_list:
                        target_broker = brokers_list[0]
                        st.session_state.active_broker = target_broker
                
                if target_broker:
                    # 顯示標題
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
                        # ✅ 加入 selected_days 到 key 中，確保天數切換時會重新爬取
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
                    # ✅ [NEW] 準備均線數據
                    ma5_data, ma10_data, ma20_data = [], [], []
                    
                    # ✅ [關鍵修改] 構建 K 線數據，加入「區間凸顯」邏輯
                    # rank_start_date 和 rank_end_date 為當前統計區間
                    
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['Open']):
                            
                            # 判斷當前日期是否在選定的統計區間內
                            is_in_range = rank_start_date <= row['DateStr'] <= rank_end_date
                            
                            # 基礎數據結構
                            item = {
                                "time": row['DateStr'],
                                "open": float(row['Open']),
                                "high": float(row['High']),
                                "low": float(row['Low']),
                                "close": float(row['Close'])
                            }
                            
                            # ✅ [修正] 顏色邏輯：區間內正常亮色，區間外變淡 (使用 rgba 透明度)
                            # 使用 rgba 可以讓顏色變淺，而非變灰
                            if row['Close'] >= row['Open']:
                                base_color = COLOR_UP
                                # 淡紅色: 239, 83, 80, 0.3
                                fade_color = 'rgba(239, 83, 80, 0.3)'
                            else:
                                base_color = COLOR_DOWN
                                # 淡綠色: 38, 166, 154, 0.3
                                fade_color = 'rgba(38, 166, 154, 0.3)'

                            if is_in_range:
                                item["color"] = base_color
                                item["borderColor"] = base_color
                                item["wickColor"] = base_color
                            else:
                                # 區間外的顏色 (變淺/半透明)
                                item["color"] = fade_color
                                item["borderColor"] = fade_color
                                item["wickColor"] = fade_color
                                
                            candlestick_data.append(item)
                            
                            # ✅ 收集均線數據
                            if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                            if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                            if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})
                    
                    # ✅ [修正] 移除舊的直方圖遮罩，改回使用 Candlestick
                    main_chart_series = []
                    main_chart_series.append({
                        "type": "Candlestick",
                        "data": candlestick_data,
                        # 選項中的顏色會被 data 中的個別顏色覆蓋，但還是留著當預設值
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
                    
                    # ✅ [NEW] 加入均線到圖表
                    ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                    main_chart_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
                    main_chart_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
                    main_chart_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

                    # ✅ [MODIFIED] 移除 data_len
                    charts_payload_broker.append({"chart": make_opts(400, "股價 (淺色為統計區間外)", True), "series": main_chart_series})
                    
                    if '買賣超_Final' in plot_df.columns:
                        chip_data, chip_cumulative_data = [], []
                        for i, row in plot_df.iterrows():
                            val = row.get('買賣超_Final')
                            is_in_range = rank_start_date <= row['DateStr'] <= rank_end_date
                            
                            if not pd.isna(val): 
                                # ✅ [修正] 副圖（分點買賣超）也套用變淺邏輯
                                if val > 0:
                                    c = COLOR_UP if is_in_range else 'rgba(239, 83, 80, 0.3)'
                                else:
                                    c = COLOR_DOWN if is_in_range else 'rgba(38, 166, 154, 0.3)'
                                    
                                chip_data.append({"time": row['DateStr'], "value": float(val), "color": c})
                                
                            cum_val = row.get('cumulative_chip')
                            if not pd.isna(cum_val): chip_cumulative_data.append({"time": row['DateStr'], "value": float(cum_val)})
                        
                        # ✅ [FIX] 禁用固定標籤
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
                # ✅ [NEW] 計算三大法人合計買賣超 與 累積
                plot_df['total_inst'] = plot_df['外資買賣超'] + plot_df['投信買賣超'] + plot_df['自營商買賣超']
                plot_df['cum_total'] = plot_df['total_inst'].cumsum()

            charts_payload_inst = []
            candlestick_data = []
            # ✅ [NEW] 準備均線數據
            ma5_data, ma10_data, ma20_data = [], [], []
            
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                # ✅ 收集均線數據
                if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})

            # ✅ [NEW] 整合 K 線與均線
            ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
            main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

            # ✅ [MODIFIED] 移除 data_len
            charts_payload_inst.append({"chart": make_opts(400, "股價", True), "series": main_series})

            if '外資買賣超' in plot_df.columns:
                f_hist, f_line = [], []
                t_hist, t_line = [], []
                d_hist, d_line = [], []
                total_line, total_hist = [], [] # ✅ [NEW] 合計累積線與合計買賣柱
                for i, row in plot_df.iterrows():
                    f_val, f_cum = row['外資買賣超'], row['cum_foreign']
                    t_val, t_cum = row['投信買賣超'], row['cum_trust']
                    d_val, d_cum = row['自營商買賣超'], row['cum_dealer']
                    total_val, total_cum = row['total_inst'], row['cum_total'] # ✅ [NEW]
                    
                    f_hist.append({"time": row['DateStr'], "value": float(f_val), "color": COLOR_UP if f_val>0 else COLOR_DOWN})
                    f_line.append({"time": row['DateStr'], "value": float(f_cum)})
                    t_hist.append({"time": row['DateStr'], "value": float(t_val), "color": COLOR_UP if t_val>0 else COLOR_DOWN})
                    t_line.append({"time": row['DateStr'], "value": float(t_cum)})
                    d_hist.append({"time": row['DateStr'], "value": float(d_val), "color": COLOR_UP if d_val>0 else COLOR_DOWN})
                    d_line.append({"time": row['DateStr'], "value": float(d_cum)})
                    
                    # ✅ [NEW]
                    total_hist.append({"time": row['DateStr'], "value": float(total_val), "color": COLOR_UP if total_val>0 else COLOR_DOWN})
                    total_line.append({"time": row['DateStr'], "value": float(total_cum)})

                # ✅ [FIX] 移除個別法人資料，只保留合計，禁用固定標籤
                charts_payload_inst.append({"chart": make_opts(200, "三大法人合計", False), "series": [
                    {"type": "Histogram", "data": total_hist, "options": {"title": "合計買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": total_line, "options": {"title": "合計累", "color": "white", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                
                # 下方維持不變，顯示個別法人詳情，禁用固定標籤
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
            # ✅ [FIX] 限制融資券爬取範圍為最近 2 年
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=730) # 2 years
            long_start_date = start_dt.strftime('%Y-%m-%d')
            long_end_date = end_dt.strftime('%Y-%m-%d')
            
            with st.spinner("正在爬取融資券資料..."):
                margin_df = get_margin_data(stock_input, long_start_date, long_end_date)
            
            if margin_df is None or margin_df.empty:
                st.warning("⚠️ 查無融資融券資料，可能來源網站無資料或暫時無法連線。")
            
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
            # ✅ [NEW] 準備均線數據
            ma5_data, ma10_data, ma20_data = [], [], []

            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                # ✅ 收集均線數據
                if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})

            # ✅ [NEW] 整合 K 線與均線
            ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
            main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5"}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10"}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}})

            # ✅ [MODIFIED] 移除 data_len
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
                        # ✅ [FIX] 增加用紅(COLOR_UP), 減少用綠(COLOR_DOWN)
                        color = COLOR_UP if val_md > 0 else (COLOR_DOWN if val_md < 0 else "gray")
                        ml_diff.append({"time": row['DateStr'], "value": float(val_md), "color": color})
                    if not pd.isna(val_sb): ms_bal.append({"time": row['DateStr'], "value": float(val_sb)})
                    if not pd.isna(val_sd): 
                        # ✅ [FIX] 增加用紅(COLOR_UP), 減少用綠(COLOR_DOWN)
                        color = COLOR_UP if val_sd > 0 else (COLOR_DOWN if val_sd < 0 else "gray")
                        ms_diff.append({"time": row['DateStr'], "value": float(val_sd), "color": color})

                # ✅ [FIX] 禁用固定標籤
                charts_payload_margin.append({"chart": make_opts(150, "融資", False), "series": [
                    {"type": "Histogram", "data": ml_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    # ✅ [FIX] 餘額改用橘色
                    {"type": "Line", "data": ml_bal, "options": {"title": "餘額", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                # ✅ [FIX] 禁用固定標籤
                charts_payload_margin.append({"chart": make_opts(150, "融券", False), "series": [
                    {"type": "Histogram", "data": ms_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    # ✅ [FIX] 餘額改用橘色
                    {"type": "Line", "data": ms_bal, "options": {"title": "餘額", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})

            renderLightweightCharts(charts_payload_margin, key="tab4_margin")
            
            if margin_df is not None and not margin_df.empty:
                st.markdown("#### 近 10 日融資融券詳細數據")
                
                # 1. 排序並取最後 10 筆 (最新的在最後) -> 反轉 (最新的在最前)
                display_margin = margin_df.sort_values("DateStr").tail(10).iloc[::-1]
                
                # 2. 移除 DateStr 欄位 (只留: 日期, 融資餘額, 融資增減, 融券餘額, 融券增減)
                display_margin = display_margin[['日期', '融資餘額', '融資增減', '融券餘額', '融券增減']]
                
                # 3. 設定樣式 (增紅減綠)
                def highlight_margin(df):
                    attr = pd.DataFrame('', index=df.index, columns=df.columns)
                    c_up = f'color: {COLOR_UP}'   # 紅
                    c_down = f'color: {COLOR_DOWN}' # 綠
                    
                    # 融資增減
                    mask_m_up = df['融資增減'] > 0
                    mask_m_down = df['融資增減'] < 0
                    attr.loc[mask_m_up, ['融資增減']] = c_up
                    attr.loc[mask_m_down, ['融資增減']] = c_down
                    
                    # 融券增減
                    mask_s_up = df['融券增減'] > 0
                    mask_s_down = df['融券增減'] < 0
                    attr.loc[mask_s_up, ['融券增減']] = c_up
                    attr.loc[mask_s_down, ['融券增減']] = c_down
                    
                    return attr

                st.dataframe(
                    display_margin.style.apply(highlight_margin, axis=None), 
                    use_container_width=True, 
                    hide_index=True
                )

        # ==================== Tab 5: 大戶 (集保分佈) ====================
        if selected_page == "大戶":
            LOT_CHOICES = [10, 50, 100, 200, 400, 600, 800, 1000]
            if "retail_lot" not in st.session_state: st.session_state.retail_lot = 50
            if "large_lot" not in st.session_state: st.session_state.large_lot = 400

            # ✅ [FIX] 動態過濾選項 (UI 防呆)
            # 大戶選項：必須 > 散戶
            valid_large_opts = [x for x in LOT_CHOICES if x > st.session_state.retail_lot]
            if not valid_large_opts: valid_large_opts = [1000] # Fallback
            
            # 散戶選項：必須 < 大戶
            valid_retail_opts = [x for x in LOT_CHOICES if x < st.session_state.large_lot]
            if not valid_retail_opts: valid_retail_opts = [10] # Fallback

            c1, c2 = st.columns(2)
            with c1:
                # 若當前值不在有效列表內，重置為列表第一個
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

            # ✅ [FIX] 呼叫正確的函式名稱
            raw_holder_df = get_shareholding_data(stock_input)
            
            if raw_holder_df is None or (isinstance(raw_holder_df, dict) and raw_holder_df.get('ratio') is None):
                st.warning("⚠️ 查無集保分佈資料，可能為 ETF 或資料來源暫時無法存取。")
            else:
                # 使用 分級比例表 進行計算
                df_ratio = raw_holder_df.get("ratio")
                holder_df = process_shareholding_df(df_ratio, st.session_state.large_lot, st.session_state.retail_lot)
                
                if holder_df is not None and not holder_df.empty:
                    display_df = holder_df.copy()
                    # 計算增減 (與前一週比較)
                    display_df['大戶增減'] = display_df['大戶持股(%)'].diff()
                    display_df['散戶增減'] = display_df['散戶持股(%)'].diff()
                    
                    # 倒序顯示 (最新的在上面)
                    display_df_show = display_df.sort_values("日期", ascending=False).reset_index(drop=True)
                    
                    # ✅ [FIX] 修正樣式邏輯：根據增減欄位來決定持股欄位的顏色
                    def highlight_changes(df):
                        attr = pd.DataFrame('', index=df.index, columns=df.columns)
                        c_up = f'color: {COLOR_UP}'   # 紅
                        c_down = f'color: {COLOR_DOWN}' # 綠
                        
                        # 大戶邏輯
                        mask_up = df['大戶增減'] > 0
                        mask_down = df['大戶增減'] < 0
                        attr.loc[mask_up, ['大戶持股(%)', '大戶增減']] = c_up
                        attr.loc[mask_down, ['大戶持股(%)', '大戶增減']] = c_down
                        
                        # 散戶邏輯
                        mask_up_r = df['散戶增減'] > 0
                        mask_down_r = df['散戶增減'] < 0
                        attr.loc[mask_up_r, ['散戶持股(%)', '散戶增減']] = c_up
                        attr.loc[mask_down_r, ['散戶持股(%)', '散戶增減']] = c_down
                        
                        return attr

                    st.markdown("#### 集保戶股權分散表")
                    # ✅ [FIX] hide_index=True 隱藏左側索引
                    st.dataframe(
                        display_df_show[['日期', '大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']]
                        .style.apply(highlight_changes, axis=None) # 全表套用樣式函式
                        .format("{:.2f}", subset=['大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']), 
                        use_container_width=True, 
                        height=400,
                        hide_index=True
                    )
                    
                    # =========================================================
                    # ✅ [主要修改] 股價只顯示集保日期存在的資料點
                    # =========================================================
                    
                    # 準備合併
                    df_price_daily['_dt'] = pd.to_datetime(df_price_daily['DateStr'])
                    holder_df['_dt'] = pd.to_datetime(holder_df['DateStr'])
                    
                    # 排序
                    holder_df = holder_df.sort_values('_dt')
                    df_price_daily = df_price_daily.sort_values('_dt')
                    
                    # ✅ [FIX] 改為以「holder_df (集保數據)」為主表，去抓對應的股價
                    # 這樣圖表就只會顯示集保分佈表有的日期
                    chart_df = pd.merge_asof(
                        holder_df,
                        df_price_daily[['_dt', 'Close']], # 只取需要的股價欄位
                        on='_dt',
                        direction='backward' # 若當天無股價，找前一天的
                    )
                    
                    l_data, r_data, p_data = [], [], []
                    for i, row in chart_df.iterrows():
                        if not pd.isna(row['大戶持股(%)']): l_data.append({"time": row['DateStr'], "value": row['大戶持股(%)']})
                        if not pd.isna(row['散戶持股(%)']): r_data.append({"time": row['DateStr'], "value": row['散戶持股(%)']})
                        if not pd.isna(row['Close']): p_data.append({"time": row['DateStr'], "value": row['Close']})
                        
                    holder_payload = []
                    holder_series = [
                        # ✅ [FIX] 禁用固定標籤
                        {"type": "Line", "data": l_data, "options": {"title": f"大戶(>{st.session_state.large_lot})%", "color": "red", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": False, "priceLineVisible": False}},
                        {"type": "Line", "data": r_data, "options": {"title": f"散戶(<{st.session_state.retail_lot})%", "color": "green", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": False, "priceLineVisible": False}},
                        {"type": "Line", "data": p_data, "options": {"title": "股價", "color": "white", "lineWidth": 1, "priceScaleId": "right", "lineStyle": 2, "lastValueVisible": False, "priceLineVisible": False}} 
                    ]
                    
                    # ✅ [FIX] autoScale: True, 移除固定 min/max 讓波動更明顯
                    # ✅ [MODIFIED] 移除 data_len
                    holder_opts = make_opts(400, "籌碼分佈 vs 股價", True)
                    holder_opts["leftPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    holder_opts["rightPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    
                    holder_payload.append({"chart": holder_opts, "series": holder_series})
                    renderLightweightCharts(holder_payload, key="tab5_holder")

    else:
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n2. 股票代號輸入錯誤。\n3. Yahoo API 暫時連線失敗，請稍後再試。")

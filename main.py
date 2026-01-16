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

# ✅ [MODIFIED] 將 Stock Price 恢復為 10 年，並修正時區以對齊玩股網
@st.cache_data(ttl=21600)
def get_stock_price(stock_id, refresh_nonce=0):
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    df = None
    for ticker in tickers_to_try:
        try:
            stock = yf.Ticker(ticker)
            temp_df = stock.history(period="10y") 
            if not temp_df.empty:
                df = temp_df
                break
        except: continue
    if df is None or df.empty: return None

    try:
        # ✅ [FIX] 使用 .dt.date 直接取得日期，避免時區轉換造成的誤差
        # yfinance 的 index 是 datetime，可能帶有時區或為 UTC
        # 直接轉為 date 物件再轉字串，通常能對齊當地的交易日
        df['DateStr'] = df.index.date.astype(str)
        
        # 移除時區資訊，避免後續計算報錯
        df.index = df.index.tz_localize(None)
        
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
    爬取玩股網主力買賣超資料 (含5日/20日集中度)。
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
                        # 檢查是否包含買賣超與家數差
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
            # 新增集中度欄位
            con5_col = next((c for c in df.columns if "5日集中" in c), None)
            con20_col = next((c for c in df.columns if "20日集中" in c), None)
            
            if buy_col and diff_col and date_col:
                # 選取需要的欄位
                cols_to_keep = [date_col, buy_col, diff_col]
                col_names = ['日期', '買賣超', '家數差']
                
                if con5_col:
                    cols_to_keep.append(con5_col)
                    col_names.append('5日集中')
                if con20_col:
                    cols_to_keep.append(con20_col)
                    col_names.append('20日集中')
                
                clean_df = df[cols_to_keep].copy()
                clean_df.columns = col_names
                
                # 處理數值 (移除逗號，轉數字)
                for col in ['買賣超', '家數差']:
                    clean_df[col] = pd.to_numeric(clean_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                # 處理集中度 (移除%，轉數字)
                for col in ['5日集中', '20日集中']:
                    if col in clean_df.columns:
                        clean_df[col] = clean_df[col].astype(str).str.replace('%', '').str.replace(',', '')
                        clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)

                # 處理日期 (玩股網通常是 YYYY/MM/DD 或 MM/DD)
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
                
                # ✅ [FIX] 隱藏 DateStr 欄位，並加上 % 格式
                if 'DateStr' in display_df.columns:
                    display_df = display_df.drop(columns=['DateStr'])
                
                # 設定顯示格式 (集中度加回 %)
                st.dataframe(
                    display_df.style.format({
                        '5日集中': '{:.2f}%',
                        '20日集中': '{:.2f}%'
                    }), 
                    use_container_width=True, 
                    hide_index=True
                )
                
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

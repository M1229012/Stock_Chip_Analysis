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

# ✅ TradingView 圖表套件
from streamlit_lightweight_charts import renderLightweightCharts

# ================= 1. 系統設定 =================

st.set_page_config(layout="wide", page_title="籌碼K線", initial_sidebar_state="auto")

# ✅ CSS 設定 (強制修正：使用 :has 選擇器確保選中狀態顯示，並微調文字水平/垂直位置)
st.markdown("""
    <style>
    /* --- 通用字體設定 --- */
    html, body, [class*="css"] { font-size: 18px !important; }
    .stDataFrame { font-size: 16px !important; }
      
    /* --- 數據卡片樣式 --- */
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

    /* --- 手機版 RWD (螢幕 < 768px) --- */
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
    }

    /* --- 電腦版 RWD (螢幕 > 768px) --- */
    @media (min-width: 769px) {
        /* 電腦時：隱藏包含 mobile-marker 的容器 */
        div[data-testid="stVerticalBlock"]:has(> .element-container .mobile-marker) {
            display: none !important;
        }
    }

    /* =========================================================================
       ✅ [CSS 強制修正] 確保 Radio Button 選中狀態有明顯反饋且對齊
       ========================================================================= */
    
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
        margin-bottom: 5px;
        /* 這裡加上一條全長的淡線當作軌道 (可選) */
        border-bottom: 1px solid rgba(255, 255, 255, 0.1); 
        width: fit-content; /* 讓線條只跟著按鈕長度，不要橫跨整個螢幕 */
        min-width: 100%; /* 或者是讓它橫跨螢幕但顏色很淡 */
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
        flex: 0 1 auto;
    }

    /* 4. ✅ 滑鼠懸停效果 (Hover) */
    div[data-testid="stRadio"] > div[role="radiogroup"] label:hover {
        color: #ffffff !important;
        background-color: rgba(255, 255, 255, 0.05) !important; /* 懸停時淡淡的灰 */
    }

    /* 5. ✅ [關鍵修正] 選中狀態 (Active) 
       使用 :has(input:checked) 確保一定能抓到被選取的項目 */
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

with st.sidebar:
    st.header("參數設定")
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
    
    # ✅ [MOVED] 統計天數已移到「分點」頁面
    
    st.markdown(f"🕒 資料抓取時間: {current_time}")
    
    if st.button("查詢", type="primary"):
        if stock_input: st.session_state.search_counts[stock_input] = st.session_state.search_counts.get(stock_input, 0) + 1
        st.rerun()
    
    if "refresh_nonce" not in st.session_state: st.session_state.refresh_nonce = 0
    if st.button("🔄 強制更新籌碼資料"):
        st.session_state.refresh_nonce = int(time.time())
        st.rerun()

if stock_input:
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    # ✅ 使用 session_state 的統計天數（由分點頁面控制）
    # ✅ 關鍵：這裡直接讀取 st.session_state.days_label，如果 widget 有變動，streamlit 重新執行時這裡就會拿到新的值
    current_days_label = st.session_state.days_label
    selected_days = days_map.get(current_days_label, 20) # [FIX] 將 fallback 改為 20
    st.session_state.selected_days = selected_days # 同步更新

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    with st.spinner(f"正在分析 {stock_display} ..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce)
        
    df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
    
    # ✅ [NEW] 預先定義 df_price 為日資料，確保所有分頁都能存取到基礎資料
    df_price = df_price_daily.copy() if df_price_daily is not None else None
    
    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date})")
        st.caption(f"資料來源：{target_url}")

        # ✅ [FIX] 移除 st.tabs，改用 st.radio 模擬分頁，這樣才能將狀態綁定在 session_state 中
        if 'current_page' not in st.session_state:
            st.session_state.current_page = "K線"
            
        # 使用水平 radio 模擬 tabs，並隱藏標題
        # ✅ 搭配 CSS 使其看起來像 Material UI Tabs
        selected_page = st.radio(
            "功能分頁", 
            ["K線", "分點", "法人", "融資券", "大戶"], 
            horizontal=True,
            label_visibility="collapsed",
            key="current_page" # 綁定 session_state，確保互動後停留在同一頁
        )
        # ✅ [FIX] 移除 st.divider()，解決那條長線的問題
        # st.divider() 

        # 共用 opts (crosshair: horzLine.labelVisible=True -> 右側顯示價格)
        # [FIX] 調整 labelBackgroundColor 為亮色 (#4c525e)
        # ✅ [MODIFIED] 新增 data_len 參數，用於設定預設顯示範圍
        def make_opts(height, title=None, time_visible=True, scale_mode="normal", data_len=None):
            opts = {
                "layout": {"textColor": "white", "background": {"type": "solid", "color": "#131722"}},
                "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
                "grid": {"vertLines": {"color": "rgba(42, 46, 57, 0.5)"}, "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}},
                "timeScale": {"borderColor": "rgba(197, 203, 206, 0.8)", "visible": time_visible, "timeVisible": False},
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
            
            # ✅ [MODIFIED] 設定預設可視範圍 (顯示最後 60 根 bar)
            if data_len is not None and data_len > 0:
                # 計算可視範圍：從 (總長度 - 60) 開始，到 (總長度 + 2) 結束 (稍微留白)
                from_idx = max(0, data_len - 60)
                to_idx = data_len + 2 
                opts["timeScale"]["visibleLogicalRange"] = {
                    "from": from_idx,
                    "to": to_idx
                }

            return opts

        # ==================== Tab 1: K線 ====================
        if selected_page == "K線":
            # ✅ [NEW] 將 K 線週期選擇器移至此處 (均線選擇器的上方)
            kline_period = st.selectbox("K 線週期", ["日K", "週K", "月K"])
            
            # ✅ [NEW] 根據選擇的週期重新採樣 (Resample) 資料
            if df_price_daily is not None:
                df_price = resample_data(df_price_daily, kline_period)

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
            
            if df_price is not None and not df_price.empty:
                charts_payload = []
                plot_df = df_price.copy()
                plot_df.index.name = None
                plot_df["Date"] = pd.to_datetime(plot_df["DateStr"], errors="coerce")
                plot_df = plot_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

                # ✅ [MODIFIED] 取得目前資料總長度，用於設定縮放
                current_len = len(plot_df)

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
                
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload.append({"chart": make_opts(400, "股價", True, data_len=current_len), "series": main_series})

                vol_data = []
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Volume']): vol_data.append({"time": row['DateStr'], "value": float(row['Volume']), "color": COLOR_UP if row['Close']>=row['Open'] else COLOR_DOWN})
                # ✅ [FIX] 禁用固定標籤
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload.append({"chart": make_opts(150, "成交量", False, data_len=current_len), "series": [{"type": "Histogram", "data": vol_data, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": "right", "title": "成交量", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}]})

                # ✅ [修正錯誤] 這裡原本 k_data, d_data = [] 會導致 ValueError，改為 [], []
                k_data, d_data = [], []
                if 'K' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['K']): k_data.append({"time": row['DateStr'], "value": float(row['K'])})
                        if not pd.isna(row['D']): d_data.append({"time": row['DateStr'], "value": float(row['D'])})
                    # ✅ [FIX] 禁用固定標籤
                    # ✅ [MODIFIED] 傳入 current_len
                    charts_payload.append({"chart": make_opts(150, "KD", False, data_len=current_len), "series": [
                        {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                        {"type": "Line", "data": d_data, "options": {"color": "cyan", "lineWidth": 1, "title": "D", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                    ]})

                dif_data, dea_data, hist_data = [], [], []
                if 'DIF' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['DIF']): dif_data.append({"time": row['DateStr'], "value": float(row['DIF'])})
                        if not pd.isna(row['DEA']): dea_data.append({"time": row['DateStr'], "value": float(row['DEA'])})
                        if not pd.isna(row['MACD_Hist']): hist_data.append({"time": row['DateStr'], "value": float(row['MACD_Hist']), "color": COLOR_UP if row['MACD_Hist']>=0 else COLOR_DOWN})
                    # ✅ [FIX] 禁用固定標籤
                    # ✅ [MODIFIED] 傳入 current_len
                    charts_payload.append({"chart": make_opts(150, "MACD", False, data_len=current_len), "series": [
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
                    # ✅ [FIX] 禁用固定標籤
                    # ✅ [MODIFIED] 傳入 current_len
                    charts_payload.append({"chart": make_opts(150, "RSI", False, scale_mode="rsi", data_len=current_len), "series": [
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

                    # ✅ [MODIFIED] 取得目前資料總長度，用於設定縮放
                    current_len = len(plot_df)

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

                    # ✅ [MODIFIED] 傳入 current_len
                    charts_payload_broker.append({"chart": make_opts(400, "股價 (淺色為統計區間外)", True, data_len=current_len), "series": main_chart_series})
                    
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
                        # ✅ [MODIFIED] 傳入 current_len
                        charts_payload_broker.append({"chart": make_opts(200, f"{target_broker} 買賣 (淺色為統計區間外)", False, data_len=current_len), "series": [
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
            
            # ✅ [MODIFIED] 取得目前資料總長度，用於設定縮放
            current_len = len(plot_df)

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

            # ✅ [MODIFIED] 傳入 current_len
            charts_payload_inst.append({"chart": make_opts(400, "股價", True, data_len=current_len), "series": main_series})

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
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload_inst.append({"chart": make_opts(200, "三大法人合計", False, data_len=current_len), "series": [
                    {"type": "Histogram", "data": total_hist, "options": {"title": "合計買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": total_line, "options": {"title": "合計累", "color": "white", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                
                # 下方維持不變，顯示個別法人詳情，禁用固定標籤
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload_inst.append({"chart": make_opts(150, "外資", False, data_len=current_len), "series": [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": f_line, "options": {"title": "累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "投信", False, data_len=current_len), "series": [
                    {"type": "Histogram", "data": t_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": t_line, "options": {"title": "累積", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "自營商", False, data_len=current_len), "series": [
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
            # ✅ [NEW] 準備均線數據
            ma5_data, ma10_data, ma20_data = [], [], []

            # ✅ [MODIFIED] 取得目前資料總長度，用於設定縮放
            current_len = len(plot_df)

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

            # ✅ [MODIFIED] 傳入 current_len
            charts_payload_margin.append({"chart": make_opts(400, "股價", True, data_len=current_len), "series": main_series})

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
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload_margin.append({"chart": make_opts(150, "融資", False, data_len=current_len), "series": [
                    {"type": "Histogram", "data": ml_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    # ✅ [FIX] 餘額改用橘色
                    {"type": "Line", "data": ml_bal, "options": {"title": "餘額", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                # ✅ [FIX] 禁用固定標籤
                # ✅ [MODIFIED] 傳入 current_len
                charts_payload_margin.append({"chart": make_opts(150, "融券", False, data_len=current_len), "series": [
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
                    # ✅ [MODIFIED] 傳入 chart_df 的長度
                    holder_opts = make_opts(400, "籌碼分佈 vs 股價", True, data_len=len(chart_df))
                    holder_opts["leftPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    holder_opts["rightPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    
                    holder_payload.append({"chart": holder_opts, "series": holder_series})
                    renderLightweightCharts(holder_payload, key="tab5_holder")

    else:
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n2. 股票代號輸入錯誤。\n3. Yahoo API 暫時連線失敗，請稍後再試。")

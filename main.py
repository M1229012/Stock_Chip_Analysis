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

# ✅ CSS 保留原樣
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

# ✅ 確保 render_broker_table 定義在主邏輯之前
def render_broker_table(df, sum_data, color_hex, title):
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
    
    st.dataframe(
        df.style.map(lambda x: f'color: {color_hex}; font-weight: bold', subset=['net']),
        use_container_width=True, height=500, hide_index=True, column_config=full_config
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

# ✅ [FIX] 使用 requests 爬取 Norway 神秘金字塔 StockHolders.aspx
def _norm_col(x: str) -> str:
    return re.sub(r"\s+", "", str(x)).replace("\u3000", "")

# ✅ [FIX] 函式正名：get_shareholding_data
@st.cache_data(ttl=60*60*6)
def get_shareholding_data(stock_id: str) -> dict:
    url = f"https://norway.twsthr.info/StockHolders.aspx?STOCK={stock_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        r.encoding = "utf-8"

        dfs = pd.read_html(StringIO(r.text))
        norm_dfs = []
        for df in dfs:
            df = df.copy()
            df.columns = [_norm_col(c) for c in df.columns]
            norm_dfs.append(df)

        def has_any_col(df, keywords):
            cols = " ".join(map(str, df.columns))
            return all(k in cols for k in keywords)

        summary = next((df for df in norm_dfs if has_any_col(df, ["資料日期", "總股東人數"]) and ("收盤價" in " ".join(df.columns))), None)
        ratio = next((df for df in norm_dfs if ("資料日期" in df.columns) and any("1000張以上" in c or ("1000" in c and "以上" in c) for c in df.columns)), None)
        compare = next((df for df in norm_dfs if any("持股張數分級" in str(c) for c in df.columns) or (df.shape[1] > 0 and "持股張數分級" in str(df.columns[0]))), None)

        return {"summary": summary, "ratio": ratio, "compare": compare}
    except Exception:
        return {"summary": None, "ratio": None, "compare": None}

# ✅ [FIX] 欄位導向的精確解析邏輯
def _upper_lots_from_label(label: str) -> int | None:
    s = str(label).replace(" ", "").replace(",", "").replace("股", "")
    if "以上" in s: return 10**9
    m = re.search(r"(\d+)[-~～](\d+)", s)
    if not m: return None
    if "股" in str(label): return 1
    return int(m.group(2))

# ✅ [FIX] 確保此函式在被呼叫前已定義，修復 NameError
def process_shareholding_df(raw_df: pd.DataFrame, large_threshold: int, retail_threshold: int) -> pd.DataFrame | None:
    df = raw_df.copy()
    if df.empty: return None

    date_row_idx = -1
    for i in range(min(5, len(df))):
        row_str = df.iloc[i].astype(str).str.cat()
        if re.search(r"20\d{6}", row_str):
            date_row_idx = i
            break
    if date_row_idx == -1: return None

    dates, date_cols = [], []
    row_vals = df.iloc[date_row_idx].values
    for i, val in enumerate(row_vals):
        d_str = str(val).replace(".0", "")
        if re.match(r"^20\d{6}$", d_str):
            d_fmt = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
            dates.append(d_fmt)
            date_cols.append(i)
    if not dates: return None

    data_start_idx = date_row_idx + 1
    for i in range(data_start_idx, len(df)):
        val = str(df.iloc[i, 0])
        if "1-999" in val or "1-5" in val:
            data_start_idx = i
            break
            
    rows_map = []
    for i in range(data_start_idx, len(df)):
        label = str(df.iloc[i, 0])
        upper = _upper_lots_from_label(label)
        if upper: rows_map.append((upper, i))

    out = []
    for idx, date_str in enumerate(dates):
        base_col = date_cols[idx]
        ratio_col = base_col + 2
        people_col = base_col
        if ratio_col >= df.shape[1]: continue

        large_ratio, large_people = 0.0, 0
        retail_ratio, retail_people = 0.0, 0

        for upper, row_idx in rows_map:
            try:
                r_val = df.iloc[row_idx, ratio_col]
                p_val = df.iloc[row_idx, people_col]
                r = float(str(r_val).replace("%", "").replace(",", "")) if pd.notna(r_val) and str(r_val) != 'nan' else 0.0
                p = int(str(p_val).replace(",", "")) if pd.notna(p_val) and str(p_val).replace(",","").isdigit() else 0
                
                if upper >= large_threshold:
                    large_ratio += r
                    large_people += p
                if upper < retail_threshold:
                    retail_ratio += r
                    retail_people += p
            except: continue

        out.append({
            "日期": date_str,
            "DateStr": date_str,
            "大戶持股(%)": round(large_ratio, 2),
            "大戶人數": large_people,
            "散戶持股(%)": round(retail_ratio, 2),
            "散戶人數": retail_people
        })

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

st.title(f"📊 籌碼K線 (TradingView 風格)")

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

if "search_counts" not in st.session_state:
    st.session_state.search_counts = {}

with st.sidebar:
    st.header("參數設定")
    all_stocks = get_all_stock_options()
    
    def get_sort_key(stock_str):
        code = stock_str.split()[0]
        count = st.session_state.search_counts.get(code, 0)
        return -count

    sorted_stocks = sorted(all_stocks, key=get_sort_key)
    
    default_index = 0
    for idx, s in enumerate(sorted_stocks):
        if s.startswith("2313"):
            default_index = idx
            break

    stock_selection = st.selectbox("搜尋股票", options=sorted_stocks, index=default_index, placeholder="請輸入股票代號...")
    if stock_selection: stock_input = stock_selection.split()[0]
    else: stock_input = ""
    
    days_map = {"1日": 1, "5日": 5, "10日": 10, "20日": 20, "40日": 40, "60日": 60, "120日": 120, "240日": 240}
    days_label = st.selectbox("統計天數", list(days_map.keys()), index=6) 
    selected_days = days_map[days_label]
    
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
    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    with st.spinner(f"正在分析 {stock_display} ..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce)
        
    df_price = get_stock_price(stock_input, st.session_state.refresh_nonce)

    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date})")
        st.caption(f"資料來源：{target_url}")

        if "active_tab" in st.query_params: default_tab = st.query_params["active_tab"]
        tab_kline, tab_broker, tab_inst, tab_margin, tab_holder = st.tabs(["K線", "分點", "法人", "融資券", "大戶"])

        # 共用 opts (crosshair: horzLine.labelVisible=True -> 右側顯示價格)
        # [FIX] 調整 labelBackgroundColor 為亮色 (#4c525e)
        def make_opts(height, title=None, time_visible=True, scale_mode="normal"):
            opts = {
                "layout": {"textColor": "white", "background": {"type": "solid", "color": "#131722"}},
                "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
                "grid": {"vertLines": {"color": "rgba(42, 46, 57, 0.5)"}, "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}},
                "timeScale": {"borderColor": "rgba(197, 203, 206, 0.8)", "visible": time_visible, "timeVisible": False},
                "crosshair": {
                    "mode": 1,
                    "vertLine": {"visible": True, "style": 0, "width": 1, "color": 'rgba(255, 255, 255, 0.4)', "labelVisible": True},
                    "horzLine": {
                        "visible": True, 
                        "labelVisible": True,
                        "labelBackgroundColor": '#4c525e' # ✅ 更明顯的標籤背景色
                    }
                },
                "height": height,
            }
            if scale_mode == "rsi":
                opts["rightPriceScale"] = {"visible": False, "autoScale": False, "mode": 0, "maxValue": 100, "minValue": 0}
            if title:
                opts["watermark"] = {"visible": True, "fontSize": 20, "horzAlign": 'left', "vertAlign": 'top', "color": 'rgba(255, 255, 255, 0.2)', "text": title}
            return opts

        # ==================== Tab 1: K線 ====================
        with tab_kline:
            # ✅ [FIX] 使用 multiselect 收納均線按鈕
            selected_mas = st.multiselect(
                "技術指標選擇 (均線 / 布林)",
                options=["MA5", "MA10", "MA20", "MA60", "MA120", "MA240", "BB"],
                default=["MA5", "MA10", "MA20", "MA60"]
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

                ma_opts = {"lastValueVisible": True, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN}}]
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
                charts_payload.append({"chart": make_opts(150, "成交量", False), "series": [{"type": "Histogram", "data": vol_data, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": "right", "title": "成交量", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}]})

                k_data, d_data = [], []
                if 'K' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['K']): k_data.append({"time": row['DateStr'], "value": float(row['K'])})
                        if not pd.isna(row['D']): d_data.append({"time": row['DateStr'], "value": float(row['D'])})
                    charts_payload.append({"chart": make_opts(150, "KD", False), "series": [
                        {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                        {"type": "Line", "data": d_data, "options": {"color": "cyan", "lineWidth": 1, "title": "D", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                    ]})

                dif_data, dea_data, hist_data = [], [], []
                if 'DIF' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['DIF']): dif_data.append({"time": row['DateStr'], "value": float(row['DIF'])})
                        if not pd.isna(row['DEA']): dea_data.append({"time": row['DateStr'], "value": float(row['DEA'])})
                        if not pd.isna(row['MACD_Hist']): hist_data.append({"time": row['DateStr'], "value": float(row['MACD_Hist']), "color": COLOR_UP if row['MACD_Hist']>=0 else COLOR_DOWN})
                    charts_payload.append({"chart": make_opts(150, "MACD", False), "series": [
                        {"type": "Histogram", "data": hist_data, "options": {"title": "柱", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                        {"type": "Line", "data": dif_data, "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                        {"type": "Line", "data": dea_data, "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                    ]})

                rsi_data, rsi_80, rsi_20 = [], [], []
                if 'RSI' in plot_df.columns:
                    for i, row in plot_df.iterrows():
                        if not pd.isna(row['RSI']): 
                            rsi_data.append({"time": row['DateStr'], "value": float(row['RSI'])})
                            rsi_80.append({"time": row['DateStr'], "value": 80})
                            rsi_20.append({"time": row['DateStr'], "value": 20})
                    charts_payload.append({"chart": make_opts(150, "RSI", False, scale_mode="rsi"), "series": [
                        {"type": "Line", "data": rsi_data, "options": {"color": "#AB47BC", "lineWidth": 1, "title": "RSI(6)", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                        {"type": "Line", "data": rsi_80, "options": {"color": "red", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}},
                        {"type": "Line", "data": rsi_20, "options": {"color": "green", "lineWidth": 1, "lineStyle": 2, "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": False}}
                    ]})
                
                renderLightweightCharts(charts_payload, key="tab1_kline")

        # ==================== Tab 2: 分點 ====================
        with tab_broker:
            brokers_list = list(dict.fromkeys(df_buy['broker'].tolist() + df_sell['broker'].tolist()))
            target_broker = st.selectbox("選擇要查看每日明細的券商", brokers_list)
            st.markdown("---")
            
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
                merged_key = (stock_input, broker_key, st.session_state.refresh_nonce)

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
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
            
            charts_payload_broker.append({"chart": make_opts(400, "股價", True), "series": [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": True}}]})
            
            if '買賣超_Final' in plot_df.columns:
                chip_data, chip_cumulative_data = [], []
                for i, row in plot_df.iterrows():
                    val = row.get('買賣超_Final')
                    if not pd.isna(val): chip_data.append({"time": row['DateStr'], "value": float(val), "color": COLOR_UP if val>0 else COLOR_DOWN})
                    cum_val = row.get('cumulative_chip')
                    if not pd.isna(cum_val): chip_cumulative_data.append({"time": row['DateStr'], "value": float(cum_val)})
                
                charts_payload_broker.append({"chart": make_opts(200, f"{target_broker} 買賣", False), "series": [
                     {"type": "Histogram", "data": chip_data, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                     {"type": "Line", "data": chip_cumulative_data, "options": {"title": "累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})
            
            renderLightweightCharts(charts_payload_broker, key=f"tab2_broker_{target_broker}")

            st.markdown("---")
            st.markdown("##### 區間前 15 大買賣超排行")
            t1, t2 = st.tabs(["🔴 買超", "🟢 賣超"])
            # ✅ [FIX] 恢復分點前15大表格
            with t1: render_broker_table(df_buy, sum_buy, COLOR_UP, "🔴 買超前 15 大")
            with t2: render_broker_table(df_sell, sum_sell, COLOR_DOWN, "🟢 賣超前 15 大")

        # ==================== Tab 3: 法人 ====================
        with tab_inst:
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

            charts_payload_inst = []
            candlestick_data = []
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
            charts_payload_inst.append({"chart": make_opts(400, "股價", True), "series": [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": True}}]})

            if '外資買賣超' in plot_df.columns:
                f_hist, f_line = [], []
                t_hist, t_line = [], []
                d_hist, d_line = [], []
                for i, row in plot_df.iterrows():
                    f_val, f_cum = row['外資買賣超'], row['cum_foreign']
                    t_val, t_cum = row['投信買賣超'], row['cum_trust']
                    d_val, d_cum = row['自營商買賣超'], row['cum_dealer']
                    f_hist.append({"time": row['DateStr'], "value": float(f_val), "color": COLOR_UP if f_val>0 else COLOR_DOWN})
                    f_line.append({"time": row['DateStr'], "value": float(f_cum)})
                    t_hist.append({"time": row['DateStr'], "value": float(t_val), "color": COLOR_UP if t_val>0 else COLOR_DOWN})
                    t_line.append({"time": row['DateStr'], "value": float(t_cum)})
                    d_hist.append({"time": row['DateStr'], "value": float(d_val), "color": COLOR_UP if d_val>0 else COLOR_DOWN})
                    d_line.append({"time": row['DateStr'], "value": float(d_cum)})

                charts_payload_inst.append({"chart": make_opts(200, "三大法人合計", False), "series": [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "外資", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": f_line, "options": {"title": "外資累", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Histogram", "data": t_hist, "options": {"title": "投信", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": t_line, "options": {"title": "投信累", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Histogram", "data": d_hist, "options": {"title": "自營", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": d_line, "options": {"title": "自營累", "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "外資", False), "series": [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": f_line, "options": {"title": "累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "投信", False), "series": [
                    {"type": "Histogram", "data": t_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": t_line, "options": {"title": "累積", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "自營商", False), "series": [
                    {"type": "Histogram", "data": d_hist, "options": {"title": "買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": d_line, "options": {"title": "累積", "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})
            renderLightweightCharts(charts_payload_inst, key="tab3_inst")

        # ==================== Tab 4: 融資券 ====================
        with tab_margin:
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
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
            charts_payload_margin.append({"chart": make_opts(400, "股價", True), "series": [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": True}}]})

            if '融資餘額' in plot_df.columns:
                ml_bal, ml_diff, ms_bal, ms_diff = [], [], [], []
                for i, row in plot_df.iterrows():
                    val_mb = row.get('融資餘額')
                    val_md = row.get('融資增減')
                    val_sb = row.get('融券餘額')
                    val_sd = row.get('融券增減')
                    if not pd.isna(val_mb): ml_bal.append({"time": row['DateStr'], "value": float(val_mb)})
                    if not pd.isna(val_md): 
                        color = 'rgba(239, 83, 80, 0.7)' if val_md > 0 else ('rgba(38, 166, 154, 0.7)' if val_md < 0 else "gray")
                        ml_diff.append({"time": row['DateStr'], "value": float(val_md), "color": color})
                    if not pd.isna(val_sb): ms_bal.append({"time": row['DateStr'], "value": float(val_sb)})
                    if not pd.isna(val_sd): 
                        color = 'rgba(255, 215, 0, 0.7)' if val_sd > 0 else ('rgba(0, 191, 255, 0.7)' if val_sd < 0 else "gray")
                        ms_diff.append({"time": row['DateStr'], "value": float(val_sd), "color": color})

                charts_payload_margin.append({"chart": make_opts(150, "融資", False), "series": [
                    {"type": "Histogram", "data": ml_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": ml_bal, "options": {"title": "餘額", "color": "#00FF00", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})
                charts_payload_margin.append({"chart": make_opts(150, "融券", False), "series": [
                    {"type": "Histogram", "data": ms_diff, "options": {"title": "增減", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}},
                    {"type": "Line", "data": ms_bal, "options": {"title": "餘額", "color": "#FF0000", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": True}}
                ]})

            renderLightweightCharts(charts_payload_margin, key="tab4_margin")
            
            if margin_df is not None and not margin_df.empty:
                st.markdown("#### 近 10 日融資融券詳細數據")
                # ✅ [FIX] hide_index=True 隱藏左側索引
                st.dataframe(margin_df.tail(10).iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True)

        # ==================== Tab 5: 大戶 (集保分佈) ====================
        with tab_holder:
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
                    
                    def color_diff(val):
                        if pd.isna(val): return ''
                        if val > 0: return 'color: #ff4b4b' 
                        if val < 0: return 'color: #26a69a'
                        return ''

                    st.markdown("#### 集保戶股權分散表")
                    # ✅ [FIX] hide_index=True 隱藏左側索引
                    st.dataframe(
                        display_df_show[['日期', '大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']]
                        .style.map(color_diff, subset=['大戶增減', '散戶增減'])
                        .format("{:.2f}", subset=['大戶持股(%)', '大戶增減', '散戶持股(%)', '散戶增減']), 
                        use_container_width=True, 
                        height=400,
                        hide_index=True
                    )
                    
                    chart_df = pd.merge(holder_df, df_price[['DateStr', 'Close']], left_on='DateStr', right_on='DateStr', how='left')
                    chart_df['Close'] = chart_df['Close'].ffill()
                    
                    l_data, r_data, p_data = [], [], []
                    for i, row in chart_df.iterrows():
                        if not pd.isna(row['大戶持股(%)']): l_data.append({"time": row['DateStr'], "value": row['大戶持股(%)']})
                        if not pd.isna(row['散戶持股(%)']): r_data.append({"time": row['DateStr'], "value": row['散戶持股(%)']})
                        if not pd.isna(row['Close']): p_data.append({"time": row['DateStr'], "value": row['Close']})
                        
                    holder_payload = []
                    holder_series = [
                        {"type": "Line", "data": l_data, "options": {"title": f"大戶(>{st.session_state.large_lot})%", "color": "red", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": True, "priceLineVisible": False}},
                        {"type": "Line", "data": r_data, "options": {"title": f"散戶(<{st.session_state.retail_lot})%", "color": "green", "lineWidth": 2, "priceScaleId": "left", "lastValueVisible": True, "priceLineVisible": False}},
                        {"type": "Line", "data": p_data, "options": {"title": "股價", "color": "white", "lineWidth": 1, "priceScaleId": "right", "lineStyle": 2, "lastValueVisible": True, "priceLineVisible": False}} 
                    ]
                    
                    # ✅ [FIX] autoScale: True, 移除固定 min/max 讓波動更明顯
                    holder_opts = make_opts(400, "籌碼分佈 vs 股價", True)
                    holder_opts["leftPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    holder_opts["rightPriceScale"] = {"visible": True, "borderColor": "rgba(197, 203, 206, 0.8)", "autoScale": True}
                    
                    holder_payload.append({"chart": holder_opts, "series": holder_series})
                    renderLightweightCharts(holder_payload, key="tab5_holder")

    else:
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n2. 股票代號輸入錯誤。\n3. Yahoo API 暫時連線失敗，請稍後再試。")

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

def render_broker_table(df, sum_data, color_hex, title):
    st.markdown(f"#### {title}")
    
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

# ✅ 輔助函式：計算 KD, MACD, BB
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
                
                def is_date(s):
                    return re.match(r'\d{2,3}/\d{1,2}/\d{1,2}', str(s)) is not None
                clean_df = clean_df[clean_df['日期'].apply(is_date)]
                
                for col in ['外資買賣超', '投信買賣超', '自營商買賣超']:
                    clean_df[col] = clean_df[col].astype(str).str.replace(',', '').str.replace('+', '').str.replace('nan', '0')
                    clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)

                def parse_date(d_str):
                    parts = re.split(r'[/-]', str(d_str))
                    if len(parts) >= 2:
                        y = int(parts[0]) + 1911 if int(parts[0]) < 1911 else int(parts[0])
                        m = int(parts[1])
                        d = int(parts[2]) if len(parts) > 2 else 1
                        return f"{y:04d}-{m:02d}-{d:02d}"
                    return None
                
                clean_df['DateStr'] = clean_df['日期'].apply(parse_date)
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
                
                def is_date(s):
                    return re.match(r'\d{2,3}/\d{1,2}/\d{1,2}', str(s)) is not None
                clean_df = clean_df[clean_df['日期'].apply(is_date)]
                
                for col in ['融資餘額', '融資增減', '融券餘額', '融券增減']:
                    clean_df[col] = clean_df[col].astype(str).str.replace(',', '').str.replace('+', '').str.replace('nan', '0')
                    clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
                
                def parse_date(d_str):
                    parts = re.split(r'[/-]', str(d_str))
                    if len(parts) >= 2:
                        y = int(parts[0]) + 1911 if int(parts[0]) < 1911 else int(parts[0])
                        m = int(parts[1])
                        d = int(parts[2]) if len(parts) > 2 else 1
                        return f"{y:04d}-{m:02d}-{d:02d}"
                    return None
                
                clean_df['DateStr'] = clean_df['日期'].apply(parse_date)
                return clean_df.dropna(subset=['DateStr'])
    except:
        pass
    finally:
        driver.quit()
    return None

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
        if not tables:
            return None, None, None, None, None, url
        df = tables[0]
        
        header_row = -1
        for i, row in df.iterrows():
            row_str = row.astype(str).values
            if "買超券商" in row_str and "賣超券商" in row_str:
                header_row = i
                break
        if header_row == -1:
            return None, None, None, None, None, url

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
                        broker_info[name] = {
                            'b': params['b'][0],
                            'BHID': params['BHID'][0]
                        }
        except:
            pass

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
        except Exception:
            pass

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
    target_url = (f"{base_url}?A={stock_id}"
                  f"&BHID={BHID}"
                  f"&b={b}"
                  f"&C={c_val}"
                  f"&D={start_date}"
                  f"&E={end_date}"
                  f"&ver=V3")

    table_xpath = "/html/body/div[1]/table/tbody/tr[2]/td[2]/table/tbody/tr/td/form/table/tbody/tr/td/table/tbody/tr[6]/td/table"

    try:
        driver.get(target_url)
        all_dfs = []
        page_count = 0
        max_pages = 60
        
        while page_count < max_pages:
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, table_xpath))
                )
            except:
                break

            try:
                target_table = driver.find_element(By.XPATH, table_xpath)
                table_html = target_table.get_attribute('outerHTML')
                tables = pd.read_html(StringIO(table_html))
                current_df = tables[0] if tables else None
            except:
                html = driver.page_source
                tables = pd.read_html(StringIO(html), match="日期")
                current_df = tables[0] if tables else None

            if current_df is not None:
                all_dfs.append(current_df)
            
            try:
                next_links = driver.find_elements(By.XPATH, "//a[contains(text(), '下一頁')]")
                if next_links and next_links[0].is_enabled():
                    next_links[0].click()
                    time.sleep(0.5) 
                    page_count += 1
                else:
                    break 
            except:
                break

        if not all_dfs:
            return None, target_url

        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip().replace(" ", "") for c in df.columns]
        
        if '買賣超' not in df.columns and len(df.columns) >= 4:
            df = df.iloc[:, :4]
            df.columns = ['日期', '買進', '賣出', '買賣超']
            
        required = ['日期', '買進', '賣出', '買賣超']
        if not all(c in df.columns for c in required):
            return None, target_url

        df = df[df['日期'] != '日期']
        
        for col in ['買進', '賣出', '買賣超']:
             df[col] = (df[col].astype(str)
                        .str.replace(',', '', regex=False)
                        .str.replace('+', '', regex=False)
                        .str.replace('nan', '', regex=False))
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['買賣超_Calc'] = df['買進'] - df['賣出']

        def parse_date(d_str):
            s = str(d_str).strip()
            parts = re.split(r'[/-]', s)
            if len(parts) == 3:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 1911: y += 1911
                return f"{y:04d}-{m:02d}-{d:02d}"
            elif len(parts) == 2:
                m, d = int(parts[0]), int(parts[1])
                now = datetime.now()
                y = now.year
                if m > now.month + 2: y -= 1
                return f"{y:04d}-{m:02d}-{d:02d}"
            return None

        df['DateStr'] = df['日期'].apply(parse_date)
        df = df.dropna(subset=['DateStr'])
        df = df.sort_values('DateStr', ascending=True)
        
        return df, target_url
        
    except Exception:
        return None, target_url
    finally:
        driver.quit()

@st.cache_data(ttl=21600)
def get_stock_price(stock_id, refresh_nonce=0):
    # 定義要嘗試的後綴順序
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    
    df = None
    
    for ticker in tickers_to_try:
        try:
            stock = yf.Ticker(ticker)
            temp_df = stock.history(period="2y")
            if not temp_df.empty:
                df = temp_df
                break
        except Exception:
            continue
            
    if df is None or df.empty:
        return None

    try:
        df.index = df.index.tz_localize(None)
        df['DateStr'] = df.index.strftime('%Y-%m-%d')
        
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # ✅ 計算指標
        df = calculate_technical_indicators(df)
        return df
    except Exception:
        return None

# ================= 4. 介面邏輯 (保留原樣) =================

st.title(f"📊 籌碼K線 (TradingView 風格)")

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

# ✅ 初始化搜尋計數 Session State
if "search_counts" not in st.session_state:
    st.session_state.search_counts = {}

with st.sidebar:
    st.header("參數設定")
    
    # ✅ 優化：搜尋功能 (使用 Selectbox + 排序)
    all_stocks = get_all_stock_options()
    
    # 定義排序邏輯：搜尋次數越高的排越前面
    # 如果還沒有搜尋過，預設顯示 2313 (符合原本預設值)
    def get_sort_key(stock_str):
        code = stock_str.split()[0]
        count = st.session_state.search_counts.get(code, 0)
        return -count # 負數讓 sort 變成降序 (次數高的在前面)

    sorted_stocks = sorted(all_stocks, key=get_sort_key)
    
    # 找出原本預設值 "2313" 在列表中的位置，避免報錯
    default_index = 0
    for idx, s in enumerate(sorted_stocks):
        if s.startswith("2313"):
            default_index = idx
            break

    # 使用 selectbox 讓使用者輸入或選擇
    stock_selection = st.selectbox(
        "搜尋股票 (輸入代號或名稱)",
        options=sorted_stocks,
        index=default_index,
        placeholder="請輸入股票代號或名稱..."
    )
    
    # 提取代號
    if stock_selection:
        stock_input = stock_selection.split()[0]
    else:
        stock_input = ""
    
    days_map = {
        "1日": 1, 
        "5日": 5, 
        "10日": 10, 
        "20日": 20, 
        "40日": 40, 
        "60日": 60, 
        "120日": 120, 
        "240日": 240
    }
    days_label = st.selectbox("統計天數 (交易日)", list(days_map.keys()), index=6) 
    selected_days = days_map[days_label]
    
    st.markdown(f"🕒 資料抓取時間: {current_time}")
    
    if st.button("查詢", type="primary"):
        # ✅ 記錄搜尋次數 (增加熱門度)
        if stock_input:
            st.session_state.search_counts[stock_input] = st.session_state.search_counts.get(stock_input, 0) + 1
        st.rerun()
    
    # 強制更新按鈕
    if "refresh_nonce" not in st.session_state:
        st.session_state.refresh_nonce = 0
    if st.button("🔄 強制更新籌碼資料（忽略快取）"):
        st.session_state.refresh_nonce = int(time.time())
        st.rerun()

if stock_input:
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    with st.spinner(f"正在分析 {stock_display} 近 {selected_days} 交易日 ({rank_start_date} ~ {rank_end_date})..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(
            stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce
        )
        
    # ✅ 修改：加入 refresh_nonce
    df_price = get_stock_price(stock_input, st.session_state.refresh_nonce)

    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date}) - 主力買賣超排行")
        st.caption(f"排行總表網址：{target_url}")
        
        # ✅ 保留原本的表格顯示與 RWD 邏輯
        with st.container():
            st.markdown('<div class="desktop-marker"></div>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                render_broker_table(df_buy, sum_buy, COLOR_UP, "🔴 買超前 15 大")
            with col2:
                render_broker_table(df_sell, sum_sell, COLOR_DOWN, "🟢 賣超前 15 大")

        with st.container():
            st.markdown('<div class="mobile-marker"></div>', unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["🔴 買超排行", "🟢 賣超排行"])
            with tab1:
                render_broker_table(df_buy, sum_buy, COLOR_UP, "🔴 買超前 15 大")
            with tab2:
                render_broker_table(df_sell, sum_sell, COLOR_DOWN, "🟢 賣超前 15 大")

        st.markdown("---")

        if df_price is not None and not df_price.empty:
            st.subheader("🔍 TradingView 互動 K 線圖")
            
            # --- 選擇券商 ---
            brokers_list = df_buy['broker'].tolist() + df_sell['broker'].tolist()
            brokers_list = list(dict.fromkeys(brokers_list))
            
            # 這裡改成兩欄，右邊放指標勾選 (✅ 優化：改用 Multiselect)
            col_sel1, col_sel2 = st.columns([1, 2])
            with col_sel1:
                target_broker = st.selectbox("選擇要查看每日明細的券商", brokers_list)
            
            # --- 指標勾選區 (優化版) ---
            with col_sel2:
                # 定義選項
                default_options = [
                    "成交量", "KD", "MACD", "分點買賣超", 
                    "外資", "投信", "自營商"
                ]
                all_options = [
                    "成交量", "KD", "MACD", "分點買賣超", 
                    "布林通道", "融資融券", 
                    "外資", "投信", "自營商", "三大法人"
                ]
                
                selected_indicators = st.multiselect(
                    "顯示副圖指標 (可多選)",
                    options=all_options,
                    default=default_options
                )

                # 將選擇結果映射回 boolean 變數，保持後續邏輯不變
                show_vol = "成交量" in selected_indicators
                show_kd = "KD" in selected_indicators
                show_macd = "MACD" in selected_indicators
                show_chip = "分點買賣超" in selected_indicators
                show_bb = "布林通道" in selected_indicators
                show_margin = "融資融券" in selected_indicators
                show_inst_foreign = "外資" in selected_indicators
                show_inst_trust = "投信" in selected_indicators
                show_inst_dealer = "自營商" in selected_indicators
                show_inst_total = "三大法人" in selected_indicators

            merged_df = None
            target_key = normalize_name(target_broker)
            
            broker_params = None
            if broker_info:
                if target_key in broker_info:
                    broker_params = broker_info[target_key]
                else:
                    for k, v in broker_info.items():
                        if target_key in k or k in target_key:
                            broker_params = v
                            break

            # --- 爬取單一券商明細 (邏輯完全保留) ---
            if broker_params:
                long_start_date = df_price['DateStr'].iloc[0] 
                long_end_date = df_price['DateStr'].iloc[-1] 
                
                broker_key = (broker_params['BHID'], broker_params['b'], broker_params.get('C', '1'))
                merged_key = (stock_input, broker_key, st.session_state.refresh_nonce)

                if st.session_state.get('merged_key') != merged_key:
                    with st.spinner(f"正在爬取 {target_broker} 每日明細..."):
                        broker_daily_df, detail_url = get_specific_broker_daily(
                            stock_input, broker_key, long_start_date, long_end_date, st.session_state.refresh_nonce
                        )
                        
                        if broker_daily_df is not None and not broker_daily_df.empty:
                            broker_daily_df = broker_daily_df.drop_duplicates(subset=["DateStr"], keep="last").sort_values('DateStr')
                            merged_df = pd.merge(df_price, broker_daily_df, on='DateStr', how='left')
                            merged_df['買賣超_Final'] = merged_df['買賣超_Calc'].fillna(0)
                            
                            st.session_state['merged_df'] = merged_df
                            st.session_state['merged_key'] = merged_key
                        else:
                            st.session_state.pop('merged_df', None)
                            st.session_state['merged_key'] = merged_key
                            st.warning("⚠️ 該券商明細抓取失敗，顯示純股價")
                else:
                    merged_df = st.session_state.get('merged_df')

            # --- 準備繪圖資料 (TradingView 格式) ---
            plot_df = merged_df if merged_df is not None else df_price
            plot_df = plot_df.copy()
            plot_df["Date"] = pd.to_datetime(plot_df["DateStr"], errors="coerce")
            plot_df = plot_df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

            # ✅ 新增：計算累積買賣超
            if '買賣超_Final' in plot_df.columns:
                plot_df['cumulative_chip'] = plot_df['買賣超_Final'].fillna(0).cumsum()

            # ✅ 新增：如果勾選了三大法人(含單一或合併)或融資融券，進行爬蟲並合併，並計算累積值
            if show_inst_foreign or show_inst_trust or show_inst_dealer or show_inst_total:
                inst_df = get_institutional_data(stock_input, long_start_date, long_end_date)
                if inst_df is not None:
                    plot_df = pd.merge(plot_df, inst_df, on='DateStr', how='left')
                    # 計算累積值
                    if '外資買賣超' in plot_df.columns: plot_df['cum_foreign'] = plot_df['外資買賣超'].fillna(0).cumsum()
                    if '投信買賣超' in plot_df.columns: plot_df['cum_trust'] = plot_df['投信買賣超'].fillna(0).cumsum()
                    if '自營商買賣超' in plot_df.columns: plot_df['cum_dealer'] = plot_df['自營商買賣超'].fillna(0).cumsum()
            
            if show_margin:
                margin_df = get_margin_data(stock_input, long_start_date, long_end_date)
                if margin_df is not None:
                    plot_df = pd.merge(plot_df, margin_df, on='DateStr', how='left')

            # ========= 🚀 改用多 chart 堆疊模式 =========
            
            # ✅ 修正：新增 time_visible 參數 和 title (浮水印)
            def make_opts(height, title=None, time_visible=True):
                opts = {
                    "layout": {
                        "textColor": "white",
                        "background": {"type": "solid", "color": "#131722"},
                    },
                    # ✅ 新增：設定日期格式為台灣慣用 (yyyy年MM月dd日)
                    "localization": {
                        "locale": "zh-TW",
                        "dateFormat": "yyyy年MM月dd日",
                    },
                    "grid": {
                        "vertLines": {"color": "rgba(42, 46, 57, 0.5)"},
                        "horzLines": {"color": "rgba(42, 46, 57, 0.5)"},
                    },
                    "timeScale": {
                        "borderColor": "rgba(197, 203, 206, 0.8)",
                        "visible": time_visible, # ✅ 控制時間軸顯示
                        "timeVisible": False     # ✅ 隱藏十字線標籤中的時間部分 (00:00:00)
                    },
                    "crosshair": {"mode": 1},
                    "height": height,
                }
                
                # ✅ 浮水印設定 (左上角標題)
                if title:
                    opts["watermark"] = {
                        "visible": True,
                        "fontSize": 18,
                        "horzAlign": 'left',
                        "vertAlign": 'top',
                        "color": 'rgba(255, 255, 255, 0.7)',
                        "text": title,
                    }
                return opts

            # ✅ [FIX START] 修正變數作用域：將 charts_payload 的初始化移到最上層
            charts_payload = [] 
            
            # ✅ [FIX START] 預先初始化所有數據變數，防止 NameError
            vol_data = []
            k_data, d_data = [], []
            dif_data, dea_data, hist_data = [], [], []
            chip_data, chip_cumulative_data = [], []
            f_hist, f_line = [], []
            t_hist, t_line = [], []
            d_hist, d_line = [], []
            margin_long_bal_data, margin_long_diff_data = [], []
            margin_short_bal_data, margin_short_diff_data = [], []

            # 1. K線資料
            candlestick_data = []
            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']) and not pd.isna(row['Close']):
                    candlestick_data.append({
                        "time": row['DateStr'],
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close'])
                    })

            # 2. 均線資料
            ma_base_options = {
                "lastValueVisible": False,  # ✅ [FIX] 隱藏右側軸標籤，讓數值顯示在左上角 Legend
                "priceLineVisible": False, 
                "crosshairMarkerVisible": True, 
                "lineWidth": 1
            }
            
            ma5_data = [{"time": row['DateStr'], "value": float(row['MA5'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA5'])]
            ma10_data = [{"time": row['DateStr'], "value": float(row['MA10'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA10'])]
            ma20_data = [{"time": row['DateStr'], "value": float(row['MA20'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA20'])]
            ma60_data = [{"time": row['DateStr'], "value": float(row['MA60'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA60'])]

            # ✅ 數據準備：布林通道
            bb_up_data = []
            bb_low_data = []
            if show_bb:
                bb_up_data = [{"time": row['DateStr'], "value": float(row['BB_Up'])} for i, row in plot_df.iterrows() if not pd.isna(row['BB_Up'])]
                bb_low_data = [{"time": row['DateStr'], "value": float(row['BB_Low'])} for i, row in plot_df.iterrows() if not pd.isna(row['BB_Low'])]

            # 1. 主圖：K線 + MA + BB (✅ time_visible=True)
            # ✅ [FIX] 確保主圖無論如何都會被加入，不依賴任何條件
            main_series = [
                {
                    "type": "Candlestick",
                    "data": candlestick_data,
                    "options": {
                        "upColor": COLOR_UP,
                        "downColor": COLOR_DOWN,
                        "borderUpColor": COLOR_UP,
                        "borderDownColor": COLOR_DOWN,
                        "wickUpColor": COLOR_UP,
                        "wickDownColor": COLOR_DOWN,
                    },
                },
                {"type": "Line", "data": ma5_data,  "options": {**ma_base_options, "color": "orange", "title": "MA5"}},
                {"type": "Line", "data": ma10_data, "options": {**ma_base_options, "color": "cyan",   "title": "MA10"}},
                {"type": "Line", "data": ma20_data, "options": {**ma_base_options, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}},
                {"type": "Line", "data": ma60_data, "options": {**ma_base_options, "color": "lime",   "lineWidth": 2, "title": "MA60"}},
            ]
            
            # 加入布林通道
            if show_bb:
                main_series.append({"type": "Line", "data": bb_up_data, "options": {**ma_base_options, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB上軌"}})
                main_series.append({"type": "Line", "data": bb_low_data, "options": {**ma_base_options, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB下軌"}})

            charts_payload.append({"chart": make_opts(400, "股價", True), "series": main_series})

            # 2. 副圖：成交量 (✅ time_visible=False)
            if show_vol:
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Volume']):
                        color = COLOR_UP if row['Close'] >= row['Open'] else COLOR_DOWN
                        vol_data.append({
                            "time": row['DateStr'],
                            "value": float(row['Volume']), 
                            "color": color
                        })
                        
                vol_series = [{
                    "type": "Histogram",
                    "data": vol_data,
                    "options": {
                        "priceFormat": {"type": "volume"},
                        "priceScaleId": "right",
                        "title": "成交量",
                        "priceLineVisible": False,
                        "crosshairMarkerVisible": True,
                        "lastValueVisible": False # ✅ [FIX] 隱藏右側軸標籤
                    }
                }]
                charts_payload.append({"chart": make_opts(150, "成交量", False), "series": vol_series})

            # 3. 副圖：KD (✅ time_visible=False)
            if show_kd and 'K' in plot_df.columns:
                k_data = [{"time": row['DateStr'], "value": float(row['K'])} for i, row in plot_df.iterrows() if not pd.isna(row['K'])]
                d_data = [{"time": row['DateStr'], "value": float(row['D'])} for i, row in plot_df.iterrows() if not pd.isna(row['D'])]
                
                kd_series = [
                    {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K值", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": d_data, "options": {"color": "cyan",   "lineWidth": 1, "title": "D值", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                ]
                charts_payload.append({"chart": make_opts(150, "KD", False), "series": kd_series})

            # 4. 副圖：MACD (✅ time_visible=False)
            if show_macd and 'DIF' in plot_df.columns:
                dif_data = [{"time": row['DateStr'], "value": float(row['DIF'])} for i, row in plot_df.iterrows() if not pd.isna(row['DIF'])]
                dea_data = [{"time": row['DateStr'], "value": float(row['DEA'])} for i, row in plot_df.iterrows() if not pd.isna(row['DEA'])]
                for i, row in plot_df.iterrows():
                    val = row['MACD_Hist']
                    if not pd.isna(val):
                        color = COLOR_UP if val >= 0 else COLOR_DOWN
                        hist_data.append({"time": row['DateStr'], "value": float(val), "color": color})
                        
                macd_series = [
                    {"type": "Histogram", "data": hist_data, "options": {"title": "MACD柱狀", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": dif_data, "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": dea_data, "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                ]
                charts_payload.append({"chart": make_opts(150, "MACD", False), "series": macd_series})

            # 5. 副圖：分點買賣超 (雙軸) (✅ time_visible=False)
            if show_chip and '買賣超_Final' in plot_df.columns:
                for i, row in plot_df.iterrows():
                    val = row.get('買賣超_Final')
                    if not pd.isna(val):
                        color = COLOR_UP if val > 0 else (COLOR_DOWN if val < 0 else "gray")
                        chip_data.append({
                            "time": row['DateStr'],
                            "value": float(val), 
                            "color": color
                        })
                    
                    cum_val = row.get('cumulative_chip')
                    if not pd.isna(cum_val):
                        chip_cumulative_data.append({
                            "time": row['DateStr'],
                            "value": float(cum_val)
                        })
                        
                chip_series = [
                    {
                        "type": "Histogram",
                        "data": chip_data,
                        "options": {"title": f"{target_broker} 買賣超", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False} # ✅ [FIX]
                    },
                    {
                        "type": "Line",
                        "data": chip_cumulative_data,
                        "options": {"title": "分點累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False} # ✅ [FIX]
                    }
                ]
                charts_payload.append({"chart": make_opts(200, "分點買賣超", False), "series": chip_series})

            # 6. [NEW] 副圖：三大法人 - 外資獨立 (✅ time_visible=False)
            # [FIX START] 拆分三大法人數據
            combined_inst_series = [] # 合併圖表用的

            # 只要有勾選任一法人相關選項，就準備所有資料
            if (show_inst_foreign or show_inst_trust or show_inst_dealer or show_inst_total) and '外資買賣超' in plot_df.columns:
                for i, row in plot_df.iterrows():
                    # 外資資料準備
                    val = row.get('外資買賣超')
                    cum = row.get('cum_foreign')
                    if not pd.isna(val):
                        color = COLOR_UP if val > 0 else (COLOR_DOWN if val < 0 else "gray")
                        f_hist.append({"time": row['DateStr'], "value": float(val), "color": color})
                    if not pd.isna(cum):
                        f_line.append({"time": row['DateStr'], "value": float(cum)})
                    
                    # 投信資料準備
                    val = row.get('投信買賣超')
                    cum = row.get('cum_trust')
                    if not pd.isna(val):
                        color = COLOR_UP if val > 0 else (COLOR_DOWN if val < 0 else "gray")
                        t_hist.append({"time": row['DateStr'], "value": float(val), "color": color})
                    if not pd.isna(cum):
                        t_line.append({"time": row['DateStr'], "value": float(cum)})
                            
                    # 自營商資料準備
                    val = row.get('自營商買賣超')
                    cum = row.get('cum_dealer')
                    if not pd.isna(val):
                        color = COLOR_UP if val > 0 else (COLOR_DOWN if val < 0 else "gray")
                        d_hist.append({"time": row['DateStr'], "value": float(val), "color": color})
                    if not pd.isna(cum):
                        d_line.append({"time": row['DateStr'], "value": float(cum)})

            if show_inst_foreign and f_hist:
                foreign_series = [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "外資買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": f_line, "options": {"title": "外資累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}} # ✅ [FIX]
                ]
                charts_payload.append({"chart": make_opts(150, "外資", False), "series": foreign_series})

            # 7. [NEW] 副圖：三大法人 - 投信獨立 (✅ time_visible=False)
            if show_inst_trust and t_hist:
                trust_series = [
                    {"type": "Histogram", "data": t_hist, "options": {"title": "投信買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": t_line, "options": {"title": "投信累積", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}} # ✅ [FIX]
                ]
                charts_payload.append({"chart": make_opts(150, "投信", False), "series": trust_series})

            # 8. [NEW] 副圖：三大法人 - 自營商獨立 (✅ time_visible=False)
            if show_inst_dealer and d_hist:
                dealer_series = [
                    {"type": "Histogram", "data": d_hist, "options": {"title": "自營買賣", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}, # ✅ [FIX]
                    {"type": "Line", "data": d_line, "options": {"title": "自營累積", "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}} # ✅ [FIX]
                ]
                charts_payload.append({"chart": make_opts(150, "自營商", False), "series": dealer_series})

            # 9. [NEW] 副圖：三大法人 - 合併 (當勾選「三大法人」時顯示)
            if show_inst_total:
                if f_hist: combined_inst_series.append({"type": "Histogram", "data": f_hist, "options": {"title": "外資單日", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]
                if f_line: combined_inst_series.append({"type": "Line", "data": f_line, "options": {"title": "外資累積", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]
                
                if t_hist: combined_inst_series.append({"type": "Histogram", "data": t_hist, "options": {"title": "投信單日", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]
                if t_line: combined_inst_series.append({"type": "Line", "data": t_line, "options": {"title": "投信累積", "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]
                
                if d_hist: combined_inst_series.append({"type": "Histogram", "data": d_hist, "options": {"title": "自營單日", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]
                if d_line: combined_inst_series.append({"type": "Line", "data": d_line, "options": {"title": "自營累積", "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}) # ✅ [FIX]

                if combined_inst_series:
                    charts_payload.append({"chart": make_opts(200, "三大法人(合)", False), "series": combined_inst_series})

            # ✅ 數據準備：融資融券 (雙軸：增減量 + 累積餘額)
            # [FIX START] 顯式初始化 margin_series，避免 NameError
            margin_long_series = []
            margin_short_series = []
            
            if show_margin and '融資餘額' in plot_df.columns:
                for i, row in plot_df.iterrows():
                    # 融資餘額 (Line)
                    val_mb = row.get('融資餘額')
                    if not pd.isna(val_mb):
                        margin_long_bal_data.append({"time": row['DateStr'], "value": float(val_mb)})
                    # 融券餘額 (Line)
                    val_sb = row.get('融券餘額')
                    if not pd.isna(val_sb):
                        margin_short_bal_data.append({"time": row['DateStr'], "value": float(val_sb)})
                        
                    # 融資增減 (Histogram) - 使用帶透明度的紅/綠
                    val_md = row.get('融資增減')
                    if not pd.isna(val_md):
                        # 紅(增)/綠(減) + 透明度
                        color = 'rgba(239, 83, 80, 0.7)' if val_md > 0 else ('rgba(38, 166, 154, 0.7)' if val_md < 0 else "gray")
                        margin_long_diff_data.append({"time": row['DateStr'], "value": float(val_md), "color": color})
                        
                    # 融券增減 (Histogram) - 使用帶透明度的黃/藍
                    val_sd = row.get('融券增減')
                    if not pd.isna(val_sd):
                        # 黃(增)/藍(減) + 透明度
                        color = 'rgba(255, 215, 0, 0.7)' if val_sd > 0 else ('rgba(0, 191, 255, 0.7)' if val_sd < 0 else "gray")
                        margin_short_diff_data.append({"time": row['DateStr'], "value": float(val_sd), "color": color})
            
            # 10. 副圖：融資 (雙軸：增減量 + 累積餘額)
            if show_margin and (margin_long_bal_data or margin_long_diff_data):
                # 融資增減 (Histogram)
                if margin_long_diff_data:
                    margin_long_series.append({"type": "Histogram", "data": margin_long_diff_data, "options": {"title": "融資增減", "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": True}}) # ✅ [FIX]
                # 融資餘額 (Line)
                if margin_long_bal_data:
                    margin_long_series.append({"type": "Line", "data": margin_long_bal_data, "options": {"title": "融資餘額", "color": "#00FF00", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": True}}) # ✅ [FIX]
                
                charts_payload.append({"chart": make_opts(150, "融資", False), "series": margin_long_series})

            # 11. 副圖：融券 (雙軸：增減量 + 累積餘額)
            if show_margin and (margin_short_bal_data or margin_short_diff_data):
                # 融券增減 (Histogram)
                if margin_short_diff_data:
                    margin_short_series.append({"type": "Histogram", "data": margin_short_diff_data, "options": {"title": "融券增減", "priceScaleId": "right", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": True}}) # ✅ [FIX]
                # 融券餘額 (Line)
                if margin_short_bal_data:
                    margin_short_series.append({"type": "Line", "data": margin_short_bal_data, "options": {"title": "融券餘額", "color": "#FF0000", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "lastValueVisible": False, "crosshairMarkerVisible": True}}) # ✅ [FIX]
                
                charts_payload.append({"chart": make_opts(150, "融券", False), "series": margin_short_series})

            # ✅ 一次 render：多張 chart 會依序往下排
            # ✅ 新增 key 值：包含指標選擇字串，強制讓圖表在結構改變時重繪，解決 K 線圖消失問題
            render_key = f"tv_chart_stack_{stock_input}_{''.join(sorted(selected_indicators))}"
            renderLightweightCharts(charts_payload, key=render_key)

    else:
        # ✅ 新增：明確告訴使用者為什麼沒圖 (當資料完全抓不到時)
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n"
                "1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n"
                "2. 股票代號輸入錯誤。\n"
                "3. Yahoo API 暫時連線失敗，請稍後再試。")

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

# ================= 2. 輔助函式 (保留原樣) =================

def normalize_name(name):
    return str(name).strip().replace(" ", "").replace("　", "")

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

# ✅ 輔助函式：計算 KD 與 MACD
def calculate_technical_indicators(df):
    df = df.copy()
    # 1. 計算 KD (9, 3, 3)
    rsv_period = 9
    
    df['9_High'] = df['High'].rolling(window=rsv_period).max()
    df['9_Low'] = df['Low'].rolling(window=rsv_period).min()
    df['RSV'] = 100 * ((df['Close'] - df['9_Low']) / (df['9_High'] - df['9_Low']))
    df['RSV'] = df['RSV'].fillna(50)
    
    # 計算 K, D (平滑計算)
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

    # 2. 計算 MACD (12, 26, 9)
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = 2 * (df['DIF'] - df['DEA'])
    
    return df

# ================= 3. 爬蟲核心 (保留原樣) =================

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
def get_stock_price(stock_id):
    ticker = f"{stock_id}.TW" if not stock_id.endswith('.TW') else stock_id
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty:
            ticker = f"{stock_id}.TWO"
            stock = yf.Ticker(ticker)
            df = stock.history(period="2y")
        if df.empty: return None
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

with st.sidebar:
    st.header("參數設定")
    stock_input_raw = st.text_input("股票代號", value="2313")
    stock_input = re.sub(r'\D', '', str(stock_input_raw)) if stock_input_raw else ""
    
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
        
    df_price = get_stock_price(stock_input)

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
            
            # 這裡改成兩欄，右邊放指標勾選
            col_sel1, col_sel2 = st.columns([1, 2])
            with col_sel1:
                target_broker = st.selectbox("選擇要查看每日明細的券商", brokers_list)
            
            # --- 指標勾選區 ---
            with col_sel2:
                st.write("顯示副圖指標：")
                col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                show_vol = col_c1.checkbox("成交量", value=True)
                show_kd = col_c2.checkbox("KD", value=False)
                show_macd = col_c3.checkbox("MACD", value=False)
                show_chip = col_c4.checkbox("分點買賣超", value=True)

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
                "lastValueVisible": False, 
                "priceLineVisible": False, 
                "crosshairMarkerVisible": False,
                "lineWidth": 1
            }
            
            ma5_data = [{"time": row['DateStr'], "value": float(row['MA5'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA5'])]
            ma10_data = [{"time": row['DateStr'], "value": float(row['MA10'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA10'])]
            ma20_data = [{"time": row['DateStr'], "value": float(row['MA20'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA20'])]
            ma60_data = [{"time": row['DateStr'], "value": float(row['MA60'])} for i, row in plot_df.iterrows() if not pd.isna(row['MA60'])]

            series_list = []

            # === 主圖 (K線 + MA) [Panel 0] ===
            # ✅ 重點修正：明確指定 Panel 0，確保它佔據主區域
            series_list.append({
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
                "panel": 0 
            })
            
            # 加入均線 (Panel 0)
            series_list.append({"type": "Line", "data": ma5_data, "options": {**ma_base_options, "color": "orange", "title": "MA5"}, "panel": 0})
            series_list.append({"type": "Line", "data": ma10_data, "options": {**ma_base_options, "color": "cyan", "title": "MA10"}, "panel": 0})
            series_list.append({"type": "Line", "data": ma20_data, "options": {**ma_base_options, "color": "#ff00ff", "lineWidth": 2, "title": "MA20"}, "panel": 0})
            series_list.append({"type": "Line", "data": ma60_data, "options": {**ma_base_options, "color": "lime", "lineWidth": 2, "title": "MA60"}, "panel": 0})

            # === 副圖管理 (從 Panel 1 開始遞增) ===
            next_panel_id = 1
            
            # 1. 成交量 (Volume)
            if show_vol:
                vol_data = []
                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Volume']):
                        color = COLOR_UP if row['Close'] >= row['Open'] else COLOR_DOWN
                        vol_data.append({
                            "time": row['DateStr'],
                            "value": float(row['Volume']), 
                            "color": color
                        })
                
                series_list.append({
                    "type": "Histogram",
                    "data": vol_data,
                    "options": {
                        "priceFormat": {"type": "volume"},
                        "priceScaleId": "right", 
                    },
                    "panel": next_panel_id # ✅ 使用遞增的 ID
                })
                next_panel_id += 1

            # 2. KD 指標
            if show_kd and 'K' in plot_df.columns:
                k_data = [{"time": row['DateStr'], "value": float(row['K'])} for i, row in plot_df.iterrows() if not pd.isna(row['K'])]
                d_data = [{"time": row['DateStr'], "value": float(row['D'])} for i, row in plot_df.iterrows() if not pd.isna(row['D'])]
                
                series_list.append({
                    "type": "Line",
                    "data": k_data,
                    "options": {"color": "orange", "lineWidth": 1, "title": "K(9,3,3)", "priceScaleId": "right"},
                    "panel": next_panel_id
                })
                series_list.append({
                    "type": "Line",
                    "data": d_data,
                    "options": {"color": "cyan", "lineWidth": 1, "title": "D", "priceScaleId": "right"},
                    "panel": next_panel_id
                })
                next_panel_id += 1

            # 3. MACD 指標
            if show_macd and 'DIF' in plot_df.columns:
                dif_data = [{"time": row['DateStr'], "value": float(row['DIF'])} for i, row in plot_df.iterrows() if not pd.isna(row['DIF'])]
                dea_data = [{"time": row['DateStr'], "value": float(row['DEA'])} for i, row in plot_df.iterrows() if not pd.isna(row['DEA'])]
                hist_data = []
                for i, row in plot_df.iterrows():
                    val = row['MACD_Hist']
                    if not pd.isna(val):
                        color = COLOR_UP if val >= 0 else COLOR_DOWN
                        hist_data.append({"time": row['DateStr'], "value": float(val), "color": color})
                
                series_list.append({
                    "type": "Histogram",
                    "data": hist_data,
                    "options": {"title": "MACD Hist", "priceScaleId": "right"},
                    "panel": next_panel_id
                })
                series_list.append({
                    "type": "Line",
                    "data": dif_data,
                    "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF", "priceScaleId": "right"},
                    "panel": next_panel_id
                })
                series_list.append({
                    "type": "Line",
                    "data": dea_data,
                    "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA", "priceScaleId": "right"},
                    "panel": next_panel_id
                })
                next_panel_id += 1

            # 4. 分點買賣超 (Chip) - ✅ 修改：加入累積折線圖並重疊
            if show_chip and '買賣超_Final' in plot_df.columns:
                chip_data = []
                chip_cumulative_data = [] # ✅ 新增累積資料列表
                for i, row in plot_df.iterrows():
                    # 單日買賣超
                    val = row.get('買賣超_Final')
                    if not pd.isna(val):
                        color = COLOR_UP if val > 0 else (COLOR_DOWN if val < 0 else "gray")
                        chip_data.append({
                            "time": row['DateStr'],
                            "value": float(val), 
                            "color": color
                        })
                    
                    # ✅ 累積買賣超
                    cum_val = row.get('cumulative_chip')
                    if not pd.isna(cum_val):
                        chip_cumulative_data.append({
                            "time": row['DateStr'],
                            "value": float(cum_val)
                        })
                
                # 加入單日買賣超直方圖
                series_list.append({
                    "type": "Histogram",
                    "data": chip_data,
                    "options": {
                        "title": f"{target_broker} 每日買賣超",
                        "priceScaleId": "right"
                    },
                    "panel": next_panel_id # ✅ 同一個 Panel
                })

                # ✅ 加入累積買賣超折線圖 (疊加在同一個 Panel)
                series_list.append({
                    "type": "Line",
                    "data": chip_cumulative_data,
                    "options": {
                        "title": f"{target_broker} 累積買賣超",
                        "color": "#FFD700", # 金黃色
                        "lineWidth": 2,
                        "priceScaleId": "left" # ✅ 使用左側刻度以區分
                    },
                    "panel": next_panel_id # ✅ 同一個 Panel
                })
                
                next_panel_id += 1

            # === 圖表全域設定 ===
            # ✅ 計算總高度：主圖 400px + 每個副圖 150px
            total_height = 400 + (next_panel_id - 1) * 150

            chartOptions = {
                "layout": {
                    "textColor": 'white',
                    "background": {
                        "type": 'solid',
                        "color": '#131722' # TradingView 深色背景
                    }
                },
                "grid": {
                    "vertLines": {"color": "rgba(42, 46, 57, 0.5)"},
                    "horzLines": {"color": "rgba(42, 46, 57, 0.5)"}
                },
                "timeScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)",
                    "timeVisible": True
                },
                "crosshair": {
                    "mode": 1
                },
                "height": total_height # ✅ 套用計算出的總高度
            }

            # ✅ 正確的呼叫方式：List[Dict]
            charts_payload = [
                {
                    "chart": chartOptions,
                    "series": series_list,
                }
            ]
            renderLightweightCharts(charts_payload, key="tv_chart")

    else:
        st.error(f"⚠️ 查無資料，請確認股票代號或稍後再試。")

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
from streamlit_lightweight_charts import renderLightweightCharts

# ================= 1. 系統設定 =================

st.set_page_config(layout="wide", page_title="籌碼K線", initial_sidebar_state="collapsed")

# ✅ 讀取並載入外部 CSS 檔案
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"⚠️ 找不到 {file_name}，請確認檔案是否在同一目錄下。")

# 呼叫 CSS 載入函式
local_css("style.css")

# ✅ 初始化主題狀態 (預設暗色圖表)
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# ✅ [CRITICAL FIX] 初始化 K線指標選擇狀態
if "kline_indicators_selector" not in st.session_state:
    st.session_state.kline_indicators_selector = ["成交量", "KDJ", "MACD"]

# ✅ [NEW] 初始化 K線分點相關狀態
if "kline_broker_days" not in st.session_state:
    st.session_state.kline_broker_days = "20日"
if "kline_selected_brokers" not in st.session_state:
    st.session_state.kline_selected_brokers = []

# ✅ 定義顏色變數 (PAGE_BG 固定，只切換圖表顏色)
PAGE_BG = "#131722" 

if st.session_state.theme == 'dark':
    CHART_BG = "#131722"
    CHART_TEXT = "white"
    GRID_COLOR = "rgba(42, 46, 57, 0.5)"
    MULTI_LINE_COLOR = "white"
else:
    # 亮色模式只影響圖表
    CHART_BG = "#ffffff"
    CHART_TEXT = "black"
    GRID_COLOR = "rgba(42, 46, 57, 0.1)"
    MULTI_LINE_COLOR = "#000000"

COLOR_UP = '#ef5350' # 紅色 (上漲)
COLOR_DOWN = '#26a69a' # 綠色 (下跌)

# ================= 2. 輔助函式 =================

def normalize_name(name):
    return str(name).strip().replace(" ", "").replace("　", "")

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
    except:
        return ""

def render_broker_table(df, sum_data, color_hex, title, key_id):
    if "買超" in title:
        label_total = "🔴 合計買超"
        label_avg = "🔴 均價"
    else:
        label_total = "🟢 合計賣超"
        label_avg = "🟢 均價"

    full_config = {
        "broker": "券商分點",
        "buy": st.column_config.NumberColumn("買進", format="%d"),
        "sell": st.column_config.NumberColumn("賣出", format="%d"),
        "net": st.column_config.NumberColumn("買賣超", format="%d"),
        "pct": "佔比"
    }
    
    event = st.dataframe(
        df.style.map(lambda x: f'color: {color_hex}; font-weight: bold', subset=['net']),
        use_container_width=True, 
        height=400, 
        hide_index=True, 
        column_config=full_config,
        on_select="rerun", 
        selection_mode="single-row", 
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

    if len(event.selection.rows) > 0:
        selected_idx = event.selection.rows[0]
        return df.iloc[selected_idx]['broker']
    return None

def calculate_technical_indicators(df):
    df = df.copy()
    
    # BB
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Low'] = df['BB_Mid'] - 2 * df['BB_Std']

    # KDJ
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
    df['J'] = 3 * df['K'] - 2 * df['D']

    # MACD
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = 2 * (df['DIF'] - df['DEA'])

    # RSI
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=5, adjust=False).mean() 
    ema_down = down.ewm(com=5, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))

    # MA
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['MA240'] = df['Close'].rolling(window=240).mean()
    
    df = df.replace([np.inf, -np.inf], np.nan)

    return df

def resample_data(df, period):
    if period == '日K':
        return df
    
    df = df.copy()
    df.index = pd.to_datetime(df['DateStr'])
    
    rule = 'W-MON' if period == '週K' else 'ME'
    
    agg_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    
    resampled = df.resample(rule).agg(agg_dict).dropna()
    resampled['DateStr'] = resampled.index.strftime('%Y-%m-%d')
    resampled = resampled.reset_index(drop=True)
    
    resampled = calculate_technical_indicators(resampled)
    return resampled

def make_opts(height, title=None, time_visible=True, scale_mode="normal", font_size=12, top_margin=0.0, bottom_margin=0.0, right_offset=5):
    h = height
    fs = font_size
    min_w = 75

    opts = {
        "layout": {
            "textColor": CHART_TEXT, 
            "background": {"type": "solid", "color": CHART_BG},
            "fontSize": fs 
        },
        "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
        "grid": {"vertLines": {"color": GRID_COLOR}, "horzLines": {"color": GRID_COLOR}},
        "timeScale": {
            "borderColor": "rgba(197, 203, 206, 0.8)", 
            "visible": time_visible, 
            "timeVisible": True, 
            "secondsVisible": False,
            "barSpacing": 12, 
            "rightOffset": right_offset, 
        },
        "rightPriceScale": {
            "borderColor": "rgba(197, 203, 206, 0.8)", 
            "visible": True, 
            "minimumWidth": min_w, 
            "autoScale": True,
            "scaleMargins": {
                "top": top_margin, 
                "bottom": bottom_margin
            }
        },
        "crosshair": {
            "mode": 1, 
            "vertLine": {"visible": True, "style": 0, "width": 1, "color": 'rgba(255, 255, 255, 0.4)', "labelVisible": True},
            "horzLine": {
                "visible": True, 
                "labelVisible": True,
                "labelBackgroundColor": '#1E88E5'
            }
        },
        "height": h, 
        "handleScale": {
            "axisPressedMouseMove": True,
        },
        "handleScroll": {
            "mouseWheel": True,
            "pressedMouseMove": True,
        },
    }
    if scale_mode == "rsi":
        opts["rightPriceScale"] = {
            "visible": True, "autoScale": False, "mode": 0, "maxValue": 100, "minValue": 0, "minimumWidth": min_w,
            "scaleMargins": {"top": 0.05, "bottom": 0.05} 
        }
    if title:
        watermark_color = 'rgba(255, 255, 255, 0.2)' if st.session_state.theme == 'dark' else 'rgba(0, 0, 0, 0.1)'
        opts["watermark"] = {"visible": True, "fontSize": 20, "horzAlign": 'left', "vertAlign": 'top', "color": watermark_color, "text": title}
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

    options.page_load_strategy = 'eager'

    prefs = {
        "profile.managed_default_content_settings.images": 2,          
        "profile.default_content_setting_values.notifications": 2,     
        "profile.managed_default_content_settings.stylesheets": 2,     
        "profile.managed_default_content_settings.cookies": 2,         
        "profile.managed_default_content_settings.javascript": 1,      
        "profile.managed_default_content_settings.plugins": 1,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    options.add_experimental_option("prefs", prefs)
    
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    
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
                    time.sleep(0.1) 
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

@st.cache_data(persist="disk", ttl=604800)
def get_shareholding_data(stock_id: str, refresh_nonce: int = 0):
    driver = get_driver()
    url = f"https://norway.twsthr.info/StockHolders.aspx?STOCK={stock_id}"
    
    try:
        driver.get(url)
        summary_xpath = "/html/body/form/div[4]/div/div[2]/div/div[2]/div/table/tbody/tr[4]/td/table/tbody/tr[2]/td/div[1]/table"

        WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, summary_xpath))
        )
        summary_df = None
        try:
            tbl_summary = driver.find_element(By.XPATH, summary_xpath)
            summary_df = pd.read_html(StringIO(tbl_summary.get_attribute("outerHTML")))[0]
        except Exception:
            pass
            
        ratio_df = None
        try:
            tab_ratio = driver.find_element(By.XPATH, "/html/body/form/div[4]/div/div[2]/div/div[2]/div/table/tbody/tr[4]/td/table/tbody/tr[1]/td/div/ul/li[3]/a/span")
            driver.execute_script("arguments[0].click();", tab_ratio)
            time.sleep(1) 
            
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

def process_shareholding_df(ratio_df: pd.DataFrame, large_threshold: int, retail_threshold: int) -> pd.DataFrame | None:
    if ratio_df is None or ratio_df.empty: return None
    
    df = ratio_df.copy()
    if df.shape[1] < 18: return None
    
    col_map = {
        3: 1, 4: 5, 5: 10, 6: 15, 7: 20, 8: 30, 9: 40, 10: 50,
        11: 100, 12: 200, 13: 400, 14: 600, 15: 800, 16: 1000, 17: 99999999 
    }
    
    out = []
    
    for i, row in df.iterrows():
        try:
            d_val = str(row.iloc[2])
            d_str = d_val.replace("/", "").replace("-", "")
            
            if not re.match(r"^\d{8}$", d_str): continue
            
            date_fmt = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
            
            large_ratio = 0.0
            retail_ratio = 0.0
            
            for col_idx, upper in col_map.items():
                val_str = str(row.iloc[col_idx]).replace("%", "").replace(",", "")
                val = float(val_str) if val_str != 'nan' else 0.0
                
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
                
                if upper <= retail_threshold:
                    retail_ratio += val
                
                if lower >= large_threshold:
                    large_ratio += val
            
            out.append({
                "DateStr": date_fmt,
                "日期": date_fmt,
                "大戶持股(%)": round(large_ratio, 2),
                "散戶持股(%)": round(retail_ratio, 2),
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
            temp_df = stock.history(period="10y") 
            if not temp_df.empty:
                # ✅ [FIX] 將成交量單位由「股」轉為「張」 (除以 1000)
                temp_df['Volume'] = temp_df['Volume'] / 1000
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

@st.cache_data(ttl=300) 
def get_intraday_data(stock_id, interval):
    tickers_to_try = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    df = None
    
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
            temp_df = stock.history(period="60d", interval=yf_interval)
            if not temp_df.empty:
                # ✅ [FIX] 將成交量單位由「股」轉為「張」 (除以 1000)
                temp_df['Volume'] = temp_df['Volume'] / 1000
                df = temp_df
                break
        except: continue
        
    if df is None or df.empty: return None

    try:
        if df.index.tz is not None:
             df.index = df.index.tz_convert('Asia/Taipei').tz_localize(None)
        
        df['DateStr'] = df.index.strftime('%Y-%m-%d %H:%M')
        df = calculate_technical_indicators(df)
        return df
    except: return None

@st.cache_data(ttl=21600, show_spinner=False)
def get_wantgoo_data(stock_id, refresh_nonce):
    SB_LIB_PATH = "/tmp/sb_lib"
    os.makedirs(SB_LIB_PATH, exist_ok=True)
    
    if not os.path.exists(os.path.join(SB_LIB_PATH, "seleniumbase")):
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", 
                "seleniumbase", "pandas", "lxml", 
                "-t", SB_LIB_PATH, 
                "--no-cache-dir", "--quiet"
            ], check=True)
        except subprocess.CalledProcessError:
            pass 

    scraper_script = r"""
import sys
import os

sb_lib_path = "/tmp/sb_lib"
if sb_lib_path not in sys.path:
    sys.path.insert(0, sb_lib_path)

import pandas as pd
try:
    from seleniumbase import SB
except ImportError:
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

stock_id = "{stock_id}"
url = f"https://www.wantgoo.com/stock/{stock_id}/major-investors/main-trend"
MAX_RETRY = 4

def log_err(msg):
    sys.stderr.write(f"[ChildProcess] {msg}\n")

def main():
    try:
        with SB(uc=True, headless=True, locale_code="zh-TW") as sb:
            for attempt in range(1, MAX_RETRY + 1):
                try:
                    sb.uc_open_with_reconnect(url, reconnect_time=4)
                    
                    if "Just a moment" in sb.get_title():
                        log_err("Detected Cloudflare interstitial, waiting...")
                        sb.sleep(6)
                    
                    try:
                        sb.wait_for_element("table", timeout=15)
                    except:
                        log_err("Table element not found instantly, waiting more...")
                        sb.sleep(3)

                    html = sb.get_page_source()
                    
                    try:
                        dfs = pd.read_html(StringIO(html))
                    except ValueError:
                        dfs = []

                    target_df = None
                    for df in dfs:
                        cols = [str(c).strip() for c in df.columns]
                        if any("買賣超" in c for c in cols) and any("家數差" in c for c in cols):
                            target_df = df
                            break
                    
                    if target_df is not None and not target_df.empty:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', encoding='utf-8-sig') as tmp:
                            target_df.to_csv(tmp.name, index=False)
                            print(tmp.name)
                            return 
                    else:
                        log_err(f"Attempt {attempt}: Table not found or empty.")
                        sb.sleep(random.uniform(2, 5))
                        
                except Exception as inner_e:
                    log_err(f"Attempt {attempt} failed: {str(inner_e)}")
                    sb.sleep(3)

            raise RuntimeError("Max retries reached, unable to extract table.")

    except Exception as e:
        log_err(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    scraper_script = scraper_script.replace("{stock_id}", str(stock_id))

    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(scraper_script)
            
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown subprocess error"
            raise RuntimeError(f"Subprocess failed: {error_msg}")
            
        csv_path = result.stdout.strip()
        
        if not csv_path or not os.path.exists(csv_path):
            raise RuntimeError(f"No CSV path returned. Stderr: {result.stderr}")

        try:
            df = pd.read_csv(csv_path)
            os.remove(csv_path)
            
            df.columns = [str(c).strip() for c in df.columns]
            buy_col = next((c for c in df.columns if "買賣超" in c), None)
            diff_col = next((c for c in df.columns if "家數差" in c), None)
            date_col = next((c for c in df.columns if "日期" in c), None)
            con5_col = next((c for c in df.columns if "5日集中" in c), None)
            con20_col = next((c for c in df.columns if "20日集中" in c), None)
            
            if buy_col and diff_col and date_col:
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
                
                for col in ['買賣超', '家數差']:
                    clean_df[col] = pd.to_numeric(clean_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                for col in ['5日集中', '20日集中']:
                    if col in clean_df.columns:
                        clean_df[col] = clean_df[col].astype(str).str.replace('%', '').str.replace(',', '')
                        clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)

                clean_df['dt_temp'] = pd.to_datetime(clean_df['日期'])
                clean_df['dt_temp'] = clean_df['dt_temp'] + pd.Timedelta(days=1)
                
                clean_df['DateStr'] = clean_df['dt_temp'].dt.strftime('%Y-%m-%d')
                
                clean_df['日期'] = clean_df['DateStr'].str.replace('-', '/')
                
                clean_df = clean_df.drop(columns=['dt_temp'])
                
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

@st.cache_data(ttl=21600)
def get_norway_rank_data(url="https://norway.twsthr.info/StockHoldersTopWeek.aspx"):
    driver = get_driver()
    
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//table[contains(., '大股東持有張數增減')]"))
        )
        
        html = driver.page_source
        dfs = pd.read_html(StringIO(html), header=None)
        
        target_df = None
        for df in dfs:
            if len(df.columns) > 10 and len(df) > 20:
                if df.apply(lambda x: x.astype(str).str.contains('大股東持有').any()).any():
                    target_df = df
                    break
        
        if target_df is None and len(dfs) > 0:
             target_df = max(dfs, key=len)

        if target_df is not None:
            header_idx = -1
            data_start_idx = -1
            
            for idx, row in target_df.iterrows():
                row_str = row.astype(str).values
                if re.search(r'\d{4}', str(row[3])):
                    data_start_idx = idx
                    break
            
            if data_start_idx == -1: return None
            
            for idx in range(max(0, data_start_idx - 5), data_start_idx):
                row = target_df.iloc[idx]
                if re.match(r'^\d{4,}$', str(row[5])):
                    header_idx = idx
                    break
            
            raw_data = target_df.iloc[data_start_idx:data_start_idx+100].copy()
            
            col_indices = [3, 5, 6, 7, 8, 9, 10, 13, 15]
            
            final_cols = ["股票代號/名稱"]
            if header_idx != -1:
                date_headers = target_df.iloc[header_idx, 5:11].tolist()
                final_cols.extend([str(d) for d in date_headers])
            else:
                final_cols.extend([f"Date_{i}" for i in range(1, 7)])
                
            final_cols.extend(["總增減", "上週持有%"])
            
            result_df = raw_data.iloc[:, col_indices]
            result_df.columns = final_cols
            
            result_df = result_df.astype(str)
            
            return result_df

    except Exception:
        return None
    finally:
        driver.quit()

@st.cache_data
def get_all_stock_options():
    stock_options = []
    for code, info in twstock.codes.items():
        if info.type == "股票": 
            stock_options.append(f"{code} {info.name}")
    return stock_options

st.title(f"📊 籌碼K線")

# ✅ [NEW] 主題切換按鈕 (位於最右上角，僅切換圖表主題)
col_top_head, col_top_theme = st.columns([8, 1])
with col_top_theme:
    if st.button("🌞/🌜", help="切換 K 線圖表深色/淺色模式"):
        st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'
        st.rerun()

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

# ✅ [FIX] 類股排行點擊後的跳轉
if "__jump_stock_code" in st.session_state:
    code = st.session_state.pop("__jump_stock_code")
    for s in get_all_stock_options():
        if s.startswith(code):
            st.session_state["stock_selector"] = s
            break

if "__jump_page" in st.session_state:
    st.session_state["current_page"] = st.session_state.pop("__jump_page")

if "search_counts" not in st.session_state:
    st.session_state.search_counts = {}

# ✅ 統計天數選項
days_map = {"1日": 1, "5日": 5, "10日": 10, "20日": 20, "40日": 40, "60日": 60, "120日": 120, "240日": 240}
if "days_label" not in st.session_state:
    st.session_state.days_label = "20日" 
if "selected_days" not in st.session_state:
    st.session_state.selected_days = days_map.get(st.session_state.days_label, 20) 

st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

# ✅ [LAYOUT CHANGE] 緊湊型搜尋欄 (Columns)
col_search_1, col_search_2, col_search_3 = st.columns([6, 1.5, 2.5], gap="small")

with col_search_1:
    all_stocks = get_all_stock_options()
    
    def get_sort_key(stock_str):
        code = stock_str.split()[0]
        count = st.session_state.search_counts.get(code, 0)
        return -count

    sorted_stocks = sorted(all_stocks, key=get_sort_key)
    
    if "stock_selector" not in st.session_state:
        default_index = 0
        for idx, s in enumerate(sorted_stocks):
            if s.startswith("2313"):
                default_index = idx
                break
        if sorted_stocks:
            st.session_state["stock_selector"] = sorted_stocks[default_index]
    
    stock_selection = st.selectbox(
        "搜尋股票", 
        options=sorted_stocks, 
        placeholder="請輸入股票代號...",
        key="stock_selector",
        label_visibility="collapsed"
    )

if stock_selection: 
    stock_input = stock_selection.split()[0]
else: 
    stock_input = ""

with col_search_2:
    if st.button("🔎 查詢", type="primary", use_container_width=True):
        if stock_input: 
            st.session_state.search_counts[stock_input] = st.session_state.search_counts.get(stock_input, 0) + 1
        st.rerun()

with col_search_3:
    if "refresh_nonce" not in st.session_state: st.session_state.refresh_nonce = 0
    if st.button("🔄 更新籌碼", use_container_width=True):
        st.session_state.refresh_nonce = int(time.time())
        st.rerun()

st.caption(f"🕒 資料抓取時間: {current_time}")

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

if 'current_page' not in st.session_state:
    st.session_state.current_page = "K線"

selected_page = st.radio(
    "功能分頁", 
    ["K線", "分點", "法人", "融資券", "主力", "大戶", "類股排行", "多股比較", "選股"], 
    horizontal=True,
    label_visibility="collapsed",
    key="current_page"
)

# ==================== Tab: 主力 (New) ====================
if selected_page == "主力":
    if stock_input:
        stock_name = get_stock_name(stock_input)
        stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input
        st.subheader(f"⚡ {stock_display} 主力買賣超與家數差") 
        
        wg_df = None
        
        with st.spinner("正在抓取主力數據 (使用 SeleniumBase)..."):
            try:
                wg_df = get_wantgoo_data(stock_input, st.session_state.refresh_nonce)
            except Exception as e:
                st.warning(f"⚠️ 無法取得玩股網主力數據，可能被阻擋或無資料。\n(錯誤訊息: {str(e)})")
                st.info("💡 建議點擊上方「強制更新籌碼資料」重試。")
                wg_df = None
        
        if wg_df is not None and not wg_df.empty:
            if 'df_price_daily' not in locals() or df_price_daily is None:
                df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
            
            if df_price_daily is not None:
                merged_wg = pd.merge(df_price_daily, wg_df, on='DateStr', how='inner')
                
                candlestick_data = []
                ma5_data, ma20_data = [], []
                net_buy_data = []
                diff_data = []
                
                for i, row in merged_wg.iterrows():
                    candlestick_data.append({
                        "time": row['DateStr'], 
                        "open": row['Open'], "high": row['High'], 
                        "low": row['Low'], "close": row['Close']
                    })
                    if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": row['MA5']})
                    if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": row['MA20']})
                    
                    nb = row['買賣超']
                    net_buy_data.append({
                        "time": row['DateStr'], 
                        "value": nb, 
                        "color": COLOR_UP if nb > 0 else COLOR_DOWN
                    })
                    
                    df_val = row['家數差']
                    diff_color = COLOR_UP if df_val < 0 else COLOR_DOWN
                    diff_data.append({
                        "time": row['DateStr'], 
                        "value": df_val, 
                        "color": diff_color
                    })

                # ✅ [FIX] 增加留白 (top_margin, right_offset)
                chart1 = {
                    "chart": make_opts(400, "股價", True, font_size=10, top_margin=0.05, bottom_margin=0.05, right_offset=20),
                    "series": [
                        {"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN}},
                        {"type": "Line", "data": ma5_data, "options": {"title": "MA5  ", "color": "orange", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}},
                        {"type": "Line", "data": ma20_data, "options": {"title": "MA20  ", "color": "#ff00ff", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}}
                    ]
                }
                
                # ✅ [FIX] 主力買賣超與家數差柱狀圖縮小 (top_margin=0.3) 並預留右側空間
                chart2 = {
                    "chart": make_opts(150, "主力買賣超 (張)", False, font_size=10, top_margin=0.3, right_offset=20),
                    "series": [
                        {"type": "Histogram", "data": net_buy_data, "options": {"title": "買賣超  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "lastValueVisible": False, "priceLineVisible": False}}
                    ]
                }
                
                chart3 = {
                    "chart": make_opts(150, "買賣家數差 (家)", False, font_size=10, top_margin=0.3, right_offset=20),
                    "series": [
                        {"type": "Histogram", "data": diff_data, "options": {"title": "家數差  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "lastValueVisible": False, "priceLineVisible": False}}
                    ]
                }
                
                renderLightweightCharts([chart1, chart2, chart3], key=f"wg_charts_{stock_input}")
                
                st.markdown("<br><br>", unsafe_allow_html=True)

                st.markdown("#### 詳細數據")
                display_df = wg_df.sort_values('DateStr', ascending=False)
                
                if 'DateStr' in display_df.columns:
                    display_df = display_df.drop(columns=['DateStr'])
                
                def highlight_main_force(val):
                    try:
                        if isinstance(val, (int, float)):
                            if val > 0: return f'color: {COLOR_UP}'
                            elif val < 0: return f'color: {COLOR_DOWN}'
                    except:
                        pass
                    return ''

                cols_to_style = ['買賣超', '家數差']
                if '5日集中' in display_df.columns: cols_to_style.append('5日集中')
                if '20日集中' in display_df.columns: cols_to_style.append('20日集中')

                st.dataframe(
                    display_df.style
                        .format({
                            '5日集中': '{:.2f}%',
                            '20日集中': '{:.2f}%'
                        })
                        .map(highlight_main_force, subset=cols_to_style), 
                    use_container_width=True, 
                    hide_index=True
                )
                
            else:
                st.warning("無法取得股價資料以繪製對照圖表。")
                st.dataframe(wg_df)

# ==================== Tab 6: 類股排行 (新增功能) ====================
elif selected_page == "類股排行":
    st.subheader("🏆 大股東持股排行榜 (Top 100)")

    tab_listed, tab_otc = st.tabs(["上市排行 (Top 100)", "上櫃排行 (Top 100)"])

    def render_rank_page(url, key_suffix):
        rank_df = get_norway_rank_data(url)
        
        if rank_df is not None and not rank_df.empty:
            rank_df = rank_df.reset_index(drop=True)
            
            def highlight_val(val):
                try:
                    clean_val = str(val).replace('%', '').replace(',', '').strip()
                    v = float(clean_val)
                    if v > 0:
                        return f'color: {COLOR_UP}' # 紅
                    elif v < 0:
                        return f'color: {COLOR_DOWN}' # 綠
                except:
                    pass
                return ''
                
            styled_df = rank_df.style.map(highlight_val, subset=rank_df.columns[1:])
            
            event = st.dataframe(
                styled_df,
                use_container_width=True, 
                hide_index=True,
                on_select="rerun", 
                selection_mode="single-row",
                key=f"rank_table_{key_suffix}" # 區分 key
            )
            
            if len(event.selection.rows) > 0:
                selected_row_idx = event.selection.rows[0]
                stock_str = str(rank_df.iloc[selected_row_idx, 0])
                
                if stock_str:
                    match = re.search(r'(\d{4})', stock_str)
                    if match:
                        code = match.group(1)
                        st.session_state["__jump_stock_code"] = code
                        st.session_state["__jump_page"] = "K線"
                        st.session_state.search_counts[code] = st.session_state.search_counts.get(code, 0) + 1
                        st.rerun()
        else:
            st.warning("⚠️ 無法取得排行資料，請稍後再試。")

    with tab_listed:
        render_rank_page("https://norway.twsthr.info/StockHoldersTopWeek.aspx", "listed")
    
    with tab_otc:
        render_rank_page("https://norway.twsthr.info/StockHoldersTopWeek.aspx?CID=100&Show=1", "otc")

# ==================== Tab 7: 多股比較 (New) ====================
elif selected_page == "多股比較":
    st.subheader("📈 多股 K 線比較")
    
    if "multi_stock_inputs" not in st.session_state:
        st.session_state.multi_stock_inputs = "2330 2317 2454"

    # Inputs for comparison
    with st.expander("⚙️ 設定比較股票與指標", expanded=True):
        col_input, col_ind = st.columns([3, 1])
        with col_input:
            user_input = st.text_input(
                "輸入股票代號 (可輸入多支，以空白或逗號分隔，最多 10 支)", 
                key="multi_stock_inputs" 
            )
        with col_ind:
            # ✅ [修改 1] 在這裡加入新的選項文字，將 KD 改為 KDJ
            indicator_type = st.selectbox(
                "選擇副圖指標", 
                [
                    "成交量", "KDJ", "MACD", "RSI", 
                    "外資買賣超", "投信買賣超", "自營商買賣超",
                    "融資", "融券", "主力買賣超", "家數差"  # 新增的選項
                ],
                key="multi_stock_ind_selector"
            )
    
    # Process stocks
    raw_stocks = re.split(r'[ ,]+', user_input.strip())
    valid_stocks = [s.strip() for s in raw_stocks if s.strip()]
    
    valid_stocks = valid_stocks[:10]
    num_stocks = len(valid_stocks)
    
    if num_stocks > 0:
        cols_per_row = 2
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
                            # 1. Main Chart (K-Line + MA)
                            chart_data = []
                            ma5, ma20 = [], []
                            
                            for _, row in df.iterrows():
                                if not pd.isna(row['Open']):
                                    chart_data.append({
                                        "time": row['DateStr'], 
                                        "open": row['Open'], "high": row['High'], 
                                        "low": row['Low'], "close": row['Close']
                                    })
                                if not pd.isna(row['MA5']): ma5.append({"time": row['DateStr'], "value": row['MA5']})
                                if not pd.isna(row['MA20']): ma20.append({"time": row['DateStr'], "value": row['MA20']})
                            
                            main_series = [
                                {"type": "Candlestick", "data": chart_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False, "priceLineVisible": False}},
                                {"type": "Line", "data": ma5, "options": {"title": "MA5  ", "color": "orange", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}},
                                {"type": "Line", "data": ma20, "options": {"title": "MA20  ", "color": "#ff00ff", "lineWidth": 1, "lastValueVisible": False, "priceLineVisible": False}}
                            ]
                            
                            payload = [{"chart": make_opts(400, display_title, False, font_size=10, top_margin=0.2, bottom_margin=0.2, right_offset=20), "series": main_series}]
                            
                            # 2. Sub Chart Preparation
                            sub_data = []
                            sub_series = []
                            common_opts = {"lastValueVisible": False, "priceLineVisible": False}
                            
                            # ✅ [修改 2] 資料抓取邏輯 (依據選項去抓不同資料)
                            merged_df = df # 預設只用股價資料
                            
                            # (A) 抓法人資料
                            if indicator_type in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
                                s_date = df['DateStr'].iloc[0]
                                e_date = df['DateStr'].iloc[-1]
                                inst_df = get_institutional_data(code, s_date, e_date)
                                if inst_df is not None:
                                    merged_df = pd.merge(df, inst_df, on='DateStr', how='left').fillna(0)
                            
                            # (B) 抓融資券資料
                            elif indicator_type in ["融資", "融券"]:
                                end_dt = datetime.now()
                                start_dt = end_dt - timedelta(days=730)
                                s_date = start_dt.strftime('%Y-%m-%d')
                                e_date = end_dt.strftime('%Y-%m-%d')
                                margin_df = get_margin_data(code, s_date, e_date)
                                if margin_df is not None:
                                    merged_df = pd.merge(df, margin_df, on='DateStr', how='left').fillna(0)

                            # (C) 抓主力/家數差資料
                            elif indicator_type in ["主力買賣超", "家數差"]:
                                try:
                                    wg_df = get_wantgoo_data(code, st.session_state.refresh_nonce)
                                    if wg_df is not None:
                                        merged_df = pd.merge(df, wg_df, on='DateStr', how='left').fillna(0)
                                except: pass

                            # ✅ [修改 3] 繪圖邏輯 (決定怎麼畫)
                            if indicator_type == "成交量":
                                for _, row in df.iterrows():
                                     if not pd.isna(row['Volume']):
                                         sub_data.append({"time": row['DateStr'], "value": row['Volume'], "color": COLOR_UP if row['Close'] >= row['Open'] else COLOR_DOWN})
                                sub_series = [{"type": "Histogram", "data": sub_data, "options": {"title": "成交量(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", **common_opts}}]
                                
                            elif indicator_type in ["KDJ", "MACD", "RSI"]:
                                 # ✅ [FIX] 改為 KDJ 繪圖
                                 if indicator_type == "KDJ":
                                     k, d, j = [], [], []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['K']): k.append({"time": row['DateStr'], "value": row['K']})
                                         if not pd.isna(row['D']): d.append({"time": row['DateStr'], "value": row['D']})
                                         if not pd.isna(row['J']): j.append({"time": row['DateStr'], "value": row['J']})
                                     sub_series = [
                                         {"type": "Line", "data": k, "options": {"title": "K  ", "color": "orange", "lineWidth": 1, **common_opts}},
                                         {"type": "Line", "data": d, "options": {"title": "D  ", "color": "cyan", "lineWidth": 1, **common_opts}},
                                         # J 線通常使用紫色或紫紅色
                                         {"type": "Line", "data": j, "options": {"title": "J  ", "color": "#E040FB", "lineWidth": 1, **common_opts}}
                                     ]
                                 elif indicator_type == "RSI":
                                     rsi = []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['RSI']): rsi.append({"time": row['DateStr'], "value": row['RSI']})
                                     sub_series = [{"type": "Line", "data": rsi, "options": {"title": "RSI  ", "color": "#AB47BC", "lineWidth": 1, **common_opts}}]
                                 elif indicator_type == "MACD":
                                     dif, dea, hist = [], [], []
                                     for _, row in df.iterrows():
                                         if not pd.isna(row['DIF']): dif.append({"time": row['DateStr'], "value": row['DIF']})
                                         if not pd.isna(row['DEA']): dea.append({"time": row['DateStr'], "value": row['DEA']})
                                         if not pd.isna(row['MACD_Hist']): hist.append({"time": row['DateStr'], "value": row['MACD_Hist'], "color": COLOR_UP if row['MACD_Hist'] >= 0 else COLOR_DOWN})
                                     sub_series = [
                                         {"type": "Histogram", "data": hist, "options": {"title": "MACD  ", **common_opts}},
                                         {"type": "Line", "data": dif, "options": {"title": "DIF  ", "color": "#FFD700", "lineWidth": 1, **common_opts}},
                                         {"type": "Line", "data": dea, "options": {"title": "DEA  ", "color": "#00FFFF", "lineWidth": 1, **common_opts}}
                                     ]

                            # 處理買賣超 (法人)
                            elif indicator_type in ["外資買賣超", "投信買賣超", "自營商買賣超"]:
                                col_map = {"外資買賣超": "外資買賣超", "投信買賣超": "投信買賣超", "自營商買賣超": "自營商買賣超"}
                                target_col = col_map[indicator_type]
                                if target_col in merged_df.columns:
                                    bar_data, line_data = [], []
                                    cum_val = 0
                                    for _, row in merged_df.iterrows():
                                        val = row[target_col]
                                        cum_val += val
                                        bar_data.append({"time": row['DateStr'], "value": val, "color": COLOR_UP if val > 0 else COLOR_DOWN})
                                        line_data.append({"time": row['DateStr'], "value": cum_val})
                                        
                                    title_str = f"{indicator_type[:2]}  " if len(indicator_type)>2 else f"{indicator_type}  "
                                    sub_series = [
                                        {"type": "Histogram", "data": bar_data, "options": {"title": title_str, "priceScaleId": "right", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, **common_opts}},
                                        {"type": "Line", "data": line_data, "options": {"title": "累  ", "color": MULTI_LINE_COLOR, "lineWidth": 2, "priceScaleId": "left", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, **common_opts}}
                                    ]

                            # 處理融資 / 融券
                            elif indicator_type in ["融資", "融券"]:
                                diff_col = "融資增減" if indicator_type == "融資" else "融券增減"
                                bal_col = "融資餘額" if indicator_type == "融資" else "融券餘額"
                                
                                if diff_col in merged_df.columns:
                                    bar_data, line_data = [], []
                                    for _, row in merged_df.iterrows():
                                        v_diff = row[diff_col]
                                        v_bal = row[bal_col]
                                        bar_data.append({"time": row['DateStr'], "value": v_diff, "color": COLOR_UP if v_diff > 0 else COLOR_DOWN})
                                        if v_bal > 0: line_data.append({"time": row['DateStr'], "value": v_bal})
                                    
                                    sub_series = [
                                        {"type": "Histogram", "data": bar_data, "options": {"title": "增減  ", "priceScaleId": "right", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, **common_opts}},
                                        {"type": "Line", "data": line_data, "options": {"title": "餘額  ", "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, **common_opts}}
                                    ]

                            # 處理主力 / 家數差
                            elif indicator_type in ["主力買賣超", "家數差"]:
                                target_col = "買賣超" if indicator_type == "主力買賣超" else "家數差"
                                if target_col in merged_df.columns:
                                    bar_data = []
                                    for _, row in merged_df.iterrows():
                                        val = row[target_col]
                                        # 家數差顏色邏輯：負數(集中)為紅，正數(分散)為綠
                                        if indicator_type == "家數差":
                                            c = COLOR_UP if val < 0 else COLOR_DOWN
                                        else:
                                            c = COLOR_UP if val > 0 else COLOR_DOWN
                                        bar_data.append({"time": row['DateStr'], "value": val, "color": c})
                                        
                                    title_name = "主力  " if indicator_type == "主力買賣超" else "家數差  "
                                    sub_series = [{"type": "Histogram", "data": bar_data, "options": {"title": title_name, "priceScaleId": "right", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, **common_opts}}]

                            # Render Sub Chart
                            if sub_series:
                                chart_title = indicator_type
                                if "成交量" in chart_title or "買賣超" in chart_title or "融" in chart_title:
                                    chart_title += " (張)"
                                elif "家數差" in chart_title:
                                    chart_title += " (家)"
                                
                                chart_opts = make_opts(200, chart_title, True, font_size=10, top_margin=0.05, bottom_margin=0.05)
                                if indicator_type == "RSI": chart_opts["rightPriceScale"] = {"visible":True, "autoScale":False, "mode":0, "maxValue":100, "minValue":0}
                                payload.append({"chart": chart_opts, "series": sub_series})
                            
                            renderLightweightCharts(payload, key=f"compare_{idx}_{code}")
                        else:
                            st.warning(f"⚠️ {code} 無資料")

# ==================== Tab 8: 選股 (New) ====================
elif selected_page == "選股":
    st.subheader("⚡ 飆股篩選器")
    st.markdown("""
    **篩選條件 (嚴格)**：
    系統將自動掃描所有上市與上櫃「大戶持股增加」的股票，並列出**同時符合**以下所有條件者：
    1. **大戶籌碼增加** (排行榜入列)
    2. **法人連買 3 日**
    3. **主力近期買超**
    
    *註：此功能需逐檔即時爬取資料，請耐心等候。*
    """)
    
    if st.button("開始自動掃描"):
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            status_text.text("正在抓取大戶排行資料 (上市 + 上櫃)...")
            
            df_listed = get_norway_rank_data("https://norway.twsthr.info/StockHoldersTopWeek.aspx")
            df_otc = get_norway_rank_data("https://norway.twsthr.info/StockHoldersTopWeek.aspx?CID=100&Show=1")
            
            def process_rank_df(df, label):
                if df is None or df.empty: return []
                processed = []
                for _, row in df.iterrows():
                    try:
                        stock_str = str(row[0]) 
                        match = re.search(r'(\d{4})', stock_str)
                        if not match: continue
                        code = match.group(1)
                        
                        change_val_str = str(row['總增減']).replace(',', '').strip()
                        pct_val_str = str(row['上週持有%']).replace('%', '').replace(',', '').strip()
                        
                        change_val = float(change_val_str) if change_val_str else 0
                        pct_val = float(pct_val_str) if pct_val_str else 0
                        
                        processed.append({
                            "code": code,
                            "name": stock_str,
                            "change": change_val, 
                            "pct": pct_val,
                            "type": label
                        })
                    except: continue
                return processed

            list_data = process_rank_df(df_listed, "上市")
            otc_data = process_rank_df(df_otc, "上櫃")
            
            all_candidates = list_data + otc_data
            
            final_results = []
            
            total_checks = len(all_candidates)
            
            for idx, item in enumerate(all_candidates):
                code = item['code']
                name = item['name']
                
                status_text.text(f"正在檢查 ({idx+1}/{total_checks}): {name} ...")
                progress_bar.progress((idx + 1) / total_checks)
                
                is_inst_ok = False
                is_main_ok = False
                
                s_date, e_date = calculate_date_range(code, 10)
                
                try:
                    inst_df = get_institutional_data(code, s_date, e_date)
                    if inst_df is not None and len(inst_df) >= 3:
                        inst_df['total'] = inst_df['外資買賣超'] + inst_df['投信買賣超'] + inst_df['自營商買賣超']
                        last_3 = inst_df.tail(3)
                        if (last_3['total'] > 0).all():
                            is_inst_ok = True
                except:
                    pass
                
                if is_inst_ok:
                    try:
                        wg_df = get_wantgoo_data(code, st.session_state.refresh_nonce)
                        if wg_df is not None and not wg_df.empty:
                            last_row = wg_df.iloc[-1]
                            if last_row['買賣超'] > 0:
                                is_main_ok = True
                    except:
                        pass
                
                if is_inst_ok and is_main_ok:
                    final_results.append({
                        "代號/名稱": name,
                        "大戶總增減": item['change'],
                        "大戶持股%": item['pct'],
                        "法人連買3日": True,
                        "主力近期買超": True
                    })
            
            final_results.sort(key=lambda x: x['大戶總增減'], reverse=True)
            
            status_text.text("篩選完成！")
            progress_bar.progress(100)
            
            if final_results:
                st.success(f"共找到 {len(final_results)} 檔符合所有條件的強勢股！")
                res_df = pd.DataFrame(final_results)
                
                def highlight_result(val):
                    if isinstance(val, (int, float)):
                        if val > 0: return f'color: {COLOR_UP}; font-weight: bold' 
                        elif val < 0: return f'color: {COLOR_DOWN}; font-weight: bold' 
                    return ''
                
                event = st.dataframe(
                    res_df.style.map(highlight_result, subset=['大戶總增減']),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "法人連買3日": st.column_config.CheckboxColumn(
                            "法人連買3日",
                            default=False,
                            disabled=True 
                        ),
                        "主力近期買超": st.column_config.CheckboxColumn(
                            "主力近期買超",
                            default=False,
                            disabled=True
                        ),
                        "大戶總增減": st.column_config.NumberColumn(
                            "大戶總增減",
                            format="%.2f",
                        ),
                        "大戶持股%": st.column_config.NumberColumn(
                            "大戶持股%",
                            format="%.2f%%",
                        )
                    }
                )

                if len(event.selection.rows) > 0:
                    selected_row_idx = event.selection.rows[0]
                    stock_str = str(res_df.iloc[selected_row_idx]['代號/名稱'])
                    if stock_str:
                        match = re.search(r'(\d{4})', stock_str)
                        if match:
                            code = match.group(1)
                            st.session_state["__jump_stock_code"] = code
                            st.session_state["__jump_page"] = "K線"
                            st.session_state.search_counts[code] = st.session_state.search_counts.get(code, 0) + 1
                            st.rerun()

            else:
                st.warning("沒有股票同時符合三大條件。")
                
        except Exception as e:
            st.error(f"篩選過程發生錯誤: {str(e)}")
            st.code(traceback.format_exc())

elif stock_input:
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    current_days_label = st.session_state.days_label
    selected_days = days_map.get(current_days_label, 20) 
    st.session_state.selected_days = selected_days 

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = None, None, None, None, None, None
    
    with st.spinner(f"正在分析 {stock_display} ..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date, st.session_state.refresh_nonce)
        
    df_price_daily = get_stock_price(stock_input, st.session_state.refresh_nonce)
    
    df_price = df_price_daily.copy() if df_price_daily is not None else None
    
    if df_buy is not None and df_sell is not None:
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date})")

        def make_opts(height, title=None, time_visible=True, scale_mode="normal"):
            opts = {
                "layout": {"textColor": CHART_TEXT, "background": {"type": "solid", "color": CHART_BG}},
                "localization": {"locale": "zh-TW", "dateFormat": "yyyy年MM月dd日"},
                "grid": {"vertLines": {"color": GRID_COLOR}, "horzLines": {"color": GRID_COLOR}},
                "timeScale": {
                    "borderColor": "rgba(197, 203, 206, 0.8)", 
                    "visible": time_visible, 
                    "timeVisible": True, 
                    "secondsVisible": False,
                    "barSpacing": 12, 
                    "rightOffset": 5, 
                },
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
                # ✅ [FIX] 嘗試開啟圖表配置以支援更好的繪圖互動
                "handleScale": {
                    "axisPressedMouseMove": True,
                },
                "handleScroll": {
                    "mouseWheel": True,
                    "pressedMouseMove": True,
                },
            }
            if scale_mode == "rsi":
                opts["rightPriceScale"] = {"visible": True, "autoScale": False, "mode": 0, "maxValue": 100, "minValue": 0, "minimumWidth": 75}
            if title:
                watermark_color = 'rgba(255, 255, 255, 0.2)' if st.session_state.theme == 'dark' else 'rgba(0, 0, 0, 0.1)'
                opts["watermark"] = {"visible": True, "fontSize": 20, "horzAlign": 'left', "vertAlign": 'top', "color": watermark_color, "text": title}
            
            return opts

        # ==================== Tab 1: K線 ====================
        if selected_page == "K線":
            st.markdown("<br>", unsafe_allow_html=True) 
            
            with st.container():
                c_k_period, c_k_ma, c_k_ind = st.columns([1, 3, 5], gap="large")
                
                with c_k_period:
                    kline_period = st.selectbox("📅 週期", ["日K", "週K", "月K", "5分", "15分", "30分", "60分"])
                
                with c_k_ma:
                    ma_options_list = ["MA5", "MA10", "MA20", "MA60", "MA120", "MA240", "BB"]
                    ma_default = ["MA5", "MA10", "MA20", "MA60"]
                    selected_mas = st.multiselect(
                        "📈 均線 / 布林",
                        options=ma_options_list,
                        default=ma_default
                    )
                    
                with c_k_ind:
                    # ✅ [FIX] 這裡將 KD 選項改為 KDJ
                    indicator_options = [
                        "成交量", "KDJ", "MACD", "RSI", 
                        "外資", "投信", "自營商", "三大法人合計",
                        "融資", "融券",
                        "主力買賣超", "家數差",
                        "分點買賣超" 
                    ]
                    selected_indicators = st.multiselect(
                        "📊 副圖指標 (依選擇順序排列，支援籌碼與主力)",
                        options=indicator_options,
                        key="kline_indicators_selector"
                    )

            if "分點買賣超" in selected_indicators:
                with st.expander("🛠️ 分點買賣超設定 (選擇天數與券商)", expanded=True):
                    c_days, c_brokers = st.columns([1, 4])
                    
                    with c_days:
                        target_days_label = st.selectbox(
                            "統計天數",
                            list(days_map.keys()),
                            key="kline_broker_days"
                        )
                        target_days = days_map.get(target_days_label, 20)

                    s_d, e_d = calculate_date_range(stock_input, target_days)
                    _df_buy, _df_sell, _, _, _broker_info, _ = get_real_data_matrix(stock_input, s_d, e_d, st.session_state.refresh_nonce)
                    
                    broker_options = []
                    if _df_buy is not None and not _df_buy.empty:
                        broker_options.extend(_df_buy['broker'].tolist())
                    if _df_sell is not None and not _df_sell.empty:
                        broker_options.extend(_df_sell['broker'].tolist())
                    
                    broker_options = list(dict.fromkeys(broker_options))

                    with c_brokers:
                        selected_brokers_kline = st.multiselect(
                            f"券商分點 (統計區間前 15 大買賣超，可多選)",
                            options=broker_options,
                            key="kline_selected_brokers"
                        )

            st.markdown("<br>", unsafe_allow_html=True)
            
            plot_df = None
            if kline_period in ["日K", "週K", "月K"]:
                if df_price_daily is not None:
                    plot_df = resample_data(df_price_daily, kline_period)
            else:
                with st.spinner(f"正在載入 {kline_period} 資料..."):
                    plot_df = get_intraday_data(stock_input, kline_period)
                    if plot_df is None:
                        st.warning("⚠️ 無法取得分時資料（可能是週末或資料源暫時無法存取）")
                        plot_df = df_price_daily.copy() 

            if plot_df is not None and not plot_df.empty and kline_period == "日K":
                if any(x in selected_indicators for x in ["外資", "投信", "自營商", "三大法人合計"]):
                    s_d = plot_df['DateStr'].iloc[0]
                    e_d = plot_df['DateStr'].iloc[-1]
                    inst_df = get_institutional_data(stock_input, s_d, e_d)
                    if inst_df is not None:
                        plot_df = pd.merge(plot_df, inst_df, on='DateStr', how='left')
                        for col in ['外資買賣超', '投信買賣超', '自營商買賣超']:
                            if col in plot_df.columns: plot_df[col] = plot_df[col].fillna(0)
                        plot_df['三大法人合計'] = plot_df['外資買賣超'] + plot_df['投信買賣超'] + plot_df['自營商買賣超']
                        
                        if '外資買賣超' in plot_df.columns: plot_df['cum_foreign'] = plot_df['外資買賣超'].cumsum()
                        if '投信買賣超' in plot_df.columns: plot_df['cum_trust'] = plot_df['投信買賣超'].cumsum()
                        if '自營商買賣超' in plot_df.columns: plot_df['cum_dealer'] = plot_df['自營商買賣超'].cumsum()
                        if '三大法人合計' in plot_df.columns: plot_df['cum_total'] = plot_df['三大法人合計'].cumsum()

                if any(x in selected_indicators for x in ["融資", "融券"]):
                    end_dt = datetime.now()
                    start_dt = end_dt - timedelta(days=730)
                    margin_s_d = start_dt.strftime('%Y-%m-%d')
                    margin_e_d = end_dt.strftime('%Y-%m-%d')
                    
                    margin_df = get_margin_data(stock_input, margin_s_d, margin_e_d)
                    
                    if margin_df is not None:
                        plot_df = pd.merge(plot_df, margin_df, on='DateStr', how='left')
                        for col in ['融資增減', '融券增減', '融資餘額', '融券餘額']:
                            if col in plot_df.columns: plot_df[col] = plot_df[col].fillna(0)

                if any(x in selected_indicators for x in ["主力買賣超", "家數差"]):
                    try:
                        wg_df = get_wantgoo_data(stock_input, st.session_state.refresh_nonce)
                        if wg_df is not None:
                            plot_df = pd.merge(plot_df, wg_df, on='DateStr', how='left')
                            if '買賣超' in plot_df.columns: plot_df['主力買賣超'] = plot_df['買賣超'].fillna(0)
                            if '家數差' in plot_df.columns: plot_df['家數差'] = plot_df['家數差'].fillna(0)
                    except:
                        pass 
                
                if "分點買賣超" in selected_indicators:
                    target_brokers = st.session_state.get('kline_selected_brokers', [])
                    
                    for b_name in target_brokers:
                        target_key = normalize_name(b_name)
                        broker_params = None
                        
                        current_days_val = days_map.get(st.session_state.kline_broker_days, 20)
                        s_d_b, e_d_b = calculate_date_range(stock_input, current_days_val)
                        _, _, _, _, b_info_map, _ = get_real_data_matrix(stock_input, s_d_b, e_d_b, st.session_state.refresh_nonce)
                        
                        if b_info_map:
                            if target_key in b_info_map: broker_params = b_info_map[target_key]
                            else:
                                for k, v in b_info_map.items():
                                    if target_key in k or k in target_key:
                                        broker_params = v
                                        break
                        
                        if broker_params:
                            long_s_date = plot_df['DateStr'].iloc[0]
                            long_e_date = plot_df['DateStr'].iloc[-1]
                            
                            b_key_tuple = (broker_params['BHID'], broker_params['b'], broker_params.get('C', '1'))
                            
                            b_df, _ = get_specific_broker_daily(stock_input, b_key_tuple, long_s_date, long_e_date, st.session_state.refresh_nonce)
                            
                            if b_df is not None and not b_df.empty:
                                b_df = b_df.drop_duplicates(subset=["DateStr"], keep="last")
                                temp_b = b_df[['DateStr', '買賣超_Calc']].copy()
                                col_name = f"broker_{target_key}" 
                                temp_b.columns = ['DateStr', col_name]
                                
                                plot_df = pd.merge(plot_df, temp_b, on='DateStr', how='left')
                                plot_df[col_name] = plot_df[col_name].fillna(0)
                                plot_df[f"{col_name}_cum"] = plot_df[col_name].cumsum()


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
                plot_df = plot_df.sort_values("DateStr").reset_index(drop=True)

                candlestick_data, ma5_data, ma10_data, ma20_data, ma60_data, ma120_data, ma240_data, bb_up_data, bb_low_data = [], [], [], [], [], [], [], [], []
                
                is_intraday = kline_period in ["5分", "15分", "30分", "60分"]
                
                vol_data = []
                # ✅ [FIX] 增加 J 值陣列
                k_data, d_data, j_data = [], [], []
                dif_data, dea_data, hist_data = [], [], []
                rsi_data, rsi_80_data, rsi_20_data = [], [], []
                
                foreign_data, foreign_line = [], []
                trust_data, trust_line = [], []
                dealer_data, dealer_line = [], []
                total_inst_data, total_inst_line = [], []
                
                margin_data, margin_line = [], []
                short_data, short_line = [], []
                
                main_force_data, main_diff_data = [], []
                
                brokers_data_map = {} 

                if "分點買賣超" in selected_indicators:
                    for b_name in st.session_state.get('kline_selected_brokers', []):
                         brokers_data_map[b_name] = {"hist": [], "line": []}

                for i, row in plot_df.iterrows():
                    if not pd.isna(row['Open']) and not pd.isna(row['Close']):
                        if is_intraday:
                            try:
                                dt_obj = datetime.strptime(row['DateStr'], '%Y-%m-%d %H:%M')
                                time_val = int(dt_obj.timestamp())
                            except:
                                time_val = row['DateStr']
                        else:
                            time_val = row['DateStr']
                            
                        candlestick_data.append({"time": time_val, "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                    
                    t_val = time_val 
                    
                    if show_ma5 and not pd.isna(row['MA5']): ma5_data.append({"time": t_val, "value": float(row['MA5'])})
                    if show_ma10 and not pd.isna(row['MA10']): ma10_data.append({"time": t_val, "value": float(row['MA10'])})
                    if show_ma20 and not pd.isna(row['MA20']): ma20_data.append({"time": t_val, "value": float(row['MA20'])})
                    if show_ma60 and not pd.isna(row['MA60']): ma60_data.append({"time": t_val, "value": float(row['MA60'])})
                    if show_ma120 and not pd.isna(row['MA120']): ma120_data.append({"time": t_val, "value": float(row['MA120'])})
                    if show_ma240 and not pd.isna(row['MA240']): ma240_data.append({"time": t_val, "value": float(row['MA240'])})
                    if show_bb and not pd.isna(row['BB_Up']): bb_up_data.append({"time": t_val, "value": float(row['BB_Up'])})
                    if show_bb and not pd.isna(row['BB_Low']): bb_low_data.append({"time": t_val, "value": float(row['BB_Low'])})

                    if not pd.isna(row['Volume']): vol_data.append({"time": t_val, "value": float(row['Volume']), "color": COLOR_UP if row['Close']>=row['Open'] else COLOR_DOWN})
                    if 'K' in plot_df.columns:
                        if not pd.isna(row['K']): k_data.append({"time": t_val, "value": float(row['K'])})
                        if not pd.isna(row['D']): d_data.append({"time": t_val, "value": float(row['D'])})
                        # ✅ [FIX] 收集 J 值數據
                        if 'J' in row and not pd.isna(row['J']): j_data.append({"time": t_val, "value": float(row['J'])})
                        
                    if 'DIF' in plot_df.columns:
                        if not pd.isna(row['DIF']): dif_data.append({"time": t_val, "value": float(row['DIF'])})
                        if not pd.isna(row['DEA']): dea_data.append({"time": t_val, "value": float(row['DEA'])})
                        if not pd.isna(row['MACD_Hist']): hist_data.append({"time": t_val, "value": float(row['MACD_Hist']), "color": COLOR_UP if row['MACD_Hist']>=0 else COLOR_DOWN})
                    if 'RSI' in plot_df.columns:
                        if not pd.isna(row['RSI']): 
                            rsi_data.append({"time": t_val, "value": float(row['RSI'])})
                            rsi_80_data.append({"time": t_val, "value": 80})
                            rsi_20_data.append({"time": t_val, "value": 20})
                    
                    if kline_period == "日K":
                        if '外資買賣超' in plot_df.columns:
                            v = row['外資買賣超']
                            c = row.get('cum_foreign', 0)
                            foreign_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            foreign_line.append({"time": t_val, "value": float(c)})
                        
                        if '投信買賣超' in plot_df.columns:
                            v = row['投信買賣超']
                            c = row.get('cum_trust', 0)
                            trust_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            trust_line.append({"time": t_val, "value": float(c)})
                        
                        if '自營商買賣超' in plot_df.columns:
                            v = row['自營商買賣超']
                            c = row.get('cum_dealer', 0)
                            dealer_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            dealer_line.append({"time": t_val, "value": float(c)})
                        
                        if '三大法人合計' in plot_df.columns:
                            v = row['三大法人合計']
                            c = row.get('cum_total', 0)
                            total_inst_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            total_inst_line.append({"time": t_val, "value": float(c)})
                        
                        if '融資增減' in plot_df.columns:
                            v = row['融資增減']
                            bal = row.get('融資餘額', 0)
                            margin_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            if bal > 0: margin_line.append({"time": t_val, "value": float(bal)})
                        
                        if '融券增減' in plot_df.columns:
                            v = row['融券增減']
                            bal = row.get('融券餘額', 0)
                            short_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                            if bal > 0: short_line.append({"time": t_val, "value": float(bal)})
                            
                        if '主力買賣超' in plot_df.columns:
                            v = row['主力買賣超']
                            main_force_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v > 0 else COLOR_DOWN})
                        
                        if '家數差' in plot_df.columns:
                            v = row['家數差']
                            main_diff_data.append({"time": t_val, "value": float(v), "color": COLOR_UP if v < 0 else COLOR_DOWN})
                        
                        for b_name in st.session_state.get('kline_selected_brokers', []):
                            target_key = normalize_name(b_name)
                            col_name = f"broker_{target_key}"
                            if col_name in plot_df.columns:
                                val = row.get(col_name, 0)
                                cum = row.get(f"{col_name}_cum", 0)
                                
                                s_d_b, e_d_b = calculate_date_range(stock_input, days_map.get(st.session_state.kline_broker_days, 20))
                                
                                is_in_range = s_d_b <= row['DateStr'] <= e_d_b
                                if val > 0:
                                    color = COLOR_UP if is_in_range else 'rgba(239, 83, 80, 0.3)'
                                else:
                                    color = COLOR_DOWN if is_in_range else 'rgba(38, 166, 154, 0.3)'

                                brokers_data_map[b_name]["hist"].append({"time": t_val, "value": float(val), "color": color})
                                brokers_data_map[b_name]["line"].append({"time": t_val, "value": float(cum)})


                ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
                main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False, "priceLineVisible": False}}]
                if show_ma5: main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5  "}})
                if show_ma10: main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10  "}})
                if show_ma20: main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20  "}})
                if show_ma60: main_series.append({"type": "Line", "data": ma60_data, "options": {**ma_opts, "color": "lime", "lineWidth": 2, "title": "MA60  "}})
                if show_ma120: main_series.append({"type": "Line", "data": ma120_data, "options": {**ma_opts, "color": "gray", "title": "MA120  "}})
                if show_ma240: main_series.append({"type": "Line", "data": ma240_data, "options": {**ma_opts, "color": "blue", "title": "MA240  "}})
                if show_bb:
                    main_series.append({"type": "Line", "data": bb_up_data, "options": {**ma_opts, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB上"}})
                    main_series.append({"type": "Line", "data": bb_low_data, "options": {**ma_opts, "color": "rgba(255, 255, 255, 0.5)", "lineWidth": 1, "title": "BB下"}})
                
                charts_payload.append({"chart": make_opts(600, "股價", True), "series": main_series})

                for indicator in selected_indicators:
                    
                    common_sub_opts = {"priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}
                    line_overlay_opts = {"priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False, "lineWidth": 2, "color": "white"} 

                    if indicator == "成交量":
                        charts_payload.append({
                            "chart": make_opts(150, "成交量 (張)", False), 
                            "series": [{"type": "Histogram", "data": vol_data, "options": {"title": "成交量  ", **common_sub_opts}}]
                        })

                    elif indicator == "KDJ": # ✅ [FIX] 改為 KDJ 判斷
                        charts_payload.append({
                            "chart": make_opts(150, "KDJ", False), 
                            "series": [
                                {"type": "Line", "data": k_data, "options": {"color": "orange", "lineWidth": 1, "title": "K  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                                {"type": "Line", "data": d_data, "options": {"color": "cyan", "lineWidth": 1, "title": "D  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                                # ✅ [FIX] 增加 J 線 (紫色)
                                {"type": "Line", "data": j_data, "options": {"color": "#E040FB", "lineWidth": 1, "title": "J  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                            ]
                        })

                    elif indicator == "MACD":
                        charts_payload.append({
                            "chart": make_opts(150, "MACD", False), 
                            "series": [
                                {"type": "Histogram", "data": hist_data, "options": {"title": "MACD  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                                {"type": "Line", "data": dif_data, "options": {"color": "#FFD700", "lineWidth": 1, "title": "DIF  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                                {"type": "Line", "data": dea_data, "options": {"color": "#00FFFF", "lineWidth": 1, "title": "DEA  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                            ]
                        })

                    elif indicator == "RSI":
                        charts_payload.append({
                            "chart": make_opts(150, "RSI", False, scale_mode="rsi"), 
                            "series": [
                                {"type": "Line", "data": rsi_data, "options": {"color": "#AB47BC", "lineWidth": 1, "title": "RSI  ", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                                {"type": "Line", "data": rsi_80_data, "options": {"color": "rgba(255, 0, 127, 0.5)", "lineWidth": 1, "lineStyle": 2, "title": "80", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": False, "lastValueVisible": False}},
                                {"type": "Line", "data": rsi_20_data, "options": {"color": "rgba(0, 255, 0, 0.5)", "lineWidth": 1, "lineStyle": 2, "title": "20", "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": False, "lastValueVisible": False}}
                            ]
                        })
                        
                    elif indicator == "外資":
                        charts_payload.append({
                            "chart": make_opts(150, "外資買賣超", False),
                            "series": [
                                {"type": "Histogram", "data": foreign_data, "options": {"title": "外資  ", **common_sub_opts}},
                                {"type": "Line", "data": foreign_line, "options": {"title": "累  ", **line_overlay_opts}}
                            ]
                        })
                    elif indicator == "投信":
                        charts_payload.append({
                            "chart": make_opts(150, "投信買賣超", False),
                            "series": [
                                {"type": "Histogram", "data": trust_data, "options": {"title": "投信  ", **common_sub_opts}},
                                {"type": "Line", "data": trust_line, "options": {"title": "累  ", **line_overlay_opts}}
                            ]
                        })
                    elif indicator == "自營商":
                        charts_payload.append({
                            "chart": make_opts(150, "自營商買賣超", False),
                            "series": [
                                {"type": "Histogram", "data": dealer_data, "options": {"title": "自營商  ", **common_sub_opts}},
                                {"type": "Line", "data": dealer_line, "options": {"title": "累  ", **line_overlay_opts}}
                            ]
                        })
                    elif indicator == "三大法人合計":
                        charts_payload.append({
                            "chart": make_opts(150, "法人合計", False),
                            "series": [
                                {"type": "Histogram", "data": total_inst_data, "options": {"title": "合計  ", **common_sub_opts}},
                                {"type": "Line", "data": total_inst_line, "options": {"title": "累  ", **line_overlay_opts}}
                            ]
                        })
                    elif indicator == "融資":
                        margin_line_opts = {**line_overlay_opts, "color": "orange", "title": "餘額  "}
                        charts_payload.append({
                            "chart": make_opts(150, "融資增減", False),
                            "series": [
                                {"type": "Histogram", "data": margin_data, "options": {"title": "增減  ", **common_sub_opts}},
                                {"type": "Line", "data": margin_line, "options": margin_line_opts}
                            ]
                        })
                    elif indicator == "融券":
                        short_line_opts = {**line_overlay_opts, "color": "orange", "title": "餘額  "}
                        charts_payload.append({
                            "chart": make_opts(150, "融券增減", False),
                            "series": [
                                {"type": "Histogram", "data": short_data, "options": {"title": "增減  ", **common_sub_opts}},
                                {"type": "Line", "data": short_line, "options": short_line_opts}
                            ]
                        })
                    elif indicator == "主力買賣超":
                        charts_payload.append({
                            "chart": make_opts(150, "主力買賣超", False),
                            "series": [{"type": "Histogram", "data": main_force_data, "options": {"title": "主力  ", **common_sub_opts}}]
                        })
                    elif indicator == "家數差":
                        charts_payload.append({
                            "chart": make_opts(150, "買賣家數差", False),
                            "series": [{"type": "Histogram", "data": main_diff_data, "options": {"title": "家數差  ", **common_sub_opts}}]
                        })
                    
                    elif indicator == "分點買賣超":
                        for b_name in st.session_state.get('kline_selected_brokers', []):
                            if b_name in brokers_data_map:
                                b_data = brokers_data_map[b_name]
                                charts_payload.append({
                                    "chart": make_opts(150, f"{b_name} (張)", False),
                                    "series": [
                                        {"type": "Histogram", "data": b_data["hist"], "options": {"title": "買賣超  ", **common_sub_opts}},
                                        {"type": "Line", "data": b_data["line"], "options": {"title": "累  ", "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                                    ]
                                })
                
                renderLightweightCharts(charts_payload, key=f"tab1_kline_{stock_input}")

        # ==================== Tab 2: 分點 ====================
        if selected_page == "分點":
            col_chart, col_table = st.columns([3, 1])
            
            if "active_broker" not in st.session_state:
                st.session_state.active_broker = None
            if "last_buy" not in st.session_state: st.session_state.last_buy = None
            if "last_sell" not in st.session_state: st.session_state.last_sell = None

            if st.session_state.active_broker is None and df_buy is not None and not df_buy.empty:
                st.session_state.active_broker = df_buy.iloc[0]['broker']

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
                    main_chart_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5  "}})
                    main_chart_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10  "}})
                    main_chart_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20  "}})

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
                        
                        charts_payload_broker.append({"chart": make_opts(200, f"{target_broker} 買賣 (張)", False), "series": [
                            {"type": "Histogram", "data": chip_data, "options": {"title": "買賣(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                            {"type": "Line", "data": chip_cumulative_data, "options": {"title": "累積(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                        ]})
                    
                    renderLightweightCharts(charts_payload_broker, key=f"tab2_broker_{stock_input}_{target_broker}")

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
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5  "}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10  "}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20  "}})

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

                charts_payload_inst.append({"chart": make_opts(200, "三大法人合計 (張)", False), "series": [
                    {"type": "Histogram", "data": total_hist, "options": {"title": "合計買賣(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": total_line, "options": {"title": "合計累(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "white", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                
                charts_payload_inst.append({"chart": make_opts(150, "外資 (張)", False), "series": [
                    {"type": "Histogram", "data": f_hist, "options": {"title": "買賣(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": f_line, "options": {"title": "累積(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "#FFD700", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "投信 (張)", False), "series": [
                    {"type": "Histogram", "data": t_hist, "options": {"title": "買賣(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": t_line, "options": {"title": "累積(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "#FF00FF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_inst.append({"chart": make_opts(150, "自營商 (張)", False), "series": [
                    {"type": "Histogram", "data": d_hist, "options": {"title": "買賣(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": d_line, "options": {"title": "累積(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "#00FFFF", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
            renderLightweightCharts(charts_payload_inst, key=f"tab3_inst_{stock_input}")

        # ==================== Tab 4: 融資券 ====================
        if selected_page == "融資券":
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=730) 
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
            ma5_data, ma10_data, ma20_data = [], [], []

            for i, row in plot_df.iterrows():
                if not pd.isna(row['Open']): candlestick_data.append({"time": row['DateStr'], "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close'])})
                if not pd.isna(row['MA5']): ma5_data.append({"time": row['DateStr'], "value": float(row['MA5'])})
                if not pd.isna(row['MA10']): ma10_data.append({"time": row['DateStr'], "value": float(row['MA10'])})
                if not pd.isna(row['MA20']): ma20_data.append({"time": row['DateStr'], "value": float(row['MA20'])})

            ma_opts = {"lastValueVisible": False, "priceLineVisible": False, "crosshairMarkerVisible": True, "lineWidth": 1}
            main_series = [{"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN, "borderUpColor": COLOR_UP, "borderDownColor": COLOR_DOWN, "wickUpColor": COLOR_UP, "wickDownColor": COLOR_DOWN, "lastValueVisible": False}}]
            main_series.append({"type": "Line", "data": ma5_data, "options": {**ma_opts, "color": "orange", "title": "MA5  "}})
            main_series.append({"type": "Line", "data": ma10_data, "options": {**ma_opts, "color": "cyan", "title": "MA10  "}})
            main_series.append({"type": "Line", "data": ma20_data, "options": {**ma_opts, "color": "#ff00ff", "lineWidth": 2, "title": "MA20  "}})

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

                charts_payload_margin.append({"chart": make_opts(150, "融資 (張)", False), "series": [
                    {"type": "Histogram", "data": ml_diff, "options": {"title": "增減(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": ml_bal, "options": {"title": "餘額(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})
                charts_payload_margin.append({"chart": make_opts(150, "融券 (張)", False), "series": [
                    {"type": "Histogram", "data": ms_diff, "options": {"title": "增減(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "priceScaleId": "right", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}},
                    {"type": "Line", "data": ms_bal, "options": {"title": "餘額(張)  ", "priceFormat": {"type": "price", "precision": 0, "minMove": 1}, "color": "orange", "lineWidth": 2, "priceScaleId": "left", "priceLineVisible": False, "crosshairMarkerVisible": True, "lastValueVisible": False}}
                ]})

            renderLightweightCharts(charts_payload_margin, key=f"tab4_margin_{stock_input}")
            
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

            raw_holder_df = get_shareholding_data(stock_input, st.session_state.refresh_nonce)
            
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
                    renderLightweightCharts(holder_payload, key=f"tab5_holder_{stock_input}")

    else:
        st.error(f"⚠️ 無法取得 K 線圖資料 ({stock_input})")
        st.info("可能有以下原因：\n1. 此股票為「興櫃股票」或 Yahoo Finance 無資料。\n2. 股票代號輸入錯誤。\n3. Yahoo API 暫時連線失敗，請稍後再試。")

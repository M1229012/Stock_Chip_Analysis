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
import mplfinance as mpf
import matplotlib.pyplot as plt
from streamlit_lightweight_charts import renderLightweightCharts

# ================= 1. 系統設定 =================

st.set_page_config(layout="wide", page_title="籌碼戰情室 (2313 Demo)", initial_sidebar_state="expanded")

# 初始化 Session State
if 'theme' not in st.session_state: st.session_state.theme = 'dark'
if "kline_indicators_selector" not in st.session_state: st.session_state.kline_indicators_selector = ["成交量", "KDJ", "MACD"]
if "kline_broker_days" not in st.session_state: st.session_state.kline_broker_days = "20日"
if "kline_selected_brokers" not in st.session_state: st.session_state.kline_selected_brokers = []
if "refresh_nonce" not in st.session_state: st.session_state.refresh_nonce = 0
if "search_counts" not in st.session_state: st.session_state.search_counts = {}

# 預設股票設定 (鎖定 2313)
DEFAULT_STOCK = "2313"

# 定義顏色
PAGE_BG = "#131722"
if st.session_state.theme == 'dark':
    CHART_BG = "#131722"
    CHART_TEXT = "white"
    GRID_COLOR = "rgba(42, 46, 57, 0.5)"
    MULTI_LINE_COLOR = "white"
else:
    CHART_BG = "#ffffff"
    CHART_TEXT = "black"
    GRID_COLOR = "rgba(42, 46, 57, 0.1)"
    MULTI_LINE_COLOR = "#000000"

COLOR_UP = '#ef5350' # 紅色 (上漲)
COLOR_DOWN = '#26a69a' # 綠色 (下跌)

# CSS 設定
st.markdown(f"""
    <style>
    header[data-testid="stHeader"] {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    .stApp {{ background-color: {PAGE_BG} !important; }}
    .block-container {{ padding-top: 2rem !important; padding-bottom: 2rem !important; }}
    div.element-container:has(iframe) {{ margin-bottom: -50px !important; }}
    iframe {{ display: block !important; margin: 0px !important; padding: 0px !important; border: 0px !important; }}
    div[data-testid="stHorizontalBlock"] {{ gap: 10px !important; }}
    div[data-testid="stVerticalBlock"] {{ gap: 10px !important; }}
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 輔助函式 (爬蟲與計算) =================

def is_roc_date(s: str) -> bool:
    return re.match(r"\d{2,3}/\d{1,2}/\d{1,2}", str(s).strip()) is not None

def roc_to_datestr(d_str: str) -> str | None:
    parts = re.split(r"[/-]", str(d_str).strip())
    if len(parts) < 2: return None
    y = int(parts[0])
    y = y + 1911 if y < 1911 else y
    m = int(parts[1])
    d = int(parts[2]) if len(parts) > 2 else 1
    return f"{y:04d}-{m:02d}-{d:02d}"

def calculate_technical_indicators(df):
    df = df.copy()
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Low'] = df['BB_Mid'] - 2 * df['BB_Std']
    
    rsv_period = 9
    df['9_High'] = df['High'].rolling(window=rsv_period).max()
    df['9_Low'] = df['Low'].rolling(window=rsv_period).min()
    df['RSV'] = 100 * ((df['Close'] - df['9_Low']) / (df['9_High'] - df['9_Low']))
    df['RSV'] = df['RSV'].fillna(50)
    
    k_list, d_list = [], []
    k_prev, d_prev = 50, 50
    for rsv in df['RSV']:
        if pd.isna(rsv):
            k_now, d_now = k_prev, d_prev
        else:
            k_now = (2/3) * k_prev + (1/3) * rsv
            d_now = (2/3) * d_prev + (1/3) * k_now
        k_list.append(k_now)
        d_list.append(d_now)
        k_prev, d_prev = k_now, d_now
        
    df['K'] = k_list
    df['D'] = d_list
    df['J'] = 3 * df['K'] - 2 * df['D']

    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = 2 * (df['DIF'] - df['DEA'])

    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=5, adjust=False).mean() 
    ema_down = down.ewm(com=5, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))

    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    df['MA240'] = df['Close'].rolling(window=240).mean()
    
    return df.replace([np.inf, -np.inf], np.nan)

# --- 爬蟲核心 (Selenium & yfinance) ---

@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.page_load_strategy = 'eager'
    
    if shutil.which("chromium"): options.binary_location = shutil.which("chromium")
    elif shutil.which("chromium-browser"): options.binary_location = shutil.which("chromium-browser")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

@st.cache_data(ttl=21600)
def get_stock_price(stock_id, refresh_nonce=0):
    tickers = [f"{stock_id}.TW", f"{stock_id}.TWO"]
    for t in tickers:
        try:
            df = yf.Ticker(t).history(period="2y") # 抓兩年
            if not df.empty:
                df['Volume'] = df['Volume'] / 1000 # 轉張數
                df.index = df.index.tz_localize(None)
                df['DateStr'] = df.index.strftime('%Y-%m-%d')
                return calculate_technical_indicators(df)
        except: continue
    return None

@st.cache_data(ttl=21600)
def get_institutional_data(stock_id, start_date, end_date):
    # 這裡為了展示完整性，保留原本邏輯，實際部署可能需要依賴 Fubon 網站的穩定性
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'外資買賣超')]")))
        dfs = pd.read_html(StringIO(driver.page_source))
        for df in dfs:
            if df.astype(str).apply(lambda x: x.str.contains('外資買賣超', na=False)).any().any():
                clean_df = df.iloc[:, [0, 1, 2, 3]].copy()
                clean_df.columns = ['日期', '外資買賣超', '投信買賣超', '自營商買賣超']
                clean_df = clean_df[clean_df['日期'].apply(is_roc_date)]
                for col in clean_df.columns[1:]:
                    clean_df[col] = pd.to_numeric(clean_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                clean_df['DateStr'] = clean_df['日期'].apply(roc_to_datestr)
                return clean_df.dropna(subset=['DateStr'])
    except: pass
    return None

@st.cache_data(ttl=21600)
def get_margin_data(stock_id, start_date, end_date):
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcn/zcn.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'融資餘額')]")))
        dfs = pd.read_html(StringIO(driver.page_source))
        for df in dfs:
            if df.astype(str).apply(lambda x: x.str.contains('融資餘額', na=False)).any().any():
                clean_df = df.iloc[:, [0, 4, 5, 11, 12]].copy()
                clean_df.columns = ['日期', '融資餘額', '融資增減', '融券餘額', '融券增減']
                clean_df = clean_df[clean_df['日期'].apply(is_roc_date)]
                for col in clean_df.columns[1:]:
                    clean_df[col] = pd.to_numeric(clean_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                clean_df['DateStr'] = clean_df['日期'].apply(roc_to_datestr)
                return clean_df.dropna(subset=['DateStr'])
    except: pass
    return None

@st.cache_data(ttl=21600)
def get_wantgoo_data(stock_id, refresh_nonce):
    # 簡化版的 Wantgoo 爬取，因 Streamlit Cloud 可能無法執行 SeleniumBase
    # 若此函式失敗，戰情圖會顯示無數據，但不影響其他功能
    try:
        # 這裡模擬一個簡單的 fallback 或者提示
        # 實際部署建議使用更穩定的 API 或忽略此部分
        return None 
    except: return None

# ================= 3. 戰情圖生成與 Discord 發送 (核心新功能) =================

def send_image_to_discord(image_path, webhook_url, message=""):
    if not webhook_url: return "❌ 未設定 Webhook URL"
    try:
        with open(image_path, "rb") as f:
            payload = {"content": message}
            files = {"file": (os.path.basename(image_path), f, "image/png")}
            response = requests.post(webhook_url, data=payload, files=files)
            if 200 <= response.status_code < 300: return "✅ 圖片發送成功!"
            return f"❌ 發送失敗: {response.status_code}"
    except Exception as e: return f"❌ 發送錯誤: {str(e)}"

def generate_dashboard_img(stock_id, df_price, df_inst, df_margin, df_wg=None):
    """生成一頁式戰情圖"""
    # 1. 資料整併
    df = df_price.copy()
    df.index = pd.to_datetime(df['DateStr'])
    df.index.name = 'Date'
    
    if df_inst is not None:
        inst = df_inst.set_index('DateStr')
        inst.index = pd.to_datetime(inst.index)
        # 處理重複 index
        inst = inst[~inst.index.duplicated(keep='last')]
        df = df.join(inst[['外資買賣超', '投信買賣超', '自營商買賣超']], how='left')
        df['三大法人合計'] = df['外資買賣超'].fillna(0) + df['投信買賣超'].fillna(0) + df['自營商買賣超'].fillna(0)
        
    if df_margin is not None:
        margin = df_margin.set_index('DateStr')
        margin.index = pd.to_datetime(margin.index)
        margin = margin[~margin.index.duplicated(keep='last')]
        df = df.join(margin[['融資增減', '融券增減']], how='left')
        
    if df_wg is not None:
        wg = df_wg.set_index('DateStr')
        wg.index = pd.to_datetime(wg.index)
        wg = wg[~wg.index.duplicated(keep='last')]
        df = df.join(wg[['家數差']], how='left')

    # 取近 120 天
    df = df.tail(120)
    
    # 2. 設定 MPF 樣式 (台灣紅漲綠跌)
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, gridstyle=':', y_on_right=True)
    
    # 3. 設定副圖 (AddPlots)
    add_plots = []
    
    # MA & BB (Panel 0)
    if 'MA5' in df.columns: add_plots.append(mpf.make_addplot(df['MA5'], panel=0, color='orange', width=1))
    if 'MA10' in df.columns: add_plots.append(mpf.make_addplot(df['MA10'], panel=0, color='cyan', width=1))
    if 'MA20' in df.columns: add_plots.append(mpf.make_addplot(df['MA20'], panel=0, color='#ff00ff', width=1.5))
    if 'MA60' in df.columns: add_plots.append(mpf.make_addplot(df['MA60'], panel=0, color='green', width=1.5))
    if 'BB_Up' in df.columns: add_plots.append(mpf.make_addplot(df['BB_Up'], panel=0, color='gray', linestyle='--', width=0.8))
    if 'BB_Low' in df.columns: add_plots.append(mpf.make_addplot(df['BB_Low'], panel=0, color='gray', linestyle='--', width=0.8))

    # 三大法人 (Panel 2)
    if '三大法人合計' in df.columns:
        colors = ['r' if v >= 0 else 'g' for v in df['三大法人合計'].fillna(0)]
        add_plots.append(mpf.make_addplot(df['三大法人合計'], panel=2, type='bar', color=colors, ylabel='Inst Net'))

    # 融資 (Panel 3)
    if '融資增減' in df.columns:
        colors = ['r' if v >= 0 else 'g' for v in df['融資增減'].fillna(0)]
        add_plots.append(mpf.make_addplot(df['融資增減'], panel=3, type='bar', color=colors, ylabel='Margin'))

    # 家數差 (Panel 4)
    if '家數差' in df.columns:
        # 負數代表籌碼集中(紅)，正數代表發散(綠)
        colors = ['r' if v < 0 else 'g' for v in df['家數差'].fillna(0)]
        add_plots.append(mpf.make_addplot(df['家數差'], panel=4, type='bar', color=colors, ylabel='Diff'))

    # 4. 繪圖
    output_path = tempfile.mktemp(suffix=".png")
    fig, axes = mpf.plot(
        df, type='candle', style=s, volume=True, addplot=add_plots,
        panel_ratios=(3, 1, 1, 1, 1), 
        title=dict(title=f"{stock_id} Analysis", size=15),
        figsize=(12, 18), returnfig=True,
        savefig=dict(fname=output_path, dpi=100, bbox_inches='tight')
    )
    plt.close(fig)
    return output_path

def make_lightweight_chart(df):
    """生成互動式圖表的配置"""
    # 這裡只做最基礎的 K 線圖設定，為了程式碼簡潔
    candlestick_data = []
    vol_data = []
    for i, row in df.iterrows():
        t = row['DateStr']
        candlestick_data.append({"time": t, "open": row['Open'], "high": row['High'], "low": row['Low'], "close": row['Close']})
        color = COLOR_UP if row['Close'] >= row['Open'] else COLOR_DOWN
        vol_data.append({"time": t, "value": row['Volume'], "color": color})
    
    chart_opts = {
        "layout": {"textColor": CHART_TEXT, "background": {"type": "solid", "color": CHART_BG}},
        "grid": {"vertLines": {"color": GRID_COLOR}, "horzLines": {"color": GRID_COLOR}},
        "height": 400
    }
    series = [
        {"type": "Candlestick", "data": candlestick_data, "options": {"upColor": COLOR_UP, "downColor": COLOR_DOWN}},
        {"type": "Histogram", "data": vol_data, "options": {"priceScaleId": "right", "priceFormat": {"type": "volume"}}}
    ]
    return [{"chart": chart_opts, "series": series}]

# ================= 4. 主程式邏輯 =================

def main():
    st.title(f"📊 股票戰情室 - 代號 {DEFAULT_STOCK}")

    # 側邊欄設定
    with st.sidebar:
        st.header("⚙️ 設定")
        stock_input = st.text_input("股票代號", value=DEFAULT_STOCK)
        discord_webhook = st.text_input("Discord Webhook URL", type="password")
        if st.button("🔄 更新數據"):
            st.session_state.refresh_nonce += 1
            st.rerun()

    if not stock_input:
        st.warning("請輸入股票代號")
        return

    # 抓取數據 (一次性抓取)
    with st.spinner(f"正在分析 {stock_input} ..."):
        df_price = get_stock_price(stock_input, st.session_state.refresh_nonce)
        
        if df_price is None or df_price.empty:
            st.error("❌ 找不到股價資料，請確認代號正確。")
            return

        # 計算日期範圍 (用於抓取籌碼)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=200)
        s_date = start_dt.strftime('%Y-%m-%d')
        e_date = end_dt.strftime('%Y-%m-%d')

        df_inst = get_institutional_data(stock_input, s_date, e_date)
        df_margin = get_margin_data(stock_input, s_date, e_date)
        # df_wg = get_wantgoo_data(stock_input, st.session_state.refresh_nonce) # 暫時關閉以利部署
        df_wg = None

    # 頁面分頁
    tab1, tab2 = st.tabs(["📈 K線圖表", "📸 一頁式戰情圖 & Discord"])

    with tab1:
        st.subheader("互動式 K 線圖")
        charts = make_lightweight_chart(df_price.tail(150))
        renderLightweightCharts(charts, key="main_chart")
        st.dataframe(df_price.tail(5)[['DateStr', 'Close', 'Volume', 'MA5', 'MA20', 'RSI']], use_container_width=True)

    with tab2:
        st.subheader("一頁式全方位分析圖")
        col1, col2 = st.columns([3, 1])
        
        img_path = None
        
        with col1:
            if st.button("🚀 生成戰情圖"):
                try:
                    img_path = generate_dashboard_img(stock_input, df_price, df_inst, df_margin, df_wg)
                    st.image(img_path, caption=f"{stock_input} 綜合分析", use_container_width=True)
                    st.session_state['last_img_path'] = img_path
                except Exception as e:
                    st.error(f"生成失敗: {e}")
                    st.code(traceback.format_exc())
            
            # 如果 Session 中有圖片，就顯示 (避免切換 Tab 消失)
            elif 'last_img_path' in st.session_state and os.path.exists(st.session_state['last_img_path']):
                st.image(st.session_state['last_img_path'], caption="上次生成", use_container_width=True)
                img_path = st.session_state['last_img_path']

        with col2:
            st.markdown("### 發送至 Discord")
            msg_text = st.text_area("附加訊息", value=f"📊 {stock_input} 籌碼分析日報")
            
            if st.button("📤 發送"):
                if not discord_webhook:
                    st.error("請在左側輸入 Webhook URL")
                elif not img_path or not os.path.exists(img_path):
                    st.error("請先生成圖片")
                else:
                    with st.spinner("發送中..."):
                        res = send_image_to_discord(img_path, discord_webhook, msg_text)
                        if "成功" in res: st.success(res)
                        else: st.error(res)

if __name__ == "__main__":
    main()

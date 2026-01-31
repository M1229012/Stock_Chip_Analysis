# main.py
import os
import re
import pandas as pd
import yfinance as yf
import requests
import mplfinance as mpf
import matplotlib.pyplot as plt
from io import StringIO
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 設定 ---
STOCK_ID = "2313"
# 從環境變數讀取 Webhook (GitHub Secrets)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# --- 輔助函式 ---
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
    # 簡單計算 MA & BB
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Up'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Low'] = df['BB_Mid'] - 2 * df['BB_Std']
    return df

def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    # 嘗試偽裝 User-Agent 避免被阻擋
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def get_stock_price(stock_id):
    print(f"抓取股價: {stock_id}")
    try:
        df = yf.Ticker(f"{stock_id}.TW").history(period="1y")
        if df.empty:
            df = yf.Ticker(f"{stock_id}.TWO").history(period="1y")
        
        if not df.empty:
            df['Volume'] = df['Volume'] / 1000
            df.index = df.index.tz_localize(None)
            df['DateStr'] = df.index.strftime('%Y-%m-%d')
            return calculate_technical_indicators(df)
    except Exception as e:
        print(f"股價抓取錯誤: {e}")
    return None

def get_institutional_data(stock_id, start_date, end_date):
    print("抓取法人資料...")
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcl/zcl.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        # 等待比較久一點，避免網路延遲
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'外資買賣超')]")))
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
    except Exception as e:
        print(f"法人資料抓取失敗 (可能是被阻擋): {e}")
    finally:
        driver.quit()
    return None

def get_margin_data(stock_id, start_date, end_date):
    print("抓取融資券資料...")
    driver = get_driver()
    url = f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zcn/zcn.djhtm?a={stock_id}&c={start_date}&d={end_date}"
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//td[contains(text(),'融資餘額')]")))
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
    except Exception as e:
        print(f"融資券資料抓取失敗: {e}")
    finally:
        driver.quit()
    return None

def generate_plot(stock_id, df_price, df_inst, df_margin):
    print("開始繪圖...")
    df = df_price.copy()
    df.index = pd.to_datetime(df['DateStr'])
    
    # 合併法人
    if df_inst is not None:
        inst = df_inst.set_index('DateStr')
        inst.index = pd.to_datetime(inst.index)
        inst = inst[~inst.index.duplicated(keep='last')]
        df = df.join(inst[['外資買賣超', '投信買賣超', '自營商買賣超']], how='left')
        df['三大法人合計'] = df['外資買賣超'].fillna(0) + df['投信買賣超'].fillna(0) + df['自營商買賣超'].fillna(0)
    
    # 合併融資
    if df_margin is not None:
        margin = df_margin.set_index('DateStr')
        margin.index = pd.to_datetime(margin.index)
        margin = margin[~margin.index.duplicated(keep='last')]
        df = df.join(margin[['融資增減']], how='left')

    # 取最後 120 天
    df = df.tail(120)

    # 設定圖表樣式
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, gridstyle=':', y_on_right=True)
    
    add_plots = []
    # 主圖 MA & BB
    if 'MA5' in df.columns: add_plots.append(mpf.make_addplot(df['MA5'], panel=0, color='orange', width=1))
    if 'MA20' in df.columns: add_plots.append(mpf.make_addplot(df['MA20'], panel=0, color='#ff00ff', width=1.5))
    if 'BB_Up' in df.columns: add_plots.append(mpf.make_addplot(df['BB_Up'], panel=0, color='gray', linestyle='--', width=0.8))
    if 'BB_Low' in df.columns: add_plots.append(mpf.make_addplot(df['BB_Low'], panel=0, color='gray', linestyle='--', width=0.8))

    # 副圖1: 三大法人
    if '三大法人合計' in df.columns:
        colors = ['r' if v >= 0 else 'g' for v in df['三大法人合計'].fillna(0)]
        add_plots.append(mpf.make_addplot(df['三大法人合計'], panel=2, type='bar', color=colors, ylabel='Inst'))

    # 副圖2: 融資
    if '融資增減' in df.columns:
        colors = ['r' if v >= 0 else 'g' for v in df['融資增減'].fillna(0)]
        add_plots.append(mpf.make_addplot(df['融資增減'], panel=3, type='bar', color=colors, ylabel='Margin'))

    # 存檔
    output_filename = "dashboard.png"
    mpf.plot(
        df, type='candle', style=s, volume=True, addplot=add_plots,
        panel_ratios=(3, 1, 1, 1), 
        title=dict(title=f"{stock_id} Daily Report", size=20),
        figsize=(12, 16),
        savefig=dict(fname=output_filename, dpi=100, bbox_inches='tight')
    )
    return output_filename

def send_discord(img_path):
    if not WEBHOOK_URL:
        print("❌ 錯誤：未設定 Webhook URL")
        return

    print("發送至 Discord...")
    try:
        with open(img_path, "rb") as f:
            payload = {"content": f"📊 **{STOCK_ID} 自動籌碼戰情分析** ({datetime.now().strftime('%Y-%m-%d')})"}
            files = {"file": (img_path, f, "image/png")}
            r = requests.post(WEBHOOK_URL, data=payload, files=files)
            print(f"狀態碼: {r.status_code}")
    except Exception as e:
        print(f"發送失敗: {e}")

# --- 主程式 ---
if __name__ == "__main__":
    print(f"啟動自動化腳本 - 目標: {STOCK_ID}")
    
    # 1. 抓股價
    df_price = get_stock_price(STOCK_ID)
    if df_price is None or df_price.empty:
        print("無法取得股價，程式結束")
        exit(1)

    # 2. 抓籌碼 (計算日期)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=200)
    s_d = start_dt.strftime('%Y-%m-%d')
    e_d = end_dt.strftime('%Y-%m-%d')
    
    df_inst = get_institutional_data(STOCK_ID, s_d, e_d)
    df_margin = get_margin_data(STOCK_ID, s_d, e_d)

    # 3. 繪圖
    img = generate_plot(STOCK_ID, df_price, df_inst, df_margin)
    
    # 4. 發送
    send_discord(img)
    print("✅ 任務完成")

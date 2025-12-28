import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
import twstock  # 確保已匯入

# ================= 1. 系統設定 =================

st.set_page_config(layout="wide", page_title="籌碼K線")

st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 18px !important; }
    .stDataFrame { font-size: 16px !important; }
    .metric-container {
        display: flex;
        justify-content: space-between;
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
        margin-top: 5px;
    }
    .metric-item {
        text-align: center;
        width: 48%;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #aaa;
    }
    .metric-value {
        font-size: 1.2rem;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

COLOR_UP = '#ef5350'
COLOR_DOWN = '#26a69a'

def normalize_name(name):
    return str(name).strip().replace(" ", "").replace("　", "")

# 新增：獲取股票名稱函式
def get_stock_name(stock_id):
    try:
        if stock_id in twstock.codes:
            return twstock.codes[stock_id].name
        return ""
    except:
        return ""

# ================= 2. 爬蟲核心 (已修正雲端相容性) =================

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
    
    # 雲端環境路徑偵測 (Streamlit Cloud 專用)
    if shutil.which("chromium"):
        options.binary_location = shutil.which("chromium")
    elif shutil.which("chromium-browser"):
        options.binary_location = shutil.which("chromium-browser")
        
    # 決定 Driver 的 Service
    if shutil.which("chromedriver"):
        service = Service(shutil.which("chromedriver"))
    else:
        service = Service(get_driver_path())

    driver = webdriver.Chrome(service=service, options=options)
    return driver

def calculate_date_range(stock_id, days):
    try:
        # 校正邏輯：經比對 120天與240天 yfinance 資料比券商網頁多一天 (起始日早一天)
        # 故針對長天期減去 1 天以對齊網頁日期 (7/4 -> 7/7, 12/31 -> 1/2)
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

# ✅ 修改：TTL 設定為 604800 秒 (約 7 天)
@st.cache_data(persist="disk", ttl=604800)
def get_real_data_matrix(stock_id, start_date, end_date):
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

# ✅ 修改：TTL 設定為 604800 秒 (約 7 天)
@st.cache_data(persist="disk", ttl=604800)
def get_specific_broker_daily(stock_id, broker_params, start_date, end_date):
    driver = get_driver()
    c_val = broker_params.get('C', '1')
    base_url = "https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0/zco0.djhtm"
    target_url = (f"{base_url}?A={stock_id}"
                  f"&BHID={broker_params['BHID']}"
                  f"&b={broker_params['b']}"
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
        
        return df
    except Exception:
        return None

# ================= 3. 介面邏輯 =================

st.title(f"📊 籌碼K線")

tz = pytz.timezone('Asia/Taipei')
current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

with st.sidebar:
    st.header("參數設定")
    stock_input_raw = st.text_input("股票代號", value="3030")
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
        st.cache_data.clear()
        st.rerun()

if stock_input:
    # 獲取股票名稱
    stock_name = get_stock_name(stock_input)
    stock_display = f"{stock_input} {stock_name}" if stock_name else stock_input

    rank_start_date, rank_end_date = calculate_date_range(stock_input, selected_days)
    
    with st.spinner(f"正在分析 {stock_display} 近 {selected_days} 交易日 ({rank_start_date} ~ {rank_end_date})..."):
        df_buy, df_sell, sum_buy, sum_sell, broker_info, target_url = get_real_data_matrix(stock_input, rank_start_date, rank_end_date)
        
    df_price = get_stock_price(stock_input)

    if df_buy is not None and df_sell is not None:
        # ✅ 修改：標題加入股票名稱
        st.subheader(f"🏆 {stock_display} 區間累積 ({rank_start_date} ~ {rank_end_date}) - 主力買賣超排行")
        st.caption(f"排行總表網址：{target_url}")
        
        col1, col2 = st.columns(2)
        
        full_config = {
            "broker": "券商分點",
            "buy": st.column_config.NumberColumn("買進", format="%d"),
            "sell": st.column_config.NumberColumn("賣出", format="%d"),
            "net": st.column_config.NumberColumn("買賣超", format="%d"),
            "pct": "佔比"
        }

        with col1:
            st.markdown("#### 🔴 買超前 15 大")
            st.dataframe(
                df_buy.style.map(lambda x: f'color: {COLOR_UP}; font-weight: bold', subset=['net']),
                use_container_width=True, height=500, hide_index=True, column_config=full_config
            )
            st.markdown(f"""
            <div class="metric-container" style="border-left: 5px solid {COLOR_UP};">
                <div class="metric-item">
                    <div class="metric-label">合計買超張數</div>
                    <div class="metric-value" style="color: {COLOR_UP};">{sum_buy['total']}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">平均買超成本</div>
                    <div class="metric-value">{sum_buy['avg']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("#### 🟢 賣超前 15 大")
            st.dataframe(
                df_sell.style.map(lambda x: f'color: {COLOR_DOWN}; font-weight: bold', subset=['net']),
                use_container_width=True, height=500, hide_index=True, column_config=full_config
            )
            st.markdown(f"""
            <div class="metric-container" style="border-left: 5px solid {COLOR_DOWN};">
                <div class="metric-item">
                    <div class="metric-label">合計賣超張數</div>
                    <div class="metric-value" style="color: {COLOR_DOWN};">{sum_sell['total']}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">平均賣超成本</div>
                    <div class="metric-value">{sum_sell['avg']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        if df_price is not None and not df_price.empty:
            st.subheader("🔍 分點進出 vs 股價走勢")
            
            ma_options = ['MA5', 'MA10', 'MA20', 'MA60']
            selected_mas = st.multiselect("選擇要顯示的均線", ma_options, default=['MA5', 'MA10', 'MA20'])
            
            brokers_list = df_buy['broker'].tolist() + df_sell['broker'].tolist()
            brokers_list = list(dict.fromkeys(brokers_list))
            
            target_broker = st.selectbox("選擇要查看每日明細的券商", brokers_list)
            
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

            if broker_params:
                long_start_date = df_price['DateStr'].iloc[0] 
                long_end_date = rank_end_date 
                
                with st.spinner(f"正在爬取 {target_broker} 完整 2 年每日明細..."):
                    broker_daily_df, detail_url = get_specific_broker_daily(stock_input, broker_params, long_start_date, long_end_date)
                    
                    st.markdown(f"**🔗 正在爬取單一券商網址：** `{detail_url}`")
                    
                    if broker_daily_df is not None and not broker_daily_df.empty:
                        broker_daily_df = broker_daily_df.drop_duplicates(subset=["DateStr"], keep="last").sort_values('DateStr')
                        merged_df = pd.merge(df_price, broker_daily_df, on='DateStr', how='left')
                        merged_df['買賣超_Final'] = merged_df['買賣超_Calc'].fillna(0)
                        merged_df['cumulative_net'] = merged_df['買賣超_Final'].cumsum()
            
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                row_heights=[0.8, 0.2], specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
            )
            
            plot_df = merged_df if merged_df is not None else df_price
            plot_df = plot_df.copy()
            
            # ========== 計算 2 年全域最高與最低價 ==========
            global_min = plot_df['Low'].min()
            global_max = plot_df['High'].max()
            y_range = [global_min * 0.95, global_max * 1.05]
            # ============================================

            # ========== 加入 T+3 空白日期 ==========
            last_date_str = plot_df['DateStr'].iloc[-1]
            last_date_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
            
            future_dates = []
            for i in range(1, 4):
                next_day = last_date_dt + timedelta(days=i)
                future_dates.append(next_day.strftime("%Y-%m-%d"))
            
            for d_str in future_dates:
                new_row = {col: None for col in plot_df.columns}
                new_row['DateStr'] = d_str
                plot_df = pd.concat([plot_df, pd.DataFrame([new_row])], ignore_index=True)
            
            x_data = plot_df['DateStr']
            # =======================================

            # 1. K線圖
            fig.add_trace(go.Candlestick(
                x=x_data, open=plot_df['Open'], high=plot_df['High'],
                low=plot_df['Low'], close=plot_df['Close'], name='股價',
                increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN,
                increasing_fillcolor=COLOR_UP, decreasing_fillcolor=COLOR_DOWN
            ), row=1, col=1)

            # 2. 均線
            ma_colors = {'MA5': 'orange', 'MA10': 'cyan', 'MA20': 'magenta', 'MA60': 'green'}
            for ma in selected_mas:
                fig.add_trace(go.Scatter(
                    x=x_data, y=plot_df[ma], name=ma,
                    line=dict(color=ma_colors.get(ma, 'white'), width=1)
                ), row=1, col=1)

            if merged_df is not None:
                extended_buy_sell = list(merged_df['買賣超_Final']) + [None]*3
                extended_cum_net = list(merged_df['cumulative_net']) + [None]*3
                
                bar_colors = [
                    COLOR_UP if (v is not None and v > 0) else 
                    COLOR_DOWN if (v is not None and v < 0) else 'gray' 
                    for v in extended_buy_sell
                ]
                
                fig.add_trace(go.Bar(
                    x=x_data, 
                    y=extended_buy_sell, 
                    name='每日買賣超(張)', 
                    marker_color=bar_colors,
                    opacity=1.0
                ), row=2, col=1, secondary_y=False)
                
                fig.add_trace(go.Scatter(
                    x=x_data,
                    y=extended_cum_net,
                    name='累計庫存(2年)',
                    mode='lines',
                    line=dict(color='yellow', width=2),
                    connectgaps=True
                ), row=2, col=1, secondary_y=True)
                
                fig.add_vrect(
                    x0=rank_start_date, 
                    x1=rank_end_date,
                    fillcolor="gray", 
                    opacity=0.15, 
                    layer="below", 
                    line_width=0,
                    annotation_text="統計區間", 
                    annotation_position="top left",
                    row='all', col=1
                )
                
                st.success(f"✅ 已取得 {target_broker} 完整 2 年數據")
            else:
                if target_broker:
                      st.warning(f"⚠️ 無法抓取 {target_broker} 的詳細資料。")

            # 設定 Y 軸 (固定範圍)
            fig.update_yaxes(
                range=y_range,
                fixedrange=True,
                row=1, col=1
            )

            # X 軸預設範圍
            total_len_with_future = len(plot_df)
            zoom_days = selected_days
            zoom_start_idx = max(0, total_len_with_future - zoom_days - 3)
            end_idx = total_len_with_future - 1
            
            fig.update_xaxes(
                type='category', 
                tickmode='auto', 
                nticks=20, 
                range=[zoom_start_idx - 0.5, end_idx + 0.5], 
                row=1, col=1
            )
            fig.update_xaxes(
                type='category', 
                tickmode='auto', 
                nticks=20, 
                range=[zoom_start_idx - 0.5, end_idx + 0.5], 
                row=2, col=1
            )

            # ✅ 修改：圖表標題也加入股票名稱
            fig.update_layout(
                height=800, 
                xaxis_rangeslider_visible=False, 
                plot_bgcolor='rgba(20,20,20,1)', 
                paper_bgcolor='rgba(20,20,20,1)',
                font=dict(color='white'), 
                title=f"{stock_display} - {target_broker if target_broker else '股價'} 籌碼追蹤", 
                dragmode='pan',
                hovermode='x unified',
                legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center")
            )
            
            fig.update_yaxes(title_text="股價", row=1, col=1, showgrid=True, gridcolor='rgba(128,128,128,0.2)')
            fig.update_yaxes(title_text="每日張數", row=2, col=1, secondary_y=False, showgrid=True, gridcolor='rgba(128,128,128,0.2)')
            fig.update_yaxes(title_text="累計張數", row=2, col=1, secondary_y=True, showgrid=False)
            
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
    else:
        st.error(f"⚠️ 查無資料，請確認股票代號或稍後再試。")

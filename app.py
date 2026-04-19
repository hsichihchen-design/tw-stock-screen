import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta

# ==========================================
# 頁面與底色初始化
# ==========================================
st.set_page_config(page_title="台股掃圖", layout="wide")

# 強制設定 Streamlit 區塊為極致白底
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 0rem; }
    </style>
    """, unsafe_allow_html=True)


st.markdown("""
    <style>
    /* 1. 強制整個網頁的底層背景為純白 */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }
    
    /* 2. 強制網頁內所有的文字為純黑、加粗 */
    .stApp * {
        color: #000000 !important;
        font-family: "Arial", sans-serif !important;
    }
      
    /* 4. 隱藏側邊欄與縮減頂部邊距 */
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    </style>
    """, unsafe_allow_html=True)


# ==========================================
# 1. 先定義載入資料的函數
# ==========================================
def load_analysis_results():
    try:
        with open('uptrend_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# ==========================================
# 2. 執行載入資料 (現在 data_store 被認識了)
# ==========================================
data_store = load_analysis_results()

if not data_store:
    st.error("找不到分析數據，請先執行最新版的 update_data.py")
    st.stop()

# ==========================================
# 3. 顯示標題與更新時間 (使用已讀取的資料)
# ==========================================
last_updated = data_store.get('last_updated', '未知')

# 標題與更新時間合併為單一欄位
st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #000000; padding-top: 25px; padding-bottom: 5px; margin-bottom: 10px;'>
        <div style='font-size: 2.2rem; font-weight: 900; color: #000000; line-height: 1.2;'>台股掃圖</div>
        <div style='font-size: 0.9rem; font-weight: 800; color: #000000;'>更新：{last_updated}</div>
    </div>
    """, unsafe_allow_html=True)
# ==========================================
# 4. 資料過濾與排序
# ==========================================
all_results = data_store['results']
end_date = datetime.now()
half_year_ago = end_date - timedelta(days=365)

# 取得符合代號列表
symbol_list = sorted(list(set([seg['symbol'] for seg in all_results])))

# ==========================================
# 5. 批次下載
# ==========================================
@st.cache_data(ttl=3600)
def fetch_batch_data(symbols):
    download_start = half_year_ago - timedelta(days=90)
    # 這裡加入一個防呆：如果沒有股票清單，直接回傳空字典
    if not symbols:
        return {}
    data = yf.download(symbols, start=download_start.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), group_by='ticker', progress=False)
    return data

if symbol_list:
    with st.spinner(f"正在載入 {len(symbol_list)} 檔精選標的..."):
        stock_data = fetch_batch_data(symbol_list)

    # ==========================================
    # 6. 繪圖渲染 (雙欄極致看板模式)
    # ==========================================
    # 建立兩個直欄
    cols = st.columns(2) 
    
    for i, sym in enumerate(symbol_list):
        try:
            # 取出資料
            df = stock_data[sym].copy() if len(symbol_list) > 1 else stock_data.copy()
            df = df.dropna(subset=['Close'])
            
            if df.empty:
                continue

            # 計算均線
            df['MA10'] = df['Close'].rolling(window=10).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            
            # 切片
            plot_df = df.tail(120).copy()
            
            if not plot_df.empty:
                # ==========================================
                # 【核心修改 2】將日期轉為純文字，破除時間軸空白
                # ==========================================
                plot_df['DateStr'] = plot_df.index.strftime('%m-%d')
                
                # 建立子圖
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    row_heights=[0.8, 0.2], vertical_spacing=0.03)
                
                # 1. K線 (把 x=plot_df.index 全部換成 x=plot_df['DateStr'])
                fig.add_trace(go.Candlestick(
                    x=plot_df['DateStr'], open=plot_df['Open'], high=plot_df['High'], 
                    low=plot_df['Low'], close=plot_df['Close'],
                    increasing_line_color='#E32636', decreasing_line_color='#008F39', 
                    increasing_fillcolor='#E32636', decreasing_fillcolor='#008F39',
                    increasing_line_width=0.7, decreasing_line_width=0.7,                 
                    name='K線'
                ), row=1, col=1)
                
                # 2. 均線 (x 換成 DateStr)
                fig.add_trace(go.Scatter(x=plot_df['DateStr'], y=plot_df['MA10'], line=dict(color='#f6c23e', width=1), name='10MA'), row=1, col=1)
                fig.add_trace(go.Scatter(x=plot_df['DateStr'], y=plot_df['MA20'], line=dict(color='#8e44ad', width=1), name='20MA'), row=1, col=1)
                fig.add_trace(go.Scatter(x=plot_df['DateStr'], y=plot_df['MA60'], line=dict(color='#36b9cc', width=1), name='60MA'), row=1, col=1)
                
                # 3. 成交量 (x 換成 DateStr)
                v_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(plot_df['Close'], plot_df['Open'])]
                fig.add_trace(go.Bar(x=plot_df['DateStr'], y=plot_df['Volume'], marker_color=v_colors, name='量'), row=2, col=1)
                
                # 4. 排版設定
                fig.update_layout(
                    height=350,
                    # 👈 關鍵修正 2：大幅縮減左邊(l)與下方(b)的留白，把寶貴的像素寬度全數釋放給 K 棒
                    margin=dict(l=5, r=40, t=50, b=20), 
                    xaxis_rangeslider_visible=False,
                    template="plotly_white",
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    title=dict(
                        text=f"<b>{sym}</b>", 
                        font=dict(color='black', size=22)
                    ), 
                    font=dict(color='black'), 
                    showlegend=False,
                    dragmode=False,
                    hovermode=False
                )
                
                # 5. 座標軸設定
                fig.update_xaxes(type='category', nticks=10, showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(color='black', size=12), row=1, col=1) 
                fig.update_xaxes(type='category', nticks=10, showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(color='black', size=11), row=2, col=1)
                
                fig.update_yaxes(showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(color='black', size=12), side='right', row=1, col=1)
                fig.update_yaxes(showgrid=False, zeroline=False, fixedrange=True, showticklabels=False, row=2, col=1)
                
                # ==========================================
                # 【核心修改點】將圖表塞進對應的欄位中
                # 偶數索引 (0, 2, 4...) 放左邊 cols[0]，奇數放右邊 cols[1]
                # ==========================================
                if i % 2 == 0:
                    cols = st.columns(2)
                
                # 依序塞入目前的排位中 (偶數放左 cols[0]，奇數放右 cols[1])
                with cols[i % 2]:
                    st.plotly_chart(
                        fig, 
                        use_container_width=True, 
                        key=f"fig_{sym}", 
                        theme=None, 
                        config={
                            'toImageButtonOptions': {
                                'format': 'png',
                                'filename': f'{sym}_Analysis',
                                'scale': 2
                            },
                            'staticPlot': True,
                            'displayModeBar': False
                        }
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                
        except Exception:
            continue
st.write("---")
st.write("已經到底囉！")

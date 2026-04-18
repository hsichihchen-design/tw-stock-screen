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
st.set_page_config(page_title="台股型態瀏覽器", layout="wide")

# 強制設定 Streamlit 區塊為極致白底
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 0rem; }
    </style>
    """, unsafe_allow_html=True)

last_updated = data_store.get('last_updated', '未知')

# 建立兩欄：第一欄寬度大，放標題；第二欄寬度小，放更新時間
col_title, col_time = st.columns([3, 1])

with col_title:
    st.title("📈 台股近半年線圖")

with col_time:
    # 這裡使用 markdown 加上簡單的 CSS 來微調位置，讓它靠右並對齊標題高度
    st.markdown(f"""
        <div style="text-align: right; padding-top: 25px; color: #555555; font-size: 0.9rem;">
            <b>最後更新時間</b><br>{last_updated}
        </div>
        """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_analysis_results():
    try:
        with open('uptrend_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

data_store = load_analysis_results()

if not data_store:
    st.error("找不到分析數據，請先執行最新版的 update_data.py")
    st.stop()

# ==========================================
# 資料過濾與排序 (依序號)
# ==========================================
all_results = data_store['results']
end_date = datetime.now()
half_year_ago = end_date - timedelta(days=180)

# 取得符合代號列表
symbol_list = sorted(list(set([seg['symbol'] for seg in all_results])))

# ==========================================
# 批次下載
# ==========================================
@st.cache_data(ttl=3600)
def fetch_batch_data(symbols):
    download_start = half_year_ago - timedelta(days=90)
    data = yf.download(symbols, start=download_start.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), group_by='ticker', progress=False)
    return data

if symbol_list:
    with st.spinner(f"正在載入 {len(symbol_list)} 檔精選標的..."):
        stock_data = fetch_batch_data(symbol_list)

# ==========================================
# 繪圖渲染 (全寬、無格線、實心 K 棒)
# ==========================================
for i, sym in enumerate(symbol_list):
    # 取出資料
    df = stock_data[sym].copy() if len(symbol_list) > 1 else stock_data.copy()
    df = df.dropna(subset=['Close'])
    
    # 計算均線
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 切片
    plot_df = df.loc[df.index >= half_year_ago]
    
    if not plot_df.empty:
        # 建立子圖
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            row_heights=[0.8, 0.2], vertical_spacing=0.03)
        
        # 1. K線 (實心、台股配色)
        fig.add_trace(go.Candlestick(
            x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], 
            low=plot_df['Low'], close=plot_df['Close'],
            increasing_line_color='#ef5350', decreasing_line_color='#26a69a', 
            increasing_fillcolor='#ef5350', decreasing_fillcolor='#26a69a', # 實心填色
            name='K線'
        ), row=1, col=1)
        
        # 2. 均線
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA10'], line=dict(color='#f6c23e', width=1.5), name='10MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA20'], line=dict(color='#8e44ad', width=1.5), name='20MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA60'], line=dict(color='#36b9cc', width=1.5), name='60MA'), row=1, col=1)
        
        # 3. 成交量
        v_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(plot_df['Close'], plot_df['Open'])]
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=v_colors, name='量'), row=2, col=1)
        
        # 4. 【核心修改】排版設定：關閉格線、設定背景
        fig.update_layout(
            height=600,
            margin=dict(l=40, r=40, t=60, b=60), # 增加邊距，確保手機端不切字
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            paper_bgcolor='white',
            plot_bgcolor='white',
            
            # 標題設定：加大且設為純黑
            title=dict(
                text=f"<b>{sym}</b>", 
                font=dict(color='black', size=24)
            ), 
            
            # 全域字體設定 (作為預備)
            font=dict(color='black'), 
            
            showlegend=False,
            dragmode=False  
        )
        
        # 5. 座標軸詳細設定：強制刻度文字為純黑
        # 對 X 軸 (日期) 的設定
        fig.update_xaxes(
            showgrid=False, 
            zeroline=False, 
            fixedrange=True, 
            tickfont=dict(color='black', size=14), # 👈 強制設定日期顏色為純黑，字級 14
            tickformat='%Y-%m-%d',                 # 確保日期格式清晰
            row=1, col=1
        )
        fig.update_xaxes(showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(color='black', size=12), row=2, col=1)
        
        # 對 Y 軸 (價格) 的設定
        fig.update_yaxes(
            showgrid=False, 
            zeroline=False, 
            fixedrange=True, 
            tickfont=dict(color='black', size=14), # 👈 強制設定價格顏色為純黑，字級 14
            side='right',                          # 價格靠右顯示通常在手機上更直覺
            row=1, col=1
        )
        fig.update_yaxes(showgrid=False, zeroline=False, fixedrange=True, tickfont=dict(color='black', size=12), row=2, col=1)
        
        # 6. 下載配置
        st.plotly_chart(
            fig, 
            use_container_width=True, 
            key=f"fig_{sym}", 
            theme=None,            # 👈 魔法參數：解除 Streamlit 強制主題綁架，還原純黑字體！
            config={
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'{sym}_Analysis',
                    'scale': 2
                },
                'displayModeBar': False  # 隱藏上方工具列
            }
        )
        st.markdown("<br><br>", unsafe_allow_html=True)

st.write("---")
st.write("已經到底囉！")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

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
# 1. 載入 JSON 資料 (免下載)
# ==========================================
def load_analysis_results():
    try:
        with open('uptrend_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

data_store = load_analysis_results()

if not data_store or 'results' not in data_store:
    st.error("找不到分析數據或格式錯誤，請先執行最新版的 update_data_tw.py")
    st.stop()

# ==========================================
# 2. 顯示標題與更新時間
# ==========================================
last_updated = data_store.get('last_updated', '未知')

st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #000000; padding-top: 25px; padding-bottom: 5px; margin-bottom: 10px;'>
        <div style='font-size: 2.2rem; font-weight: 900; color: #000000; line-height: 1.2;'>台股掃圖</div>
        <div style='font-size: 0.9rem; font-weight: 800; color: #000000;'>更新：{last_updated}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 準備渲染資料
# ==========================================
all_results = data_store['results']
symbol_list = sorted(list(all_results.keys()))

if not symbol_list:
    st.info("本次分析未發現符合條件的標的。")
    st.stop()

# ==========================================
# 4. 繪圖渲染 (雙欄極致看板模式)
# ==========================================
for i, sym in enumerate(symbol_list):
    try:
        # 從 JSON 中還原 DataFrame
        k_data = all_results[sym]
        plot_df = pd.DataFrame(k_data)
        
        if plot_df.empty:
            continue

        # 計算均線 (為節省 JSON 容量，均線由前端即時計算)
        plot_df['MA10'] = plot_df['close'].rolling(window=10).mean()
        plot_df['MA20'] = plot_df['close'].rolling(window=20).mean()
        plot_df['MA60'] = plot_df['close'].rolling(window=60).mean()
        
        # 建立子圖
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            row_heights=[0.8, 0.2], vertical_spacing=0.03)
        
        # 1. K線 (對應 JSON 中小寫的欄位名稱)
        fig.add_trace(go.Candlestick(
            x=plot_df['date'], open=plot_df['open'], high=plot_df['high'], 
            low=plot_df['low'], close=plot_df['close'],
            increasing_line_color='#E32636', decreasing_line_color='#008F39', 
            increasing_fillcolor='#E32636', decreasing_fillcolor='#008F39',
            increasing_line_width=0.7, decreasing_line_width=0.7,                 
            name='K線'
        ), row=1, col=1)
        
        # 2. 均線
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA10'], line=dict(color='#f6c23e', width=1), name='10MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA20'], line=dict(color='#8e44ad', width=1), name='20MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['MA60'], line=dict(color='#36b9cc', width=1), name='60MA'), row=1, col=1)
        
        # 3. 成交量
        v_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(plot_df['close'], plot_df['open'])]
        fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['volume'], marker_color=v_colors, name='量'), row=2, col=1)
        
        # 4. 排版設定
        fig.update_layout(
            height=350,
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
        
        # 雙欄排列
        if i % 2 == 0:
            cols = st.columns(2)
        
        with cols[i % 2]:
            # 💡 核心修改：將 Plotly 圖表轉為高畫質靜態 PNG
            # width 和 height 控制圖片的基礎比例
            # scale=2 代表解析度放大兩倍 (畫質提升)。如果覺得還是不夠清晰，可以改為 scale=3
            image_bytes = fig.to_image(format="png", width=800, height=450, scale=2)
            
            # 使用 Streamlit 的 image 函數來渲染靜態圖片
            st.image(image_bytes, use_column_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"渲染 {sym} 時發生錯誤: {e}")
        continue

st.write("---")
st.write("已經到底囉！")

import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
import io
import time  
from datetime import datetime, timedelta

# ==========================================
# 參數設定
# ==========================================
YEARS = 1
MIN_RISE_PCT = 0.35      # 波段最小漲幅 35%
MIN_DURATION = 5         # 最少持續 5 天
LOOKBACK_PERIOD = 15     # 找尋局部高低點的視窗大小
MAX_STOCKS = None        # None 代表跑全市場
BATCH_SIZE = 50          # 每次向 Yahoo 請求的股票數量

def get_tw_tickers():
    """抓取台灣上市(TW)與上櫃(TWO)股票代號"""
    print("正在獲取台股上市櫃清單...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    res_twse = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", headers=headers)
    df_twse = pd.read_html(io.StringIO(res_twse.text))[0] 
    twse_tickers = []
    for x in df_twse[0].dropna():
        parts = str(x).split() 
        if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 4:
            twse_tickers.append(parts[0] + '.TW')
    
    res_tpex = requests.get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", headers=headers)
    df_tpex = pd.read_html(io.StringIO(res_tpex.text))[0]
    tpex_tickers = []
    for x in df_tpex[0].dropna():
        parts = str(x).split()
        if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 4:
            tpex_tickers.append(parts[0] + '.TWO')
    
    all_tickers = twse_tickers + tpex_tickers
    print(f"共找到 {len(twse_tickers)} 檔上市, {len(tpex_tickers)} 檔上櫃")
    
    if MAX_STOCKS:
        print(f"⚠️ 測試模式：僅抽取前 {MAX_STOCKS} 檔股票進行分析")
        return all_tickers[:MAX_STOCKS]
    return all_tickers

def safe_batch_download(tickers, start_date, end_date, batch_size=50):
    """【批次下載與防護冷卻機制】"""
    all_data = {}
    total_batches = (len(tickers) // batch_size) + (1 if len(tickers) % batch_size != 0 else 0)
    
    print(f"\n📦 準備將 {len(tickers)} 檔股票分為 {total_batches} 個批次進行下載...")
    
    for i in range(total_batches):
        batch = tickers[i*batch_size : (i+1)*batch_size]
        if not batch:
            continue
            
        print(f"   ➤ 正在下載第 {i+1}/{total_batches} 批次 ({len(batch)} 檔)...", end=" ", flush=True)
        try:
            batch_data = yf.download(batch, start=start_date, end=end_date, group_by='ticker', progress=False)
            
            for symbol in batch:
                try:
                    if len(batch) == 1:
                        df_sym = batch_data
                    else:
                        df_sym = batch_data[symbol]
                        
                    if not df_sym.empty:
                        all_data[symbol] = df_sym.copy()
                except KeyError:
                    continue 
            
            print("✅ 成功")
            time.sleep(2) 
            
        except Exception as e:
            print(f"❌ 失敗 ({str(e)})")
            print("   ⏳ 疑似觸發防封鎖機制，強制休息 30 秒後繼續...")
            time.sleep(30)
            
    return all_data

def check_ma_trend(df):
    """【宏觀趨勢濾網】近半年內，是否有 >= 85% 的交易日滿足 MA10 > MA60 且 MA20 > MA60"""
    temp_df = pd.DataFrame(index=df.index)
    temp_df['Close'] = df['Close']
    
    temp_df['MA10'] = temp_df['Close'].rolling(window=10).mean()
    temp_df['MA20'] = temp_df['Close'].rolling(window=20).mean()
    temp_df['MA60'] = temp_df['Close'].rolling(window=60).mean()
    
    half_year_ago = datetime.now() - timedelta(days=180)
    recent_df = temp_df[temp_df.index >= half_year_ago].dropna()
    
    if len(recent_df) < 60: 
        return False
        
    valid_days = ((recent_df['MA10'] > recent_df['MA60']) & (recent_df['MA20'] > recent_df['MA60'])).sum()
    ratio = valid_days / len(recent_df)
    
    return ratio >= 0.75

def identify_uptrend(df, symbol):
    """【微觀波段識別演算法】"""
    if len(df) < LOOKBACK_PERIOD * 2:
        return []

    highs, lows = [], []
    for i in range(LOOKBACK_PERIOD, len(df) - LOOKBACK_PERIOD):
        window = df.iloc[i-LOOKBACK_PERIOD : i+LOOKBACK_PERIOD+1]
        
        if float(df['High'].iloc[i]) == float(window['High'].max()):
            highs.append((i, float(df['High'].iloc[i]), df.index[i]))
        if float(df['Low'].iloc[i]) == float(window['Low'].min()):
            lows.append((i, float(df['Low'].iloc[i]), df.index[i]))

    segments = []
    used_highs = set()

    for low_idx, low_price, low_time in lows:
        candidates = [h for h in highs if h[0] > low_idx and h[0] not in used_highs]
        if not candidates: continue
        
        best_high = None
        best_rise = 0
        
        for high_idx, high_price, high_time in candidates:
            rise_pct = (high_price - low_price) / low_price
            duration = high_idx - low_idx
            
            if rise_pct >= MIN_RISE_PCT and duration >= MIN_DURATION:
                segment_data = df.iloc[low_idx+1:high_idx]
                
                if len(segment_data) == 0:
                    is_pure = True
                else:
                    min_in_segment = float(segment_data['Low'].min())
                    is_pure = min_in_segment > float(low_price)
                
                if is_pure:
                    if rise_pct > best_rise:
                        best_rise = rise_pct
                        best_high = (high_idx, high_price, high_time)
        
        if best_high:
            high_idx, high_price, high_time = best_high
            used_highs.add(high_idx)
            segments.append({
                'symbol': symbol,
                'start_date': low_time.strftime('%Y-%m-%d'),
                'end_date': high_time.strftime('%Y-%m-%d'),
                'start_price': round(float(low_price), 2),
                'end_price': round(float(high_price), 2),
                'rise_pct': round(float(best_rise), 4),
                'duration_days': int(high_idx - low_idx)
            })
    return segments

def main():
    tickers = get_tw_tickers()
    if not tickers:
        print("未獲取到任何股票代號，程式終止。")
        return

    start_date = (datetime.now() - timedelta(days=YEARS * 365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    data_dict = safe_batch_download(tickers, start_date, end_date, batch_size=BATCH_SIZE)
    
    all_results = []
    failed_count = 0
    filtered_out_by_ma = 0
    filtered_out_by_timing = 0  # 紀錄因時間條件被淘汰的數量
    
    # 計算兩個月前（60天前）的基準日期
    two_months_ago = datetime.now() - timedelta(days=30)
    
    print("\n開始執行三重過濾 (宏觀均線 + 微觀波段 + 沉澱期濾網)...")
    for symbol in tickers:
        try:
            if symbol not in data_dict:
                continue
            raw_df = data_dict[symbol].copy()
                
            if isinstance(raw_df.columns, pd.MultiIndex):
                raw_df.columns = raw_df.columns.get_level_values(0)
                
            clean_df = raw_df.dropna(subset=['High', 'Low', 'Close']).copy()
            
            if len(clean_df) == 0:
                continue
                
            # 【第 1 關】：宏觀趨勢過濾
            if not check_ma_trend(clean_df):
                filtered_out_by_ma += 1
                continue
                
            # 【第 2 關】：微觀波段識別
            segments = identify_uptrend(clean_df, symbol)
            if segments:
                # 【第 3 關】：時間濾網 (判斷是否至少有一個波段的結束日是在 60 天之前)
                has_old_uptrend = any(datetime.strptime(seg['end_date'], '%Y-%m-%d') <= two_months_ago for seg in segments)
                
                if has_old_uptrend:
                    all_results.extend(segments)
                else:
                    # 如果所有波段都發生在最近 60 天內，則淘汰
                    filtered_out_by_timing += 1
                
        except Exception as e:
            failed_count += 1
            continue
            
    tw_time = datetime.utcnow() + timedelta(hours=8)
    output = {
        'last_updated': tw_time.strftime('%Y-%m-%d %H:%M:%S'), # 👈 確保這裡是寫入 tw_time
        'total_segments_found': len(all_results),
        'results': all_results
    }
    
    with open('uptrend_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 分析完成！")
    print(f"📊 淘汰報告：")
    print(f"   - {filtered_out_by_ma} 檔因【均線未達多頭標準】被淘汰。")
    print(f"   - {filtered_out_by_timing} 檔因【大漲發生在近兩個月內 (籌碼未沉澱)】被淘汰。")
    print(f"🎯 最終找到 {len(set([r['symbol'] for r in all_results]))} 檔強勢沉澱股，已存入 uptrend_results.json")
    if failed_count > 0:
        print(f"⚠️ 有 {failed_count} 檔股票在計算時發生例外狀況被跳過。")

if __name__ == "__main__":
    main()

import streamlit as st
import yfinance as yf
import ta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time

st.set_page_config(page_title="Custom Breakout Engine", layout="wide")

# App Header mimicking Chartink's custom dashboard layouts
st.title("🦅 Momentum Breakout Scanner (Chartink EOD & Live Engine)")
st.write("Tracks structural confluences during live hours and serves as an archive after market close.")

# --- SIDEBAR INTERACTIVE FILTERS ---
st.sidebar.header("🎯 Strategy Filter Settings")

# Strategy Threshold Toggles
min_rsi_15m = st.sidebar.slider("📈 Minimum 15m RSI", min_value=50, max_value=80, value=60)
min_rsi_hourly = st.sidebar.slider("⏳ Minimum 1h RSI", min_value=50, max_value=75, value=55)
min_vol_spike = st.sidebar.slider("🔥 Min Volume Multiple (vs 20 SMA)", min_value=1.0, max_value=4.0, value=2.0, step=0.5)

# Fetching the broad Nifty 500 index pool
@st.cache_data(ttl=86400)
def get_chartink_universe():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df_nse = pd.read_csv(url)
        return [str(sym).strip() + ".NS" for sym in df_nse['Symbol'].tolist()]
    except Exception:
        return ["TATAMOTORS.NS", "RELIANCE.NS", "SBIN.NS", "TATASTEEL.NS", "INFY.NS"]

all_tickers = get_chartink_universe()
st.sidebar.info(f"Tracking Universe: **{len(all_tickers)} NSE Stocks**")

# --- CORE PARALLEL DATA PROCESSING ENGINE ---
def scan_single_ticker(ticker):
    try:
        # Pull 5 days of data to look back across historical structures safely
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 60:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).strip() for col in df.columns]
        
        # 1. Higher Timeframe Reference (Daily Breakout)
        df['Trade_Date'] = df.index.date
        daily_data = df.groupby('Trade_Date').agg({'High': 'max', 'Low': 'min', 'Close': 'last'})
        daily_data['Daily_RSI'] = ta.momentum.rsi(daily_data['Close'], window=14)
        daily_data['Prev_Day_High'] = daily_data['High'].shift(1)
        
        df['Prev_Day_High'] = df['Trade_Date'].map(daily_data['Prev_Day_High'])
        df['Daily_RSI_Mapped'] = df['Trade_Date'].map(daily_data['Daily_RSI'])
        
        # 2. Lower Timeframe Structure (15m Execution Matrix)
        df['EMA_9'] = ta.trend.ema_indicator(df['Close'], window=9)
        df['EMA_21'] = ta.trend.ema_indicator(df['Close'], window=21)
        df['Vol_SMA_20'] = ta.trend.sma_indicator(df['Volume'], window=20)
        df['RSI_14'] = ta.momentum.rsi(df['Close'], window=14)
        df['Hourly_RSI'] = ta.momentum.rsi(df['Close'], window=56)
        df['BB_Upper'] = ta.volatility.bollinger_hband(df['Close'], window=20, window_dev=2)
        
        # Grab the last calculated data point (end of day if market is closed)
        last_row = df.iloc[-1]
        
        # 3. Strategy Confluence Logic Evaluation
        cond_ema = (last_row['Close'] > last_row['EMA_9']) and (last_row['EMA_9'] > last_row['EMA_21'])
        vol_multiple = float(last_row['Volume'] / last_row['Vol_SMA_20'])
        cond_vol = vol_multiple >= min_vol_spike
        cond_rsi = (last_row['RSI_14'] >= min_rsi_15m) and (last_row['Hourly_RSI'] >= min_rsi_hourly) and (last_row['Daily_RSI_Mapped'] > 55)
        cond_bb = last_row['Close'] > last_row['BB_Upper']
        cond_breakout = last_row['Close'] > last_row['Prev_Day_High']
        
        if cond_ema and cond_vol and cond_rsi and cond_bb and cond_breakout:
            return {
                "Ticker Symbol": ticker.replace(".NS", ""),
                "LTP (₹)": round(float(last_row['Close']), 2),
                "15m RSI": round(float(last_row['RSI_14']), 1),
                "1h RSI": round(float(last_row['Hourly_RSI']), 1),
                "Volume Multiple": round(vol_multiple, 2),
                "Breakout Status": "✅ Breakout Confirmed"
            }
    except Exception:
        return None
    return None

# --- RUN ENGINE MANUALLY FOR EOD REVIEWS ---
if st.button("🔍 Run Full Market Scan / Load Archived Data", type="primary"):
    st.info("Querying data cluster... Processing historical candle logs.")
    
    triggered_stocks = []
    
    # Process the entire market using parallel processing threads
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(scan_single_ticker, all_tickers)
        for res in results:
            if res is not None:
                triggered_stocks.append(res)
                
    # Update the visual elements on the dashboard dynamically
    if triggered_stocks:
        result_df = pd.DataFrame(triggered_stocks)
        result_df = result_df.sort_values(by="Volume Multiple", ascending=False)
        
        st.success(f"📊 Scan Completed! Found **{len(result_df)} stocks** that successfully executed confluences during the session.")
        
        # --- EXCEL / CSV DOWNLOAD BUTTON (Chartink Style Export) ---
        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Scan Results as CSV",
            data=csv_data,
            file_name=f"breakout_scan_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # Display Data Table
        st.dataframe(result_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Scan completed. No stocks met your precise confluence metrics during this session.")

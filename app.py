import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Custom 15m Scanner", layout="wide")
st.title("🚀 Custom 15-Minute Momentum Scanner")
st.write("A free, cloud-hosted scanner running your custom multi-timeframe breakout strategy.")

# Define your custom watchlist (Add your favorite NSE stocks here)
watchlist = [
    "TATAMOTORS.NS", "RELIANCE.NS", "SBIN.NS", "TATASTEEL.NS", "INFY.NS",
    "ITC.NS", "TCS.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "HDFCBANK.NS"
]

if st.button("🔴 Run Real-Time Market Scan", type="primary"):
    st.info("Scanning the market... This takes about 10-15 seconds for free servers.")
    
    triggered_stocks = []
    
    for ticker in watchlist:
        try:
            # Fetch last 5 days of 15m data to safely calculate 1-hour and daily metrics
            df = yf.download(ticker, period="5d", interval="15m", progress=False)
            if df.empty:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(col).strip() for col in df.columns]
            
            # 1. Higher Timeframe (Daily) Calculation from Intraday Data
            df['Trade_Date'] = df.index.date
            daily_data = df.groupby('Trade_Date').agg({
                'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            })
            daily_data['Daily_RSI'] = ta.rsi(daily_data['Close'], length=14)
            daily_data['Prev_Day_High'] = daily_data['High'].shift(1)
            
            df['Prev_Day_High'] = df['Trade_Date'].map(daily_data['Prev_Day_High'])
            df['Daily_RSI_Mapped'] = df['Trade_Date'].map(daily_data['Daily_RSI'])
            
            # 2. Lower Timeframe (15-Minute) Indicators
            df['EMA_9'] = ta.ema(df['Close'], length=9)
            df['EMA_21'] = ta.ema(df['Close'], length=21)
            df['Vol_SMA_20'] = ta.sma(df['Volume'], length=20)
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
            df['Hourly_RSI'] = ta.rsi(df['Close'], length=56) # 4 * 14 = 1 Hour
            
            bbands = ta.bbands(df['Close'], length=20, std=2)
            df['BB_Upper'] = bbands.iloc[:, 2]
            
            # Extract the absolute last closed 15-minute candle values
            last_row = df.iloc[-1]
            
            # 3. Chartink Logic Conditions
            cond_ema = (last_row['Close'] > last_row['EMA_9']) and (last_row['EMA_9'] > last_row['EMA_21'])
            cond_vol = last_row['Volume'] > (last_row['Vol_SMA_20'] * 2)
            cond_rsi = (last_row['RSI_14'] > 60) and (last_row['Hourly_RSI'] > 55) and (last_row['Daily_RSI_Mapped'] > 60)
            cond_bb = last_row['Close'] > last_row['BB_Upper']
            cond_breakout = last_row['Close'] > last_row['Prev_Day_High']
            
            if cond_ema and cond_vol and cond_rsi and cond_bb and cond_breakout:
                triggered_stocks.append({
                    "Ticker Symbol": ticker,
                    "Current Price (LTP)": f"₹{round(float(last_row['Close']), 2)}",
                    "15m RSI": round(float(last_row['RSI_14']), 1),
                    "Volume Multiple": f"{round(float(last_row['Volume'] / last_row['Vol_SMA_20']), 2)}x",
                    "Status": "✅ Breakout Confirmed"
                })
        except Exception as e:
            continue
            
    # Display Results
    if triggered_stocks:
        result_df = pd.DataFrame(triggered_stocks)
        st.success(f"🔥 Found {len(result_df)} momentum alert entries!")
        st.dataframe(result_df, use_container_width=True)
    else:
        st.warning("No stocks currently match all confluences. Try scanning again later.")

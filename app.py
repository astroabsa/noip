import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from upstox_python.api_client import ApiClient
from upstox_python.websocket.market_data_streamer import MarketDataStreamerV3
from streamlit_autorefresh import st_autorefresh
import threading
import json
from datetime import datetime

# --- CONFIG ---
INSTRUMENT_KEY = "NSE_INDEX|Nifty 50" 

if 'market_data' not in st.session_state:
    st.session_state.market_data = {
        'ltp': 0.0, 'prev_ltp': 0.0, 'oi': 0, 'prev_oi': 0, 'pcr': 0.0,
        'history': pd.DataFrame(columns=['time', 'ltp', 'pcr'])
    }

# --- WEBSOCKET ---
def on_message(ws, message):
    data = json.loads(message)
    if 'feeds' in data and INSTRUMENT_KEY in data['feeds']:
        ltp = data['feeds'][INSTRUMENT_KEY]['ff']['market_ff']['ltp']
        st.session_state.market_data['prev_ltp'] = st.session_state.market_data['ltp']
        st.session_state.market_data['ltp'] = ltp

def start_streamer():
    api_client = ApiClient()
    api_client.configuration.access_token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    streamer = MarketDataStreamerV3(api_client)
    streamer.on_message = on_message
    streamer.connect()
    streamer.subscribe([INSTRUMENT_KEY], "full")

if 'ws_thread' not in st.session_state:
    st.session_state.ws_thread = threading.Thread(target=start_streamer, daemon=True)
    st.session_state.ws_thread.start()

# --- UI ---
st.set_page_config(page_title="Nifty Terminal", layout="wide")
st_autorefresh(interval=2000, key="f5")

st.title("🚀 Nifty Conviction Terminal")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("LTP", f"₹{st.session_state.market_data['ltp']}", 
              f"{st.session_state.market_data['ltp'] - st.session_state.market_data['prev_ltp']:.2f}")

with col2:
    pcr = st.sidebar.number_input("Update PCR", value=1.0)
    st.session_state.market_data['pcr'] = pcr
    st.write(f"### PCR: {pcr}")

with col3:
    st.success("🔥 STRONG BULLISH") # Logic placeholder

st.line_chart(st.session_state.market_data['history'].set_index('time'))

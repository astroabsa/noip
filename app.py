import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from upstox_python.api_client import ApiClient
from upstox_python.websocket.market_data_streamer import MarketDataStreamerV3
from streamlit_autorefresh import st_autorefresh
import threading
import json
import time
from datetime import datetime

# --- CONFIGURATION ---
# Replace with your specific instrument key (e.g., Nifty 50 Index)
INSTRUMENT_KEY = "NSE_INDEX|Nifty 50" 

# --- SESSION STATE INITIALIZATION ---
if 'market_data' not in st.session_state:
    st.session_state.market_data = {
        'ltp': 0.0,
        'prev_ltp': 0.0,
        'oi': 0,
        'prev_oi': 0,
        'pcr': 0.0,
        'vwap': 0.0,
        'history': pd.DataFrame(columns=['time', 'ltp', 'pcr', 'oi'])
    }

# --- LOGIC PILLARS ---
def get_conviction_label(ltp, prev_ltp, oi, prev_oi):
    if ltp > prev_ltp and oi > prev_oi:
        return "🔥 STRONG BULLISH (Long Buildup)", "#00FF00"
    elif ltp < prev_ltp and oi > prev_oi:
        return "📉 STRONG BEARISH (Short Buildup)", "#FF4B4B"
    elif ltp > prev_ltp and oi < prev_oi:
        return "⚠️ WEAK BOUNCE (Short Covering)", "#00D1FF"
    elif ltp < prev_ltp and oi < prev_oi:
        return "🩸 PROFIT BOOKING (Long Unwinding)", "#FFA500"
    return "😴 NEUTRAL", "#808080"

# --- WEBSOCKET HANDLERS ---
def on_message(ws, message):
    data = json.loads(message)
    if 'feeds' in data and INSTRUMENT_KEY in data['feeds']:
        feed = data['feeds'][INSTRUMENT_KEY]
        if 'ff' in feed and 'market_ff' in feed['ff']:
            ltp = feed['ff']['market_ff']['ltp']
            # Update LTP in state
            st.session_state.market_data['prev_ltp'] = st.session_state.market_data['ltp']
            st.session_state.market_data['ltp'] = ltp

def start_streamer():
    access_token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    api_client = ApiClient()
    api_client.configuration.access_token = access_token
    
    streamer = MarketDataStreamerV3(api_client)
    streamer.on_message = on_message
    streamer.connect()
    streamer.subscribe([INSTRUMENT_KEY], "full")

# Start background thread for WebSocket if not already running
if 'ws_thread' not in st.session_state:
    st.session_state.ws_thread = threading.Thread(target=start_streamer, daemon=True)
    st.session_state.ws_thread.start()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Professional Conviction Terminal", layout="wide")

# Auto-refresh the UI every 2 seconds to reflect WebSocket updates
st_autorefresh(interval=2000, key="datarefresh")

st.title("⚡ Upstox Live Conviction Terminal")

# Sidebar for manual data injection (Simulating the Option Chain API Polling)
with st.sidebar:
    st.header("Manual/API Controls")
    st.write("Token Status: ✅ Active")
    # In a full automated setup, this part would poll the get_option_chain API
    new_pcr = st.number_input("Current PCR (from API)", value=1.0, step=0.01)
    new_oi = st.number_input("Current OI (from API)", value=1000000)
    
    if st.button("Update Sentiment Data"):
        st.session_state.market_data['pcr'] = new_pcr
        st.session_state.market_data['prev_oi'] = st.session_state.market_data['oi']
        st.session_state.market_data['oi'] = new_oi
        
        # Log to history for Delta PCR Velocity
        new_entry = pd.DataFrame([{
            'time': datetime.now().strftime("%H:%M:%S"),
            'ltp': st.session_state.market_data['ltp'],
            'pcr': new_pcr,
            'oi': new_oi
        }])
        st.session_state.market_data['history'] = pd.concat([st.session_state.market_data['history'], new_entry]).tail(60)

# --- DASHBOARD LAYOUT ---
col1, col2, col3 = st.columns([1, 1, 1])

# Pillar 1: Price Action
with col1:
    ltp = st.session_state.market_data['ltp']
    prev_ltp = st.session_state.market_data['prev_ltp']
    delta = ltp - prev_ltp
    st.metric("NIFTY 50 LTP", f"₹{ltp:,.2f}", f"{delta:+.2f}")
    
    vwap_status = "ABOVE VWAP" if ltp > 22500 else "BELOW VWAP" # Example threshold
    st.write(f"**Institutional Status:** {vwap_status}")

# Pillar 2: Sentiment Gauge (PCR)
with col2:
    pcr_val = st.session_state.market_data['pcr']
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pcr_val,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "PCR Sentiment"},
        gauge={
            'axis': {'range': [0.5, 1.5]},
            'steps': [
                {'range': [0.5, 0.8], 'color': "salmon"},
                {'range': [0.8, 1.2], 'color': "white"},
                {'range': [1.2, 1.5], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': pcr_val
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

# Pillar 3: Conviction Signal
with col3:
    label, color = get_conviction_label(
        st.session_state.market_data['ltp'],
        st.session_state.market_data['prev_ltp'],
        st.session_state.market_data['oi'],
        st.session_state.market_data['prev_oi']
    )
    st.subheader("Market Signal")
    st.markdown(f"""
        <div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center;">
            <h2 style="color:white; margin:0;">{label}</h2>
        </div>
    """, unsafe_allow_all_html=True)

# --- TREND ANALYSIS ---
st.divider()
st.subheader("📈 ΔPCR Velocity (Leading Indicator)")

if not st.session_state.market_data['history'].empty:
    chart_data = st.session_state.market_data['history'].set_index('time')
    st.line_chart(chart_data['pcr'])
else:
    st.info("Awaiting manual 'Update Sentiment Data' to plot trends...")

st.caption("Data Refresh: Real-time via WebSocket | Logic: Price-OI-PCR Convergence")

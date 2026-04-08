import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from upstox_client import ApiClient, Configuration, OptionsApi, MarketQuoteApi
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# --- 1. CONFIGURATION & THEME ---
st.set_page_config(page_title="Market Predictor Pro", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for Dark Mode Professional Look
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-metric-indicator="up"] { color: #00ff00 !important; }
    div[data-metric-indicator="down"] { color: #ff4b4b !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
def get_upstox_client():
    conf = Configuration()
    conf.access_token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    return ApiClient(conf)

@st.cache_data(ttl=60) 
def fetch_market_data(symbol="NSE_INDEX|Nifty 50"):
    client = get_upstox_client()
    
    # 1. Fetch Option Chain
    # We use keyword arguments (instrument_key, expiry_date) to avoid positional errors
    opt_api = OptionsApi(client)
    chain_res = opt_api.get_put_call_option_chain(
        instrument_key=symbol, 
        expiry_date='2026-04-09'
    ) 
    
    # 2. Fetch India VIX
    # We use keyword arguments (instrument_key, interval)
    quote_api = MarketQuoteApi(client)
    vix_res = quote_api.get_market_quote_ohlc(
        instrument_key="NSE_INDEX|India VIX", 
        interval="1d"
    )
    vix_price = vix_res.data["NSE_INDEX|India VIX"].last_price

    return chain_res.data, vix_price
    
# --- 3. THE ANALYSIS PILLARS ---
def process_pillars(data, vix):
    df = pd.DataFrame([vars(s) for s in data])
    spot = data[0].underlying_spot_price
    
    # Pillar 1: Filter ATM ± 3 Strikes
    df['diff'] = abs(df['strike_price'] - spot)
    atm_idx = df['diff'].idxmin()
    atm_df = df.iloc[max(0, atm_idx-3) : min(len(df), atm_idx+4)].copy()
    
    # Pillar 2: OI Buildup Calculation
    call_oi = atm_df['call_options'].apply(lambda x: x['market_data']['oi']).sum()
    put_oi = atm_df['put_options'].apply(lambda x: x['market_data']['oi']).sum()
    pcr = put_oi / call_oi if call_oi > 0 else 0
    
    # Pillar 3: VIX Context
    vix_status = "⚠️ HIGH VOLATILITY" if vix > 22 else "✅ STABLE"
    
    return spot, pcr, atm_df, vix_status

# --- 4. DASHBOARD UI ---
def main():
    # Auto-refresh every 30 seconds
    st_autorefresh(interval=30000, key="datarefresh")
    
    st.title("🎯 Market Predictor Pro | Live Analysis")
    st.caption(f"Last Sync: {datetime.now().strftime('%H:%M:%S')} (April 2026 Cycle)")

    try:
        raw_data, vix_price = fetch_market_data()
        spot, pcr, atm_df, vix_msg = process_pillars(raw_data, vix_price)

        # TOP ROW: METRICS
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("NIFTY 50", f"₹{spot}")
        m2.metric("PUT-CALL RATIO (PCR)", round(pcr, 2), delta="Bullish" if pcr > 1 else "Bearish")
        m3.metric("INDIA VIX", f"{vix_price}%", delta=vix_msg)
        
        # Current Signal Box
        signal = "BULLISH" if (pcr > 1.1 and vix_price < 25) else "BEARISH" if pcr < 0.8 else "NEUTRAL"
        st.info(f"**CURRENT SIGNAL:** {signal}")

        # MIDDLE ROW: CHARTS
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("ATM ±3 Option Chain Battle")
            # Prepare data for bar chart
            chart_df = pd.DataFrame({
                'Strike': atm_df['strike_price'],
                'Call OI': atm_df['call_options'].apply(lambda x: x['market_data']['oi']),
                'Put OI': atm_df['put_options'].apply(lambda x: x['market_data']['oi'])
            })
            fig = go.Figure(data=[
                go.Bar(name='Call OI', x=chart_df['Strike'], y=chart_df['Call OI'], marker_color='#ff4b4b'),
                go.Bar(name='Put OI', x=chart_df['Strike'], y=chart_df['Put OI'], marker_color='#00ff00')
            ])
            fig.update_layout(barmode='group', template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.subheader("Sentiment Gauge")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = pcr,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [None, 2]},
                    'bar': {'color': "white"},
                    'steps' : [
                        {'range': [0, 0.7], 'color': "red"},
                        {'range': [1.3, 2], 'color': "green"}]
                }
            ))
            fig_gauge.update_layout(template="plotly_dark")
            st.plotly_chart(fig_gauge, use_container_width=True)

    except Exception as e:
        st.error(f"Waiting for market data or API Token update... Error: {e}")

if __name__ == "__main__":
    main()

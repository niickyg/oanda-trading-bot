import streamlit as st
import pandas as pd
from .data import stream_bars, get_candles
from .strategy import generate_signal, compute_atr, sl_tp_levels


# Broker import for trading
from .broker import place_order, close_profitable_positions

# Allowed decimal precision per instrument
PRECISION = {
    "GBP_JPY": 2, "EUR_JPY": 2, "NZD_JPY": 2, "USD_JPY": 2,
    "GBP_USD": 5, "EUR_USD": 5, "AUD_USD": 5, "USD_CAD": 5, "USD_CHF": 5,
    "AUD_JPY": 2, "EUR_GBP": 5, "GBP_AUD": 5, "EUR_AUD": 5,
}


def round_price(instrument: str, price: float) -> str:
    prec = PRECISION.get(instrument, 5)
    return f"{price:.{prec}f}"


# Configuration
PAIRS = [
    "GBP_JPY", "GBP_AUD", "EUR_AUD", "NZD_JPY", "GBP_USD",
    "AUD_JPY", "AUD_USD", "EUR_JPY", "USD_JPY", "EUR_GBP",
]
BAR_SECONDS = 5

# Initialize session state
if 'stream' not in st.session_state:
    st.session_state.stream = stream_bars(PAIRS, seconds=BAR_SECONDS)
if 'history' not in st.session_state:
    st.session_state.history = {p: [] for p in PAIRS}
if 'signals' not in st.session_state:
    st.session_state.signals = {p: None for p in PAIRS}

st.title("OANDA High-Frequency Bot Dashboard")

# Controls
cols = st.sidebar
start = cols.button("Fetch Next Bar and Trade")
span_fast = cols.slider("Fast EMA Span", 1, 10, 3)
span_slow = cols.slider("Slow EMA Span", 5, 50, 8)
take_profit = cols.button("Close Profitable Positions")

# Fetch and process one bar
if start:
    bar = next(st.session_state.stream)
    for pair, price in bar.items():
        st.session_state.history[pair].append(price)
        closes = st.session_state.history[pair]
        sig = generate_signal(closes, fast=span_fast, slow=span_slow)
        st.session_state.signals[pair] = sig
        if sig:
            # Risk management
            candles = get_candles(symbol=pair, count=15)
            atr = compute_atr(candles, period=14) or 0.0005
            sl_raw, tp_raw = sl_tp_levels(price, sig, atr)
            sl = round_price(pair, sl_raw)
            tp = round_price(pair, tp_raw)
            # Place the order
            resp = place_order(
                instrument=pair,
                units=1000 if sig == "BUY" else -1000,
                stopLossOnFill={"price": sl},
                takeProfitOnFill={"price": tp}
            )
            order_id = resp["orderCreateTransaction"]["id"]
            # Report trade in the app
            st.sidebar.write(
                f"Traded {pair} {sig} @ {price:.5f}, SL={sl}, TP={tp}, "
                f"ID {order_id}"
            )

# Handle Close Profitable Positions button
if take_profit:
    results = close_profitable_positions()
    cols.write(f"Closed {len(results)} profitable positions.")

# Display latest prices and signals
st.subheader("Latest Prices & Signals")
status_df = pd.DataFrame(
    {
        "Price": {
            p: st.session_state.history[p][-1]
            if st.session_state.history[p] else None
            for p in PAIRS
        },
        "Signal": st.session_state.signals,
    }
)
st.table(status_df)


# Display historical price chart
st.subheader("Price History (Last 60 Bars)")
# Only show chart if data exists
hist_data = {
    p: st.session_state.history[p][-60:]
    for p in PAIRS
    if st.session_state.history[p]
}
if hist_data:
    hist_df = pd.DataFrame(hist_data)
    st.line_chart(hist_df)
else:
    st.write("No price history available yet. Click ‘Fetch Next Bar’ to begin.")

st.caption(f"Click 'Fetch Next Bar and Trade' to process the next {BAR_SECONDS}-second bar.")

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Stock Signal App", layout="wide")

# -----------------------------
# Clean fixed header
# -----------------------------
st.markdown(
    """
    <style>
    .fixed-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 18px 32px;
        font-size: 32px;
        font-weight: 700;
        color: #2f3342;
        border-bottom: 1px solid #e5e7eb;
        z-index: 999;
    }

    .main-content {
        margin-top: 90px;
    }
    </style>

    <div class="fixed-header">
        Stock Candlestick Chart
    </div>

    <div class="main-content">
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Inputs
# -----------------------------
col1, col2 = st.columns([2, 1])

with col1:
    symbol = st.text_input("Stock Symbol", "AAPL").upper()

with col2:
    period = st.selectbox(
        "Period",
        ["1mo", "3mo", "6mo", "1y", "5y", "max"],
        index=3,
    )

# -----------------------------
# Indicators
# -----------------------------
def sma(values: pd.Series, window: int):
    return values.rolling(window).mean()


def rsi(close: pd.Series, window: int = 14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def kagi_count(closes, threshold=50):
    closes = list(closes.dropna())
    if not closes:
        return 0

    count = 0
    last_key = closes[0]

    for price in closes[1:]:
        if abs(price - last_key) >= threshold:
            count += 1
            last_key = price

    return count


def signal_color(hint: str):
    if hint == "BUY":
        return "#1d4ed8", "#dbeafe", "#60a5fa"
    if hint == "SELL":
        return "#b91c1c", "#fee2e2", "#f87171"
    return "#374151", "#f3f4f6", "#d1d5db"


def fmt_num(value):
    if pd.isna(value):
        return "-"
    return f"{value:.2f}"


# -----------------------------
# Data load
# -----------------------------
@st.cache_data(ttl=900)
def load_stock(symbol: str, period: str):
    return yf.Ticker(symbol).history(period=period, interval="1d")


try:
    df = load_stock(symbol, period)
except Exception:
    st.error("Yahoo Finance is temporarily rate-limiting requests. Please try again later.")
    st.stop()

if df.empty:
    st.error("No stock data found.")
    st.stop()

# -----------------------------
# Indicator calculations
# -----------------------------
df["SMA20"] = sma(df["Close"], 20)
df["SMA50"] = sma(df["Close"], 50)
df["RSI14"] = rsi(df["Close"], 14)

last_close = float(df["Close"].iloc[-1])
last_sma20 = df["SMA20"].iloc[-1]
last_sma50 = df["SMA50"].iloc[-1]
last_rsi = df["RSI14"].iloc[-1]
kagi_moves = kagi_count(df["Close"], 50)

# -----------------------------
# Signal logic
# -----------------------------
hint = "HOLD"
confidence = "LOW"
reason = "Not enough data."

if pd.notna(last_sma20) and pd.notna(last_sma50) and pd.notna(last_rsi):
    score = 0
    reasons = []

    if last_sma20 > last_sma50:
        score += 1
        reasons.append("SMA20 above SMA50 (uptrend)")
    else:
        score -= 1
        reasons.append("SMA20 below SMA50 (downtrend)")

    if last_rsi < 30:
        score += 1
        reasons.append("RSI oversold")
    elif last_rsi > 70:
        score -= 1
        reasons.append("RSI overbought")
    else:
        reasons.append("RSI neutral")

    if score >= 2:
        hint = "BUY"
        confidence = "HIGH"
    elif score == 1:
        hint = "BUY"
        confidence = "MEDIUM"
    elif score == 0:
        hint = "HOLD"
        confidence = "MEDIUM"
    elif score == -1:
        hint = "SELL"
        confidence = "MEDIUM"
    else:
        hint = "SELL"
        confidence = "HIGH"

    reason = "; ".join(reasons)

text_color, box_color, border_color = signal_color(hint)

# -----------------------------
# Signal box
# -----------------------------
st.markdown(
    f"""
    <div style="
        padding: 12px;
        border-radius: 10px;
        border: 1px solid {border_color};
        background: {box_color};
        color: {text_color};
        margin-top: 12px;
        margin-bottom: 20px;
    ">
        <div><b>Hint:</b> {hint}</div>
        <div><b>Confidence:</b> {confidence}</div>
        <div><b>Reason:</b> {reason}</div>

        <div style="margin-top:8px;">
            <b>Close:</b> {fmt_num(last_close)} |
            <b>SMA20:</b> {fmt_num(last_sma20)} |
            <b>SMA50:</b> {fmt_num(last_sma50)} |
            <b>RSI14:</b> {fmt_num(last_rsi)} |
            <b>Kagi Moves (≥50):</b> {kagi_moves}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Buy/Sell crossover points
# -----------------------------
cross_up = (df["SMA20"] > df["SMA50"]) & (df["SMA20"].shift(1) <= df["SMA50"].shift(1))
cross_down = (df["SMA20"] < df["SMA50"]) & (df["SMA20"].shift(1) >= df["SMA50"].shift(1))

buy_points = df[cross_up]
sell_points = df[cross_down]

# -----------------------------
# Multi-panel chart
# -----------------------------
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.75, 0.25],
    vertical_spacing=0.05,
    specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
)

# Candlestick
fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Price",
    ),
    row=1,
    col=1,
    secondary_y=False,
)

# SMA20
fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["SMA20"],
        name="SMA20",
        line=dict(color="blue", width=2),
    ),
    row=1,
    col=1,
    secondary_y=False,
)

# SMA50
fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["SMA50"],
        name="SMA50",
        line=dict(color="red", width=2),
    ),
    row=1,
    col=1,
    secondary_y=False,
)

# Volume
fig.add_trace(
    go.Bar(
        x=df.index,
        y=df["Volume"],
        name="Volume",
        marker_color=[
            "#26a69a" if c >= o else "#ef5350"
            for o, c in zip(df["Open"], df["Close"])
        ],
        opacity=0.35,
    ),
    row=1,
    col=1,
    secondary_y=True,
)

# BUY markers
fig.add_trace(
    go.Scatter(
        x=buy_points.index,
        y=buy_points["Low"] * 0.98,
        mode="markers",
        marker=dict(color="blue", size=10, symbol="triangle-up"),
        name="BUY signal",
    ),
    row=1,
    col=1,
    secondary_y=False,
)

# SELL markers
fig.add_trace(
    go.Scatter(
        x=sell_points.index,
        y=sell_points["High"] * 1.02,
        mode="markers",
        marker=dict(color="red", size=10, symbol="triangle-down"),
        name="SELL signal",
    ),
    row=1,
    col=1,
    secondary_y=False,
)

# RSI
fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["RSI14"],
        name="RSI",
        line=dict(color="purple"),
    ),
    row=2,
    col=1,
)

fig.add_hline(y=70, row=2, col=1, line_dash="dash", line_color="#ef4444")
fig.add_hline(y=30, row=2, col=1, line_dash="dash", line_color="#10b981")

fig.update_layout(
    height=760,
    dragmode="pan",
    margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    hovermode="x unified",
)

fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=False)
fig.update_yaxes(title_text="Volume", row=1, col=1, secondary_y=True, showgrid=False)
fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])

fig.update_xaxes(rangeslider_visible=False)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"scrollZoom": True},
)

# Close the main content wrapper
st.markdown("</div>", unsafe_allow_html=True)
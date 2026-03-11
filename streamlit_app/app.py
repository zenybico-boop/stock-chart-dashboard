import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Stock Signal App", layout="wide")

# -----------------------------
# Clean page styling
# -----------------------------
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 3rem;
        padding-bottom: 1rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }

    .app-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #23324a;
        margin-bottom: 0.4rem;
    }

    .company-name {
        font-size: 1rem;
        font-weight: 600;
        color: #334155;
        margin-top: -4px;
        margin-bottom: 10px;
    }

    .hint-box {
        padding: 12px 14px;
        border-radius: 10px;
        margin-top: 8px;
        margin-bottom: 12px;
        font-size: 14px;
        line-height: 1.55;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label {
        font-size: 0.95rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-title">Stock Signal Chart</div>', unsafe_allow_html=True)

# -----------------------------
# Inputs
# -----------------------------
col1, col2 = st.columns([2.2, 1.1], gap="small")

with col1:
    symbol = st.text_input("Stock Symbol", "AAPL").strip().upper()

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
def load_stock_data(symbol: str, period: str):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval="1d")

    company_name = symbol
    try:
        info = ticker.info
        company_name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("displayName")
            or symbol
        )
    except Exception:
        company_name = symbol

    return hist, company_name


try:
    df, company_name = load_stock_data(symbol, period)
except Exception:
    st.error("Yahoo Finance is temporarily rate-limiting requests. Please try again later.")
    st.stop()

st.markdown(
    f'<div class="company-name">{symbol} — {company_name}</div>',
    unsafe_allow_html=True,
)

if df.empty:
    st.error("No stock data found.")
    st.stop()

# -----------------------------
# Calculations
# -----------------------------
df["SMA20"] = sma(df["Close"], 20)
df["SMA50"] = sma(df["Close"], 50)
df["RSI14"] = rsi(df["Close"], 14)

last_close = float(df["Close"].iloc[-1])
last_sma20 = df["SMA20"].iloc[-1]
last_sma50 = df["SMA50"].iloc[-1]
last_rsi = df["RSI14"].iloc[-1]
kagi_moves = kagi_count(df["Close"], 50)

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
# Hint box
# -----------------------------
st.markdown(
    f"""
    <div class="hint-box" style="
        border:1px solid {border_color};
        background:{box_color};
        color:{text_color};
    ">
        <b>Stock:</b> {company_name} ({symbol})<br>
        <b>Hint:</b> {hint}<br>
        <b>Confidence:</b> {confidence}<br>
        <b>Reason:</b> {reason}<br><br>
        <b>Close:</b> {fmt_num(last_close)} |
        <b>SMA20:</b> {fmt_num(last_sma20)} |
        <b>SMA50:</b> {fmt_num(last_sma50)} |
        <b>RSI14:</b> {fmt_num(last_rsi)} |
        <b>Kagi Moves (≥50):</b> {kagi_moves}
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Buy/Sell points
# -----------------------------
cross_up = (df["SMA20"] > df["SMA50"]) & (df["SMA20"].shift(1) <= df["SMA50"].shift(1))
cross_down = (df["SMA20"] < df["SMA50"]) & (df["SMA20"].shift(1) >= df["SMA50"].shift(1))

buy_points = df[cross_up]
sell_points = df[cross_down]

# -----------------------------
# Chart
# -----------------------------
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.73, 0.27],
    vertical_spacing=0.05,
    specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
)

fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=f"{company_name} Price",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
        increasing_fillcolor="rgba(38,166,154,0.35)",
        decreasing_fillcolor="rgba(239,83,80,0.35)",
    ),
    row=1,
    col=1,
    secondary_y=False,
)

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

fig.add_trace(
    go.Bar(
        x=df.index,
        y=df["Volume"],
        name="Volume",
        marker_color=[
            "rgba(38,166,154,0.35)" if c >= o else "rgba(239,83,80,0.35)"
            for o, c in zip(df["Open"], df["Close"])
        ],
    ),
    row=1,
    col=1,
    secondary_y=True,
)

if not buy_points.empty:
    fig.add_trace(
        go.Scatter(
            x=buy_points.index,
            y=buy_points["Low"] * 0.985,
            mode="markers",
            marker=dict(color="blue", size=7, symbol="triangle-up"),
            name="BUY signal",
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

if not sell_points.empty:
    fig.add_trace(
        go.Scatter(
            x=sell_points.index,
            y=sell_points["High"] * 1.015,
            mode="markers",
            marker=dict(color="red", size=7, symbol="triangle-down"),
            name="SELL signal",
        ),
        row=1,
        col=1,
        secondary_y=False,
    )

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["RSI14"],
        name="RSI",
        line=dict(color="purple", width=1.5),
    ),
    row=2,
    col=1,
)

fig.add_hline(y=70, row=2, col=1, line_dash="dash", line_color="rgba(239,68,68,0.7)", line_width=1)
fig.add_hline(y=30, row=2, col=1, line_dash="dash", line_color="rgba(16,185,129,0.7)", line_width=1)

fig.update_layout(
    height=600,
    dragmode="pan",
    margin=dict(l=10, r=10, t=6, b=6),
    hovermode="x unified",
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.01,
        xanchor="left",
        x=0,
        font=dict(size=11),
    ),
    font=dict(size=11),
)

fig.update_yaxes(
    title_text="Price",
    row=1,
    col=1,
    secondary_y=False,
    showgrid=True,
    gridcolor="rgba(148,163,184,0.18)",
    zeroline=False,
)

fig.update_yaxes(
    title_text="Volume",
    row=1,
    col=1,
    secondary_y=True,
    showgrid=False,
    zeroline=False,
)

fig.update_yaxes(
    title_text="RSI",
    row=2,
    col=1,
    range=[0, 100],
    showgrid=True,
    gridcolor="rgba(148,163,184,0.15)",
    zeroline=False,
)

fig.update_xaxes(
    rangeslider_visible=False,
    showgrid=False,
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displaylogo": False,
    },
)
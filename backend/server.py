from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf


def sma(values, window: int):
    out = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            window_slice = values[i + 1 - window:i + 1]
            out.append(sum(window_slice) / window)
    return out


def rsi(values, window: int = 14):
    if len(values) < window + 1:
        return [None] * len(values)

    rsis = [None] * len(values)
    gains = []
    losses = []

    for i in range(1, window + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window

    def calc_rsi(ag, al):
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    rsis[window] = calc_rsi(avg_gain, avg_loss)

    for i in range(window + 1, len(values)):
        change = values[i] - values[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        rsis[i] = calc_rsi(avg_gain, avg_loss)

    return rsis


def kagi_count(closes, threshold=50):
    if not closes:
        return 0

    count = 0
    last_key_price = closes[0]

    for price in closes[1:]:
        if abs(price - last_key_price) >= threshold:
            count += 1
            last_key_price = price

    return count


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/history")
def history(symbol: str = "AAPL", period: str = "1y", interval: str = "1d"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        return {
            "symbol": symbol.upper(),
            "data": [],
            "error": "No price data returned."
        }

    closes = [float(x) for x in df["Close"].tolist()]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    rsi14 = rsi(closes, 14)

    data = []
    for i, (idx, row) in enumerate(df.iterrows()):
        if row.isna().any():
            continue

        data.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]) if "Volume" in row else 0.0,
            "sma20": float(sma20[i]) if sma20[i] is not None else None,
            "sma50": float(sma50[i]) if sma50[i] is not None else None,
            "rsi14": float(rsi14[i]) if rsi14[i] is not None else None,
        })

    return {"symbol": symbol.upper(), "data": data}


@app.get("/signal")
def signal(symbol: str = "AAPL", period: str = "6mo", interval: str = "1d"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        return {
            "symbol": symbol.upper(),
            "hint": "NO DATA",
            "confidence": "LOW",
            "reason": "No price data returned.",
            "kagi_moves": 0,
        }

    closes = [float(x) for x in df["Close"].tolist()]
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    rsi14 = rsi(closes, 14)
    kagi_moves = kagi_count(closes, 50)

    last_close = closes[-1]
    last_sma20 = sma20[-1]
    last_sma50 = sma50[-1]
    last_rsi = rsi14[-1]

    if last_sma20 is None or last_sma50 is None or last_rsi is None:
        return {
            "symbol": symbol.upper(),
            "hint": "HOLD",
            "confidence": "LOW",
            "reason": "Not enough data for indicators yet.",
            "close": last_close,
            "kagi_moves": kagi_moves,
        }

    score = 0
    reasons = []

    if last_sma20 > last_sma50:
        score += 1
        reasons.append("SMA20 is above SMA50 (uptrend)")
    else:
        score -= 1
        reasons.append("SMA20 is below SMA50 (downtrend)")

    if last_rsi < 30:
        score += 1
        reasons.append("RSI is below 30 (oversold)")
    elif last_rsi > 70:
        score -= 1
        reasons.append("RSI is above 70 (overbought)")
    else:
        reasons.append("RSI is neutral")

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

    return {
        "symbol": symbol.upper(),
        "hint": hint,
        "confidence": confidence,
        "reason": "; ".join(reasons),
        "close": last_close,
        "sma20": last_sma20,
        "sma50": last_sma50,
        "rsi14": last_rsi,
        "score": score,
        "kagi_moves": kagi_moves,
    }
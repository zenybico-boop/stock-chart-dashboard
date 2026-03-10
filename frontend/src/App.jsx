import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";

export default function App() {
  const [symbol, setSymbol] = useState("AAPL");
  const [period, setPeriod] = useState("1y");
  const [hint, setHint] = useState(null);
  const [hoverInfo, setHoverInfo] = useState(null);
  const [error, setError] = useState("");

  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const sma20SeriesRef = useRef(null);
  const sma50SeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const pagePadding = 40;

  const apiUrl = useMemo(() => {
    return `http://localhost:8000/history?symbol=${encodeURIComponent(
      symbol
    )}&period=${encodeURIComponent(period)}&interval=1d`;
  }, [symbol, period]);

  function getHintColors(hintValue) {
    if (hintValue === "BUY") {
      return {
        background: "#dbeafe",
        border: "#60a5fa",
        text: "#1d4ed8",
      };
    }

    if (hintValue === "SELL") {
      return {
        background: "#fee2e2",
        border: "#f87171",
        text: "#b91c1c",
      };
    }

    return {
      background: "#f3f4f6",
      border: "#d1d5db",
      text: "#374151",
    };
  }

  const hintColors = getHintColors(hint?.hint);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 620,
      layout: {
        background: { color: "white" },
        textColor: "#222",
      },
      grid: {
        vertLines: { visible: true },
        horzLines: { visible: true },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: {
        borderVisible: false,
        rightBarStaysOnScroll: true,
        rightOffset: 5,
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries);

    const sma20Series = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      priceLineVisible: false,
    });

    const sma50Series = chart.addSeries(LineSeries, {
      color: "#dc2626",
      lineWidth: 2,
      priceLineVisible: false,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0.08,
      },
    });

    candleSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.08,
        bottom: 0.30,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    sma20SeriesRef.current = sma20Series;
    sma50SeriesRef.current = sma50Series;
    volumeSeriesRef.current = volumeSeries;

    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    });

    ro.observe(container);

    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData) {
        setHoverInfo(null);
        return;
      }

      const candle = param.seriesData.get(candleSeries);

      if (!candle) {
        setHoverInfo(null);
        return;
      }

      let dateText = "";

      if (typeof param.time === "object") {
        const year = param.time.year;
        const month = String(param.time.month).padStart(2, "0");
        const day = String(param.time.day).padStart(2, "0");
        dateText = `${year}-${month}-${day}`;
      } else {
        dateText = String(param.time);
      }

      const volume = param.seriesData.get(volumeSeries);

      setHoverInfo({
        date: dateText,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: volume?.value ?? null,
      });
    });

    loadAll();

    return () => {
      ro.disconnect();
      chart.remove();
    };

    // eslint-disable-next-line
  }, []);

  async function loadChartData() {
    try {
      setError("");

      const res = await fetch(apiUrl);
      const json = await res.json();

      if (!res.ok) {
        setError(json?.error || "Failed loading chart data");
        return;
      }

      const candles = json.data.map((d) => {
        const [y, m, day] = d.date.split("-").map(Number);

        return {
          time: { year: y, month: m, day },
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        };
      });

      const sma20 = json.data
        .filter((d) => d.sma20 !== null)
        .map((d) => {
          const [y, m, day] = d.date.split("-").map(Number);

          return {
            time: { year: y, month: m, day },
            value: d.sma20,
          };
        });

      const sma50 = json.data
        .filter((d) => d.sma50 !== null)
        .map((d) => {
          const [y, m, day] = d.date.split("-").map(Number);

          return {
            time: { year: y, month: m, day },
            value: d.sma50,
          };
        });

      const volumeData = json.data.map((d) => {
        const [y, m, day] = d.date.split("-").map(Number);

        return {
          time: { year: y, month: m, day },
          value: d.volume,
          color: d.close >= d.open ? "#26a69a" : "#ef5350",
        };
      });

      candleSeriesRef.current.setData(candles);
      sma20SeriesRef.current.setData(sma20);
      sma50SeriesRef.current.setData(sma50);
      volumeSeriesRef.current.setData(volumeData);

      chartRef.current.timeScale().fitContent();
    } catch {
      setError("Backend connection failed.");
    }
  }

  async function getHint() {
    try {
      const res = await fetch(
        `http://localhost:8000/signal?symbol=${symbol}&period=${period}`
      );

      const json = await res.json();
      setHint(json);
    } catch {
      setError("Signal API failed.");
    }
  }

  async function loadAll() {
    await loadChartData();
    await getHint();
  }

  useEffect(() => {
    loadAll();

    // eslint-disable-next-line
  }, [period]);

  function onSymbolKeyDown(e) {
    if (e.key === "Enter") {
      loadAll();
    }
  }

  return (
    <div style={{ maxWidth: 1200, margin: "24px auto", fontFamily: "system-ui" }}>
      <h2 style={{ paddingLeft: pagePadding }}>Stock Candlestick Chart</h2>

      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          marginBottom: 12,
          paddingLeft: pagePadding,
        }}
      >
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          onKeyDown={onSymbolKeyDown}
          style={{ padding: 10, width: 180 }}
        />

        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          style={{ padding: 10 }}
        >
          <option value="1mo">1M</option>
          <option value="3mo">3M</option>
          <option value="6mo">6M</option>
          <option value="1y">1Y</option>
          <option value="5y">5Y</option>
          <option value="max">MAX</option>
        </select>

        <button onClick={loadAll} style={{ padding: "10px 16px" }}>
          Load
        </button>

        <button onClick={getHint} style={{ padding: "10px 16px" }}>
          Get Hint
        </button>
      </div>

      <div style={{ paddingLeft: pagePadding, marginBottom: 10 }}>
        <b>SMA20</b>: blue line &nbsp;&nbsp;
        <b>SMA50</b>: red line &nbsp;&nbsp;
        <b>Volume</b>: green/red bars
      </div>

      {hint && (
        <div
          style={{
            marginLeft: pagePadding,
            marginRight: pagePadding,
            padding: 12,
            border: `1px solid ${hintColors.border}`,
            borderRadius: 10,
            backgroundColor: hintColors.background,
            color: hintColors.text,
            marginBottom: 12,
          }}
        >
          <div><b>Hint:</b> {hint.hint}</div>
          <div><b>Confidence:</b> {hint.confidence}</div>
          <div><b>Reason:</b> {hint.reason}</div>

          <div style={{ marginTop: 8 }}>
            <b>Close:</b> {Number(hint.close).toFixed(2)} |
            <b> SMA20:</b> {Number(hint.sma20).toFixed(2)} |
            <b> SMA50:</b> {Number(hint.sma50).toFixed(2)} |
            <b> RSI14:</b> {Number(hint.rsi14).toFixed(2)} |
            <b> Kagi Moves (≥50):</b> {hint.kagi_moves}
          </div>
        </div>
      )}

      {hoverInfo && (
        <div
          style={{
            marginLeft: pagePadding,
            marginRight: pagePadding,
            marginBottom: 12,
            padding: 10,
            background: "#f8fafc",
            border: "1px solid #ddd",
            borderRadius: 10,
          }}
        >
          <b>Date:</b> {hoverInfo.date} |
          <b> Open:</b> {hoverInfo.open.toFixed(2)} |
          <b> High:</b> {hoverInfo.high.toFixed(2)} |
          <b> Low:</b> {hoverInfo.low.toFixed(2)} |
          <b> Close:</b> {hoverInfo.close.toFixed(2)}
          {hoverInfo.volume !== null && (
            <>
              {" | "}
              <b>Volume:</b> {Number(hoverInfo.volume).toLocaleString()}
            </>
          )}
        </div>
      )}

      {error && (
        <div style={{ color: "red", paddingLeft: pagePadding }}>{error}</div>
      )}

      <div style={{ paddingLeft: pagePadding, paddingRight: pagePadding }}>
        <div style={{ position: "relative" }}>
          <div
            ref={containerRef}
            style={{
              width: "100%",
              height: 620,
              border: "1px solid #ddd",
              borderRadius: 12,
              overflow: "hidden",
            }}
          />

          <div
            style={{
              position: "absolute",
              left: 6,
              bottom: 6,
              width: 72,
              height: 42,
              backgroundColor: "white",
              borderRadius: 10,
              zIndex: 20,
              pointerEvents: "none",
            }}
          />
        </div>
      </div>
    </div>
  );
}
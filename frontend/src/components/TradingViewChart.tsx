import { useCallback, useEffect, useRef, useState, memo } from 'react';
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { MarketCandle } from '../types';
import { TrendingUp, RefreshCw } from 'lucide-react';

interface TradingViewChartProps {
  symbol: string;
  timeframe: string;
  accountRef?: number | null;
  /** Optional price levels to draw on chart */
  levels?: PriceLevel[];
}

export interface PriceLevel {
  price: number;
  label: string;
  color: string;
  style?: 'solid' | 'dashed' | 'dotted';
}

interface CandlePoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
}

function toEpochSeconds(value: string): number | null {
  const ts = new Date(value).getTime();
  if (!Number.isFinite(ts)) return null;
  return Math.floor(ts / 1000);
}

const LINE_STYLES: Record<string, number> = {
  solid: LineStyle.Solid,
  dashed: LineStyle.Dashed,
  dotted: LineStyle.Dotted,
};

function TradingViewChartInner({ symbol, timeframe, accountRef, levels = [] }: TradingViewChartProps) {
  const { token } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const levelSeriesRef = useRef<ISeriesApi<'Line'>[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [candleCount, setCandleCount] = useState(0);

  const fetchCandles = useCallback(async () => {
    if (!token) return [];
    try {
      setLoading(true);
      const result = (await api.listMarketCandles(token, {
        pair: symbol,
        timeframe,
        account_ref: accountRef,
        limit: 200,
      })) as { candles?: MarketCandle[] } | MarketCandle[];

      const candles: MarketCandle[] = Array.isArray(result) ? result : result?.candles ?? [];
      return candles;
    } catch (err) {
      console.warn('Chart candle fetch failed:', err);
      return [];
    } finally {
      setLoading(false);
    }
  }, [token, symbol, timeframe, accountRef]);

  // Create chart once
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#0e1014' },
        textColor: '#8a8f98',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(30, 34, 45, 0.5)' },
        horzLines: { color: 'rgba(30, 34, 45, 0.5)' },
      },
      crosshair: {
        horzLine: { color: '#4a90d9', labelBackgroundColor: '#4a90d9' },
        vertLine: { color: '#4a90d9', labelBackgroundColor: '#4a90d9' },
      },
      rightPriceScale: {
        borderColor: 'rgba(30, 34, 45, 0.8)',
      },
      timeScale: {
        borderColor: 'rgba(30, 34, 45, 0.8)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Load candles when symbol/timeframe changes
  useEffect(() => {
    void (async () => {
      const candles = await fetchCandles();
      if (!candleSeriesRef.current || !chartRef.current) return;

      const points: CandlePoint[] = [];
      const usedTimes = new Set<number>();

      for (const c of candles) {
        const rawTime = toEpochSeconds(c.time);
        if (rawTime === null) continue;
        let t = rawTime;
        while (usedTimes.has(t)) t += 1;
        usedTimes.add(t);
        points.push({
          time: t as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        });
      }

      points.sort((a, b) => Number(a.time) - Number(b.time));
      candleSeriesRef.current.setData(points);
      setCandleCount(points.length);
      if (points.length > 0) {
        setLastPrice(points[points.length - 1].close);
      }
      chartRef.current.timeScale().fitContent();
    })();
  }, [fetchCandles]);

  // Draw price levels
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove old level lines
    for (const series of levelSeriesRef.current) {
      try {
        chart.removeSeries(series);
      } catch {
        // ignore
      }
    }
    levelSeriesRef.current = [];

    if (!levels.length || !candleSeriesRef.current) return;

    // Get time range from candle data
    const timeScale = chart.timeScale();
    const range = timeScale.getVisibleLogicalRange();
    if (!range) return;

    for (const level of levels) {
      const series = chart.addSeries(LineSeries, {
        color: level.color,
        lineWidth: 1,
        lineStyle: LINE_STYLES[level.style ?? 'dashed'] ?? LineStyle.Dashed,
        title: level.label,
        crosshairMarkerVisible: false,
        lastValueVisible: true,
        priceLineVisible: false,
      });

      // Draw a horizontal line across the visible range
      const now = Math.floor(Date.now() / 1000) as UTCTimestamp;
      const past = (now - 86400 * 30) as UTCTimestamp;
      series.setData([
        { time: past, value: level.price },
        { time: now, value: level.price },
      ]);
      levelSeriesRef.current.push(series);
    }
  }, [levels]);

  return (
    <div className="hw-surface p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border">
        <TrendingUp className="w-3.5 h-3.5 text-accent" />
        <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">LIVE_CHART</span>
        <span className="text-[10px] text-text-dim">{symbol}</span>
        <span className="text-[10px] text-text-dim">|</span>
        <span className="text-[10px] text-text-dim">{timeframe}</span>
        {lastPrice !== null && (
          <>
            <span className="text-[10px] text-text-dim">|</span>
            <span className="text-[10px] font-mono text-green-400">{lastPrice.toFixed(5)}</span>
          </>
        )}
        <span className="text-[10px] text-text-dim ml-auto">{candleCount} bars</span>
        {loading && <RefreshCw className="w-3 h-3 text-text-dim animate-spin" />}
      </div>
      <div ref={containerRef} style={{ height: 450, width: '100%' }} />
    </div>
  );
}

export const TradingViewChart = memo(TradingViewChartInner);

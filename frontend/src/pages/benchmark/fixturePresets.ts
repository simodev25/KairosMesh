export const BENCHMARK_AGENTS = [
  'technical-analyst',
  'news-analyst',
  'market-context-analyst',
  'bullish-researcher',
  'bearish-researcher',
  'trader-agent',
  'risk-manager',
  'execution-manager',
] as const;

export type BenchmarkAgentName = (typeof BENCHMARK_AGENTS)[number];

export type FixturePresetId = 'eurusd-h1-bullish' | 'btcusd-h4-range' | 'gbpjpy-m15-bearish';

interface OhlcSeries {
  opens: number[];
  highs: number[];
  lows: number[];
  closes: number[];
}

interface MarketPresetDefinition {
  id: FixturePresetId;
  label: string;
  symbol: string;
  pair: string;
  timeframe: string;
  trend: 'bullish' | 'neutral' | 'bearish';
  bars: number;
  seedPrice: number;
  drift: number;
  volatility: number;
  precision: number;
  contextSummary: string;
}

const PRESET_DEFINITIONS: readonly MarketPresetDefinition[] = [
  {
    id: 'eurusd-h1-bullish',
    label: 'EURUSD H1 — Tendance haussière',
    symbol: 'EURUSD.PRO',
    pair: 'EURUSD',
    timeframe: 'H1',
    trend: 'bullish',
    bars: 72,
    seedPrice: 1.0802,
    drift: 0.00013,
    volatility: 0.00024,
    precision: 5,
    contextSummary: 'Contexte London/NY avec momentum haussier progressif.',
  },
  {
    id: 'btcusd-h4-range',
    label: 'BTCUSD H4 — Range / Consolidation',
    symbol: 'BTCUSD',
    pair: 'BTCUSD',
    timeframe: 'H4',
    trend: 'neutral',
    bars: 60,
    seedPrice: 68120,
    drift: 2.4,
    volatility: 220,
    precision: 2,
    contextSummary: 'Consolidation large entre résistances 69000 et supports 67000.',
  },
  {
    id: 'gbpjpy-m15-bearish',
    label: 'GBPJPY M15 — Tendance baissière',
    symbol: 'GBPJPY.PRO',
    pair: 'GBPJPY',
    timeframe: 'M15',
    trend: 'bearish',
    bars: 84,
    seedPrice: 192.48,
    drift: -0.0082,
    volatility: 0.041,
    precision: 3,
    contextSummary: 'Flux vendeur intraday avec sommets descendants et volatilité soutenue.',
  },
];

export const MARKET_PRESETS = PRESET_DEFINITIONS.map((preset) => ({
  id: preset.id,
  label: preset.label,
}));

export const DEFAULT_MARKET_PRESET_ID: FixturePresetId = 'eurusd-h1-bullish';

export const DEFAULT_FIXTURE_CONFIG: Record<string, unknown> = {
  llm_enabled: true,
};

type AgentContextFactory = (preset: MarketPresetDefinition) => Record<string, unknown>;

const AGENT_CONTEXT_FACTORIES: Record<BenchmarkAgentName, AgentContextFactory> = {
  'technical-analyst': (preset) => ({
    role: 'technical-analyst',
    focus: 'Structure de marché, EMA, RSI, MACD, ATR, niveaux clés',
    preferred_horizon: preset.timeframe,
    expected_output: 'Analyse technique structurée avec biais probabiliste',
  }),
  'news-analyst': (preset) => ({
    role: 'news-analyst',
    focus: 'Catalyseurs macro, calendrier économique, sentiment de flux',
    expected_output: 'Impact news court terme sur la paire et le momentum',
    risk_note: 'Ignorer les signaux contradictoires non confirmés',
  }),
  'market-context-analyst': (preset) => ({
    role: 'market-context-analyst',
    focus: 'Régime de marché, corrélations, session active',
    regime_hint: preset.trend,
    expected_output: 'Contexte multi-horizon et alignement des facteurs',
  }),
  'bullish-researcher': (preset) => ({
    role: 'bullish-researcher',
    debate_angle: 'Construire le meilleur scénario haussier défendable',
    confirmation_bias: preset.trend === 'bullish' ? 'favorable' : 'contrarian',
    expected_output: 'Thèse haussière argumentée avec invalidation claire',
  }),
  'bearish-researcher': (preset) => ({
    role: 'bearish-researcher',
    debate_angle: 'Construire le meilleur scénario baissier défendable',
    confirmation_bias: preset.trend === 'bearish' ? 'favorable' : 'contrarian',
    expected_output: 'Thèse baissière argumentée avec invalidation claire',
  }),
  'trader-agent': (preset) => ({
    role: 'trader-agent',
    focus: 'Synthèse cross-agent et décision trade/no-trade',
    decision_mode: 'balanced',
    execution_mode: 'simulation',
    expected_output: `Décision finale alignée ${preset.pair}/${preset.timeframe}`,
  }),
  'risk-manager': (preset) => ({
    role: 'risk-manager',
    focus: 'Validation du risque, sizing, invalidation, R:R',
    risk_limits: {
      max_risk_per_trade_pct: 1,
      min_reward_to_risk: 1.8,
      max_open_positions: 3,
    },
    expected_output: 'GO/NO-GO risque motivé',
  }),
  'execution-manager': (preset) => ({
    role: 'execution-manager',
    focus: 'Paramètres d\'exécution, qualité fill, slippage',
    execution_constraints: {
      venue: 'paper',
      max_slippage_bps: preset.pair === 'BTCUSD' ? 12 : 4,
      order_type_preference: 'limit',
    },
    expected_output: 'Plan d\'exécution concret et sécurisé',
  }),
};

function round(value: number, precision: number): number {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
}

function buildOhlcSeries(preset: MarketPresetDefinition): OhlcSeries {
  const opens: number[] = [];
  const highs: number[] = [];
  const lows: number[] = [];
  const closes: number[] = [];

  let previousClose = preset.seedPrice;

  for (let i = 0; i < preset.bars; i += 1) {
    const cycle = Math.sin((i + 1) / (preset.timeframe === 'M15' ? 4.5 : 6.2));
    const noise = Math.cos((i + 1) / 3.8) * (preset.volatility * 0.23);
    const driftComponent = preset.drift + (preset.trend === 'neutral' ? cycle * (preset.volatility * 0.12) : cycle * (preset.volatility * 0.05));
    const close = round(previousClose + driftComponent + noise, preset.precision);

    const open = round(
      previousClose + Math.sin((i + 1) / 2.7) * (preset.volatility * 0.08),
      preset.precision,
    );

    const baseRange = Math.abs(close - open) + preset.volatility * (0.4 + (Math.abs(cycle) * 0.6));
    const high = round(Math.max(open, close) + baseRange * 0.55, preset.precision);
    const low = round(Math.min(open, close) - baseRange * 0.45, preset.precision);

    opens.push(open);
    highs.push(high);
    lows.push(low);
    closes.push(close);

    previousClose = close;
  }

  return { opens, highs, lows, closes };
}

function computeEma(values: number[], period: number, precision: number): number {
  const alpha = 2 / (period + 1);
  let ema = values[0] ?? 0;
  for (let i = 1; i < values.length; i += 1) {
    ema = values[i] * alpha + ema * (1 - alpha);
  }
  return round(ema, precision);
}

function computeRsi(values: number[], period = 14): number {
  if (values.length <= period) return 50;

  let gains = 0;
  let losses = 0;
  for (let i = values.length - period; i < values.length; i += 1) {
    const prev = values[i - 1] ?? values[i];
    const delta = values[i] - prev;
    if (delta >= 0) gains += delta;
    else losses += Math.abs(delta);
  }

  if (losses === 0) return 70;
  const rs = gains / losses;
  return round(100 - 100 / (1 + rs), 1);
}

function computeAtr(ohlc: OhlcSeries, precision: number, period = 14): number {
  if (ohlc.closes.length < 2) return 0;
  const trueRanges: number[] = [];
  for (let i = 1; i < ohlc.closes.length; i += 1) {
    const high = ohlc.highs[i];
    const low = ohlc.lows[i];
    const prevClose = ohlc.closes[i - 1];
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    trueRanges.push(tr);
  }
  const slice = trueRanges.slice(-period);
  const average = slice.reduce((sum, value) => sum + value, 0) / slice.length;
  return round(average, Math.min(precision, 5));
}

function buildSnapshot(preset: MarketPresetDefinition, ohlc: OhlcSeries): Record<string, unknown> {
  const closes = ohlc.closes;
  const last = closes[closes.length - 1];
  const prev = closes[closes.length - 2] ?? last;
  const emaFast = computeEma(closes, 12, preset.precision);
  const emaSlow = computeEma(closes, 26, preset.precision);
  const rsi = computeRsi(closes, 14);
  const macdDiff = round(emaFast - emaSlow, Math.min(preset.precision, 5));
  const changePct = prev === 0 ? 0 : round(((last - prev) / prev) * 100, 2);

  return {
    pair: preset.pair,
    timeframe: preset.timeframe,
    last_price: round(last, preset.precision),
    change_pct: changePct,
    rsi,
    ema_fast: emaFast,
    ema_slow: emaSlow,
    macd_diff: macdDiff,
    atr: computeAtr(ohlc, preset.precision),
    trend: preset.trend,
  };
}

function getSpecializedAgentInputs(agentName: BenchmarkAgentName): Record<string, unknown> {
  switch (agentName) {
    case 'news-analyst':
      return {
        news_context: {
          articles: [
            {
              title: 'ECB holds rates steady at 4.25%',
              sentiment: 'neutral',
              impact: 'high',
              source: 'Reuters',
              published: '2026-05-11T10:00:00Z',
            },
            {
              title: 'US Non-Farm Payrolls beat expectations at 256K',
              sentiment: 'bullish_usd',
              impact: 'high',
              source: 'Bloomberg',
              published: '2026-05-11T08:30:00Z',
            },
            {
              title: 'EURUSD technical outlook remains bearish below 1.0900',
              sentiment: 'bearish',
              impact: 'medium',
              source: 'FXStreet',
              published: '2026-05-11T07:00:00Z',
            },
          ],
          macro_calendar: [
            {
              event: 'ECB Rate Decision',
              actual: '4.25%',
              forecast: '4.25%',
              previous: '4.25%',
              impact: 'high',
            },
            {
              event: 'US Non-Farm Payrolls',
              actual: '256K',
              forecast: '185K',
              previous: '216K',
              impact: 'high',
            },
          ],
        },
      };
    case 'risk-manager':
      return {
        portfolio_state: {
          open_positions: [
            {
              symbol: 'EURUSD',
              side: 'BUY',
              size: 0.1,
              entry_price: 1.082,
              current_price: 1.0835,
              unrealized_pnl_usd: 15.0,
            },
            {
              symbol: 'GBPJPY',
              side: 'SELL',
              size: 0.05,
              entry_price: 192.45,
              current_price: 192.1,
              unrealized_pnl_usd: 23.3,
            },
          ],
          total_exposure_pct: 2.5,
          daily_drawdown_pct: -0.3,
          max_allowed_risk_pct: 1.0,
          account_balance_usd: 10000,
        },
      };
    case 'execution-manager':
      return {
        execution_context: {
          spread_pips: 1.2,
          avg_spread_24h_pips: 1.5,
          liquidity: 'high',
          active_session: 'london_newyork_overlap',
          slippage_estimate_pips: 0.3,
          market_impact: 'low',
        },
      };
    case 'bullish-researcher':
    case 'bearish-researcher':
      return {
        phase1_results: {
          technical_summary: 'Bullish structural bias with EMA alignment. RSI at 55, not overbought. MACD positive crossover.',
          news_summary: 'Mixed macro environment. ECB on hold, USD strengthened on NFP beat.',
          market_context_summary: 'Trending regime, London-NY overlap, high liquidity.',
        },
      };
    case 'trader-agent':
      return {
        debate_results: {
          bullish_thesis: 'Strong technical setup with EMA alignment and MACD crossover. NFP data supports short-term USD weakness against EUR.',
          bearish_thesis: 'ECB hold signals no further easing, limiting EUR upside. Key resistance at 1.0900 not broken.',
          bullish_confidence: 0.65,
          bearish_confidence: 0.55,
        },
      };
    default:
      return {};
  }
}

export function buildFixtureInputs(agentName: BenchmarkAgentName, presetId: FixturePresetId): Record<string, unknown> {
  const preset = PRESET_DEFINITIONS.find((item) => item.id === presetId) ?? PRESET_DEFINITIONS[0];
  const ohlc = buildOhlcSeries(preset);
  const snapshot = buildSnapshot(preset, ohlc);
  const agentContext = AGENT_CONTEXT_FACTORIES[agentName](preset);

  const contextPayload = {
    pair: preset.pair,
    symbol: preset.symbol,
    timeframe: preset.timeframe,
    bars: preset.bars,
    trend: preset.trend,
    summary: preset.contextSummary,
    agent: agentContext,
  };

  return {
    symbol: preset.symbol,
    pair: preset.pair,
    timeframe: preset.timeframe,
    context: `Analysis context:\n${JSON.stringify(contextPayload, null, 2)}`,
    ohlc,
    snapshot,
    ...getSpecializedAgentInputs(agentName),
  };
}

export function formatFixtureInputs(agentName: BenchmarkAgentName, presetId: FixturePresetId): string {
  return JSON.stringify(buildFixtureInputs(agentName, presetId), null, 2);
}

export function formatFixtureConfig(): string {
  return JSON.stringify(DEFAULT_FIXTURE_CONFIG, null, 2);
}

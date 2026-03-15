export const FOREX_PAIRS = [
  'EURUSD.PRO',
  'GBPUSD.PRO',
  'USDJPY.PRO',
  'USDCHF.PRO',
  'AUDUSD.PRO',
  'USDCAD.PRO',
  'NZDUSD.PRO',
  'EURJPY.PRO',
  'GBPJPY.PRO',
  'EURGBP.PRO',
];

export const CRYPTO_PAIRS = [
  'ADAUSD',
  'AVAXUSD',
  'BCHUSD',
  'BNBUSD',
  'BTCUSD',
  'DOGEUSD',
  'DOTUSD',
  'ETHUSD',
  'LINKUSD',
  'LTCUSD',
  'MATICUSD',
  'SOLUSD',
  'UNIUSD',
];

export const TRADEABLE_PAIRS = [...FOREX_PAIRS, ...CRYPTO_PAIRS];

export const DEFAULT_PAIR = FOREX_PAIRS[0];

export const DEFAULT_TIMEFRAMES = ['M5', 'M15', 'H1', 'H4', 'D1'];

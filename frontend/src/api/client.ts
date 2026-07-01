const BASE = '';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json();
}

async function sendJson<T>(path: string, method: 'POST' | 'DELETE', body?: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  snapshot: () => fetchJson<import('./types').SnapshotResponse>('/api/v1/snapshot/latest'),
  systemHealth: () => fetchJson<import('./types').SystemHealthResponse>('/api/v1/system/health'),
  alerts: () => fetchJson<import('./types').AlertsResponse>('/api/v1/system/alerts'),
  strategyWatchlist: () => fetchJson<import('./types').StrategyWatchlistResponse>('/api/v1/strategy-watchlist'),
  intradayPreviewWatchlist: () => fetchJson<import('./types').IntradayPreviewWatchlistResponse>('/api/v1/preview/watchlist'),
  addStrategyWatch: (symbol: string) => sendJson<import('./types').StrategyWatchlistMutationResponse>(
    '/api/v1/strategy-watchlist',
    'POST',
    { symbol },
  ),
  removeStrategyWatch: (symbol: string) => sendJson<import('./types').StrategyWatchlistRemoveResponse>(
    `/api/v1/strategy-watchlist/${encodeURIComponent(symbol)}`,
    'DELETE',
  ),
  stockSnapshot: (symbol: string) => fetchJson<import('./types').StockSnapshotResponse>(`/api/v1/stocks/${symbol}/snapshot`),
  stockKline: (symbol: string) => fetchJson<import('./types').KlineResponse>(`/api/v1/stocks/${symbol}/kline`),
  stockIndicators: (symbol: string) => fetchJson<import('./types').IndicatorsResponse>(`/api/v1/stocks/${symbol}/indicators`),
  stockCapitalFlow: (symbol: string) => fetchJson<import('./types').CapitalFlowResponse>(`/api/v1/stocks/${symbol}/capital-flow`),
  stockFundamentals: (symbol: string) => fetchJson<import('./types').FundamentalsResponse>(`/api/v1/stocks/${symbol}/fundamentals`),
  stockDisclosures: (symbol: string) => fetchJson<import('./types').DisclosuresResponse>(`/api/v1/stocks/${symbol}/disclosures`),
  stockPriceVolumeAnalysis: (symbol: string) => fetchJson<import('./types').PriceVolumeAnalysisResponse>(`/api/v1/stocks/${symbol}/price-volume-analysis`),
  backtestLatest: () => fetchJson<import('./types').BacktestRunResponse>('/api/v1/backtests/runs/latest'),
  equityCurve: () => fetchJson<import('./types').EquityCurveResponse>('/api/v1/backtests/runs/latest/equity-curve'),
  trades: () => fetchJson<import('./types').TradesResponse>('/api/v1/backtests/runs/latest/trades'),
  tasks: () => fetchJson<import('./types').TaskRunsResponse>('/api/v1/tasks/runs'),
};

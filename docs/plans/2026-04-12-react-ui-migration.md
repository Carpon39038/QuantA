# React UI Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the vanilla HTML/CSS/JS frontend with a React + TypeScript + Tailwind + Recharts frontend matching the Gemini UI design, connected to the existing backend API.

**Architecture:** Vite dev server on port 4173 with a proxy rule forwarding `/api/*` to the backend on port 8765. The existing `scripts/run_frontend.py` is replaced — Vite handles both static file serving and API proxying. All data flows through typed API client + custom hooks.

**Tech Stack:** React 19, TypeScript, Vite 6, Tailwind CSS v4 (`@tailwindcss/vite`), Recharts 3, Lucide React, clsx + tailwind-merge.

**Design doc:** `docs/plans/2026-04-12-react-ui-migration-design.md`

---

### Task 1: Scaffold React project and update run script

**Files:**
- Delete: `frontend/src/app/index.html`, `frontend/src/app/main.css`, `frontend/src/app/main.js`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Modify: `scripts/run_frontend.py`

**Step 1: Delete old frontend files**

```bash
rm -rf frontend/src/app/index.html frontend/src/app/main.css frontend/src/app/main.js
```

**Step 2: Create `frontend/package.json`**

```json
{
  "name": "quanta-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --port=4173 --host=127.0.0.1",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "lucide-react": "^0.546.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "recharts": "^3.8.1",
    "tailwind-merge": "^3.5.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.1.14",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^4.1.14",
    "typescript": "~5.8.2",
    "vite": "^6.2.0"
  }
}
```

**Step 3: Create `frontend/vite.config.ts`**

```ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 4173,
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});
```

Key detail: Vite's proxy replaces the Python proxy in `run_frontend.py`. All `/api/*` requests are forwarded to the backend.

**Step 4: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "isolatedModules": true,
    "moduleDetection": "force",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

**Step 5: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>QuantA</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 6: Create `frontend/src/main.tsx`**

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

**Step 7: Create `frontend/src/index.css`**

```css
@import "tailwindcss";

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.25); }
.hide-scrollbar::-webkit-scrollbar { display: none; }
.hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
```

**Step 8: Create minimal `frontend/src/App.tsx` placeholder**

```tsx
export default function App() {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center text-white">
      <p>QuantA loading...</p>
    </div>
  );
}
```

**Step 9: Update `scripts/run_frontend.py`**

Replace the entire file with a script that runs `npm run dev` via subprocess:

```python
#!/usr/bin/env python3
"""Launch the Vite dev server for the React frontend."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.app_wiring.settings import load_settings
from backend.app.shared.telemetry.logging import configure_logging

LOGGER = logging.getLogger("quanta.frontend.dev_server")


def main() -> int:
    configure_logging()
    settings = load_settings()

    frontend_dir = ROOT / "frontend"
    if not (frontend_dir / "node_modules").exists():
        LOGGER.info("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)

    LOGGER.info("Starting Vite dev server on %s", settings.frontend_origin)
    try:
        subprocess.run(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
        )
    except KeyboardInterrupt:
        LOGGER.info("Stopping frontend dev server")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 10: Install dependencies and verify scaffold**

```bash
cd frontend && npm install
```

```bash
cd frontend && npx vite build
```

Expected: Build succeeds with no errors.

**Step 11: Commit**

```bash
git add -A frontend/ scripts/run_frontend.py
git commit -m "feat: scaffold React + Vite + Tailwind frontend, replace vanilla JS"
```

---

### Task 2: API client and TypeScript types

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/types.ts`

**Step 1: Create `frontend/src/api/types.ts`**

Define TypeScript interfaces for all API responses. Key types:

```ts
// --- Snapshot ---
export interface SnapshotResponse {
  api_contract_version: string;
  snapshot_id: string;
  raw_snapshot_id: string;
  status: string;
  generated_at: string;
  market_overview: MarketOverview;
  screener: ScreenerSection;
  backtest: BacktestSection;
  task_status: Record<string, TaskStatusEntry>;
  runtime: RuntimeInfo;
}

export interface MarketOverview {
  trade_date: string;
  summary: string;
  regime_label: string;
  indices: IndexData[];
  breadth: MarketBreadth;
  highlights: MarketHighlight[];
}

export interface IndexData {
  symbol: string;
  name: string;
  close: number;
  change_pct: number;
  is_up: boolean;
}

export interface MarketBreadth {
  up_count: number;
  down_count: number;
  flat_count: number;
  total: number;
}

export interface MarketHighlight {
  title: string;
  detail: string;
}

export interface ScreenerSection {
  strategy_name: string;
  as_of_date: string;
  signal_price_basis: string;
  top_candidates: ScreenerCandidate[];
}

export interface ScreenerCandidate {
  symbol: string;
  name: string;
  strategy_name: string;
  score: number;
  trend_score: number | null;
  price_volume_score: number | null;
  capital_score: number | null;
  fundamental_score: number | null;
  thesis: string;
  signals: SignalOrRisk[];
  risks: SignalOrRisk[];
}

export interface SignalOrRisk {
  code: string;
  label: string;
  direction?: string;
}

export interface BacktestSection {
  strategy_name: string;
  window: string;
  metrics: BacktestMetrics;
  notes: BacktestNote[];
}

export interface BacktestMetrics {
  cagr_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
}

export interface BacktestNote {
  text: string;
}

export interface TaskStatusEntry {
  status: string;
  last_run: string | null;
  next_window: string | null;
}

export interface RuntimeInfo {
  backend_origin: string;
  frontend_origin: string;
  [key: string]: unknown;
}

// --- System ---
export interface SystemHealthResponse {
  snapshot_id: string;
  status: string;
  alert_summary: AlertSummary;
  table_counts: Record<string, number>;
  task_count: number;
  alert_count: number;
}

export interface AlertSummary {
  window_count: number;
  error_count: number;
  warning_count: number;
  notice_count: number;
}

export interface AlertsResponse {
  items: AlertItem[];
  summary: AlertSummary;
}

export interface AlertItem {
  log_level: string;
  timestamp: string;
  source: string;
  message: string;
}

// --- Stock ---
export interface StockSnapshotResponse {
  symbol: string;
  display_name: string;
  exchange: string;
  board: string;
  industry: string;
  latest_daily_bar: DailyBar | null;
  latest_price_bar: PriceBar | null;
}

export interface DailyBar {
  trade_date: string;
  open_raw: number;
  high_raw: number;
  low_raw: number;
  close_raw: number;
  pre_close_raw: number;
  volume: number | null;
  amount: number | null;
  turnover_rate: number | null;
}

export interface PriceBar {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface KlineResponse {
  symbol: string;
  display_name: string;
  dataset: string;
  items: KlineItem[];
}

export interface KlineItem {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface IndicatorsResponse {
  symbol: string;
  display_name: string;
  latest_indicator: IndicatorData | null;
  latest_patterns: PatternSignal[];
}

export interface IndicatorData {
  trade_date: string;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  macd_dif: number | null;
  macd_dea: number | null;
  macd_hist: number | null;
  rsi6: number | null;
  volume_ratio: number | null;
}

export interface PatternSignal {
  signal_code: string;
  signal_type: string;
  direction: string;
  is_triggered: boolean;
  signal_score: number;
}

export interface CapitalFlowResponse {
  symbol: string;
  display_name: string;
  latest_capital_feature: CapitalFeature | null;
}

export interface CapitalFeature {
  trade_date: string;
  main_net_inflow: number | null;
  main_net_inflow_ratio: number | null;
  northbound_net_inflow: number | null;
  has_dragon_tiger: boolean;
}

export interface FundamentalsResponse {
  symbol: string;
  display_name: string;
  latest_fundamental_feature: FundamentalFeature | null;
}

export interface FundamentalFeature {
  trade_date: string;
  report_period: string | null;
  roe_dt: number | null;
  debt_to_assets: number | null;
  total_revenue: number | null;
  net_profit_attr_p: number | null;
  cash_to_profit: number | null;
  fundamental_score: number | null;
}

export interface DisclosuresResponse {
  symbol: string;
  display_name: string;
  items: DisclosureItem[];
}

export interface DisclosureItem {
  title: string;
  announcement_time: string | null;
  detail_url: string | null;
}

// --- Backtest detail ---
export interface BacktestRunResponse {
  backtest_id: string;
  strategy_name: string;
  metrics: BacktestMetrics;
  start_date: string;
  end_date: string;
  notes: BacktestNote[];
}

export interface EquityCurveResponse {
  equity_curve: EquityPoint[];
}

export interface EquityPoint {
  trade_date: string;
  equity: number;
  drawdown: number | null;
}

export interface TradesResponse {
  trades: TradeRecord[];
}

export interface TradeRecord {
  symbol: string;
  trade_date: string;
  side: string;
  trade_price: number;
  quantity: number;
  pnl: number | null;
}

// --- Tasks ---
export interface TaskRunsResponse {
  items: TaskRun[];
}

export interface TaskRun {
  task_id: string;
  task_name: string;
  biz_date: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}
```

**Step 2: Create `frontend/src/api/client.ts`**

```ts
const BASE = '';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  snapshot: () => fetchJson<import('./types').SnapshotResponse>('/api/v1/snapshot/latest'),
  systemHealth: () => fetchJson<import('./types').SystemHealthResponse>('/api/v1/system/health'),
  alerts: () => fetchJson<import('./types').AlertsResponse>('/api/v1/system/alerts'),
  stockSnapshot: (symbol: string) => fetchJson<import('./types').StockSnapshotResponse>(`/api/v1/stocks/${symbol}/snapshot`),
  stockKline: (symbol: string) => fetchJson<import('./types').KlineResponse>(`/api/v1/stocks/${symbol}/kline`),
  stockIndicators: (symbol: string) => fetchJson<import('./types').IndicatorsResponse>(`/api/v1/stocks/${symbol}/indicators`),
  stockCapitalFlow: (symbol: string) => fetchJson<import('./types').CapitalFlowResponse>(`/api/v1/stocks/${symbol}/capital-flow`),
  stockFundamentals: (symbol: string) => fetchJson<import('./types').FundamentalsResponse>(`/api/v1/stocks/${symbol}/fundamentals`),
  stockDisclosures: (symbol: string) => fetchJson<import('./types').DisclosuresResponse>(`/api/v1/stocks/${symbol}/disclosures`),
  backtestLatest: () => fetchJson<import('./types').BacktestRunResponse>('/api/v1/backtests/runs/latest'),
  equityCurve: () => fetchJson<import('./types').EquityCurveResponse>('/api/v1/backtests/runs/latest/equity-curve'),
  trades: () => fetchJson<import('./types').TradesResponse>('/api/v1/backtests/runs/latest/trades'),
  tasks: () => fetchJson<import('./types').TaskRunsResponse>('/api/v1/tasks/runs'),
};
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

**Step 4: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: add typed API client and response types"
```

---

### Task 3: Custom hooks

**Files:**
- Create: `frontend/src/hooks/useSnapshot.ts`
- Create: `frontend/src/hooks/useStock.ts`
- Create: `frontend/src/hooks/useBacktest.ts`
- Create: `frontend/src/hooks/useSystem.ts`
- Create: `frontend/src/lib/cn.ts`

**Step 1: Create `frontend/src/lib/cn.ts`** (utility used by all components)

```ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

**Step 2: Create `frontend/src/hooks/useSnapshot.ts`**

```ts
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { SnapshotResponse } from '../api/types';

export function useSnapshot() {
  const [data, setData] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.snapshot()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}
```

**Step 3: Create `frontend/src/hooks/useSystem.ts`**

```ts
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { AlertsResponse } from '../api/types';

export function useSystem() {
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.alerts()
      .then(setAlerts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { alerts, loading, error };
}
```

**Step 4: Create `frontend/src/hooks/useStock.ts`**

```ts
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type {
  StockSnapshotResponse, KlineResponse, IndicatorsResponse,
  CapitalFlowResponse, FundamentalsResponse, DisclosuresResponse,
} from '../api/types';

export interface StockData {
  snapshot: StockSnapshotResponse | null;
  kline: KlineResponse | null;
  indicators: IndicatorsResponse | null;
  capitalFlow: CapitalFlowResponse | null;
  fundamentals: FundamentalsResponse | null;
  disclosures: DisclosuresResponse | null;
}

export function useStock(symbol: string | null) {
  const [data, setData] = useState<StockData>({
    snapshot: null, kline: null, indicators: null,
    capitalFlow: null, fundamentals: null, disclosures: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);

    Promise.all([
      api.stockSnapshot(symbol),
      api.stockKline(symbol),
      api.stockIndicators(symbol),
      api.stockCapitalFlow(symbol),
      api.stockFundamentals(symbol),
      api.stockDisclosures(symbol),
    ])
      .then(([snapshot, kline, indicators, capitalFlow, fundamentals, disclosures]) => {
        setData({ snapshot, kline, indicators, capitalFlow, fundamentals, disclosures });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [symbol]);

  return { data, loading, error };
}
```

**Step 5: Create `frontend/src/hooks/useBacktest.ts`**

```ts
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { EquityCurveResponse, TradesResponse } from '../api/types';

export interface BacktestDetail {
  equityCurve: EquityCurveResponse | null;
  trades: TradesResponse | null;
}

export function useBacktest() {
  const [data, setData] = useState<BacktestDetail>({ equityCurve: null, trades: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.equityCurve(), api.trades()])
      .then(([equityCurve, trades]) => setData({ equityCurve, trades }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}
```

**Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

**Step 7: Commit**

```bash
git add frontend/src/hooks/ frontend/src/lib/
git commit -m "feat: add custom hooks for snapshot, stock, backtest, system data"
```

---

### Task 4: Small reusable UI components

**Files:**
- Create: `frontend/src/components/ui/StatusCard.tsx`
- Create: `frontend/src/components/ui/TaskCard.tsx`
- Create: `frontend/src/components/ui/AlertItem.tsx`
- Create: `frontend/src/components/ui/IndexCard.tsx`
- Create: `frontend/src/components/ui/StockListItem.tsx`
- Create: `frontend/src/components/ui/QuoteItem.tsx`
- Create: `frontend/src/components/ui/TechItem.tsx`

These are copied from the Gemini UI `App.tsx` subcomponents, with `any` types replaced by proper TypeScript interfaces.

**Step 1: Create each component file**

Each file is a self-contained component extracted from the Gemini `App.tsx` lines 334-448. Key changes:
- Replace `any` with proper prop types
- Use `cn()` from `../../lib/cn`
- Icons from `lucide-react`

`StatusCard.tsx`:
```tsx
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface StatusCardProps {
  title: string;
  value: string;
  subValue?: string;
  status: 'success' | 'warn' | 'error' | 'neutral';
  icon: ReactNode;
}

export function StatusCard({ title, value, subValue, status, icon }: StatusCardProps) {
  return (
    <div className="flex-1 min-w-[160px] bg-white/[0.03] rounded-lg p-3 border border-white/5 flex flex-col gap-2 hover:bg-white/[0.05] transition-colors cursor-default">
      <div className="flex items-center gap-1.5 text-xs text-white/50">
        {icon}
        <span>{title}</span>
      </div>
      <div className="flex items-end justify-between">
        <div className="text-sm font-medium text-white/90">{value}</div>
        {subValue && (
          <div className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', {
            'bg-emerald-500/10 text-emerald-400': status === 'success',
            'bg-amber-500/10 text-amber-400': status === 'warn',
            'bg-rose-500/10 text-rose-400': status === 'error',
            'bg-white/10 text-white/60': status === 'neutral',
          })}>
            {subValue}
          </div>
        )}
      </div>
    </div>
  );
}
```

`TaskCard.tsx`:
```tsx
import { CheckCircle2, Activity, Clock } from 'lucide-react';

interface TaskCardProps {
  title: string;
  time: string;
  status: 'success' | 'running' | 'neutral';
}

export function TaskCard({ title, time, status }: TaskCardProps) {
  return (
    <div className="flex items-center justify-between p-2 rounded-md hover:bg-white/5 transition-colors">
      <div className="flex items-center gap-2">
        {status === 'success' && <CheckCircle2 size={14} className="text-emerald-400" />}
        {status === 'running' && <Activity size={14} className="text-blue-400 animate-pulse" />}
        {status === 'neutral' && <Clock size={14} className="text-white/40" />}
        <span className="text-xs text-white/80">{title}</span>
      </div>
      <span className="text-[10px] text-white/40">{time}</span>
    </div>
  );
}
```

`AlertItem.tsx`:
```tsx
import { AlertTriangle, AlertCircle } from 'lucide-react';

interface AlertItemProps {
  message: string;
  time: string;
  type: 'warn' | 'error';
}

export function AlertItem({ message, time, type }: AlertItemProps) {
  return (
    <div className="flex items-start gap-2 p-2 rounded-md bg-white/[0.02] border border-white/5 mb-2">
      {type === 'warn' ? <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" /> : <AlertCircle size={14} className="text-rose-400 shrink-0 mt-0.5" />}
      <div className="flex-1">
        <div className="text-xs text-white/80">{message}</div>
        <div className="text-[10px] text-white/40 mt-0.5">{time}</div>
      </div>
    </div>
  );
}
```

`IndexCard.tsx`:
```tsx
import { cn } from '../../lib/cn';

interface IndexCardProps {
  name: string;
  price: string;
  change: string;
  isUp: boolean;
}

export function IndexCard({ name, price, change, isUp }: IndexCardProps) {
  return (
    <div className="bg-white/[0.03] rounded-lg p-2.5 border border-white/5">
      <div className="text-xs text-white/50 mb-1">{name}</div>
      <div className={cn('text-sm font-medium', isUp ? 'text-[#FF5F56]' : 'text-[#27C93F]')}>{price}</div>
      <div className={cn('text-[10px]', isUp ? 'text-[#FF5F56]/80' : 'text-[#27C93F]/80')}>{change}</div>
    </div>
  );
}
```

`StockListItem.tsx`:
```tsx
import { cn } from '../../lib/cn';

interface StockListItemProps {
  name: string;
  code: string;
  score: number;
  selected: boolean;
  onClick: () => void;
  trendScore?: number | null;
  priceVolumeScore?: number | null;
  capitalScore?: number | null;
}

export function StockListItem({ name, code, score, selected, onClick, trendScore, priceVolumeScore, capitalScore }: StockListItemProps) {
  return (
    <div onClick={onClick} className={cn('p-2.5 rounded-lg cursor-pointer transition-all border', selected ? 'bg-blue-500/10 border-blue-500/30' : 'bg-transparent border-transparent hover:bg-white/5')}>
      <div className="flex justify-between items-center mb-1.5">
        <div className="flex items-center gap-2">
          <span className={cn('font-medium text-sm', selected ? 'text-blue-400' : 'text-white/90')}>{name}</span>
          <span className="text-[10px] text-white/40">{code}</span>
        </div>
        <div className="text-sm font-medium text-[#FF5F56]">{score}</div>
      </div>
      <div className="flex justify-between items-center">
        <div className="flex gap-2 text-[10px] text-white/40">
          <span>趋势 {trendScore ?? '--'}</span>
          <span>量价 {priceVolumeScore ?? '--'}</span>
          <span>资金 {capitalScore ?? '--'}</span>
        </div>
      </div>
    </div>
  );
}
```

`QuoteItem.tsx`:
```tsx
import { cn } from '../../lib/cn';

interface QuoteItemProps {
  label: string;
  value: string;
  highlight?: string;
}

export function QuoteItem({ label, value, highlight }: QuoteItemProps) {
  return (
    <div>
      <div className="text-[10px] text-white/40 mb-1">{label}</div>
      <div className={cn('text-lg font-medium', highlight || 'text-white/90')}>{value}</div>
    </div>
  );
}
```

`TechItem.tsx`:
```tsx
import { cn } from '../../lib/cn';

interface TechItemProps {
  label: string;
  value: string;
  isUp?: boolean | null;
}

export function TechItem({ label, value, isUp }: TechItemProps) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-white/50">{label}</span>
      <span className={cn('font-medium', isUp === true ? 'text-[#FF5F56]' : isUp === false ? 'text-[#27C93F]' : 'text-white/90')}>{value}</span>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat: add small reusable UI components"
```

---

### Task 5: StatusStrip and TaskSidebar panels

**Files:**
- Create: `frontend/src/components/StatusStrip.tsx`
- Create: `frontend/src/components/TaskSidebar.tsx`

**Step 1: Create `StatusStrip.tsx`**

Maps snapshot + system health data to the 6 status cards. Pulls data from the snapshot response:

- Card 1 "发布快照": `snapshot_id`, status from `status` field
- Card 2 "研究池": universe count from `runtime.source_symbol_count`
- Card 3 "补充校验": from `shadow_validation` in snapshot
- Card 4 "告警": from alert_summary (error_count + warning_count)
- Card 5 "选股运行": from `screener` section (strategy_name + candidate count)
- Card 6 "回测窗口": from `backtest.window`

Uses icons: `Database, Filter, ShieldAlert, Bell, PlayCircle, Calendar` from lucide-react.

**Step 2: Create `TaskSidebar.tsx`**

Maps `task_status` from snapshot + alerts from `/api/v1/system/alerts`:

- Task list: maps `task_status` entries to `TaskCard` components with status icons
- Alert section: maps `alerts.items` to `AlertItem` components, filtering for WARNING/ERROR

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

**Step 4: Commit**

```bash
git add frontend/src/components/StatusStrip.tsx frontend/src/components/TaskSidebar.tsx
git commit -m "feat: add StatusStrip and TaskSidebar panels"
```

---

### Task 6: MarketPanel and WatchlistPanel (center column)

**Files:**
- Create: `frontend/src/components/MarketPanel.tsx`
- Create: `frontend/src/components/WatchlistPanel.tsx`

**Step 1: Create `MarketPanel.tsx`**

Maps `market_overview` from snapshot:

- **Index grid**: 2x2 grid of `IndexCard` from `indices[]` array
- **Market breadth**: horizontal bar (green/gray/red widths based on `up_count`, `flat_count`, `down_count`)
- **Daily highlights**: list from `highlights[]` with summary text

**Step 2: Create `WatchlistPanel.tsx`**

Maps `screener` section from snapshot:

- **Strategy header**: strategy name + candidate count + as_of_date
- **Stock list**: maps `top_candidates[]` to `StockListItem` with score and sub-scores
- **Click handler**: calls `onSelectStock(symbol)` prop to notify parent

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

**Step 4: Commit**

```bash
git add frontend/src/components/MarketPanel.tsx frontend/src/components/WatchlistPanel.tsx
git commit -m "feat: add MarketPanel and WatchlistPanel"
```

---

### Task 7: StockDetail panel (right column top)

**Files:**
- Create: `frontend/src/components/StockDetail.tsx`

**Step 1: Create `StockDetail.tsx`**

This is the largest component. Maps data from `useStock` hook:

- **Stock header**: name, symbol, exchange badge, industry tags, price, change
  - Price from `latest_daily_bar.close_raw`
  - Change computed from `(close_raw - pre_close_raw) / pre_close_raw * 100`
- **Quote grid (4 cols)**: `QuoteItem` for 昨收, 候选得分, 财务得分, 形态信号
- **Price chart**: `AreaChart` from Recharts using `kline.items[]` (trade_date + close)
- **Technical indicators**: `TechItem` for MA5, MACD, RSI6, 量比 from `indicators.latest_indicator`
- **Pattern signals**: from `indicators.latest_patterns`
- **Capital flow**: `TechItem` for 主力净流入, 北向资金, 龙虎榜 from `capitalFlow.latest_capital_feature`
- **Fundamentals**: `TechItem` for ROE, 资产负债率, 现利比, 营业收入 from `fundamentals.latest_fundamental_feature`
- **Disclosures**: list of disclosure links from `disclosures.items[]`

Recharts AreaChart config (from Gemini):
```tsx
<ResponsiveContainer width="100%" height="100%">
  <AreaChart data={chartData}>
    <defs>
      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
      </linearGradient>
    </defs>
    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
    <XAxis dataKey="date" stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} />
    <YAxis domain={['dataMin - 10', 'dataMax + 10']} stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} orientation="right" />
    <Tooltip contentStyle={{ backgroundColor: '#2D2D2D', borderColor: '#ffffff10', borderRadius: '8px', fontSize: '12px' }} />
    <Area type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
  </AreaChart>
</ResponsiveContainer>
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/StockDetail.tsx
git commit -m "feat: add StockDetail panel with chart, indicators, fundamentals"
```

---

### Task 8: BacktestPanel (right column bottom)

**Files:**
- Create: `frontend/src/components/BacktestPanel.tsx`

**Step 1: Create `BacktestPanel.tsx`**

Maps data from `useBacktest` hook + snapshot `backtest` section:

- **Metrics grid (2x2)**: `QuoteItem` for 年化收益, 最大回撤, 胜率, 利润因子 from `backtest.metrics`
- **Equity curve**: `LineChart` from Recharts using `equityCurve.equity_curve[]` (trade_date + equity)
- **Trade table**: HTML table from `trades.trades[]` with columns: 日期, 方向, 标的, 价格, 数量, 盈亏
- **Notes**: from `backtest.notes[]`

Recharts LineChart config (from Gemini):
```tsx
<ResponsiveContainer width="100%" height="100%">
  <LineChart data={curveData}>
    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
    <XAxis dataKey="date" stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
    <YAxis domain={['auto', 'auto']} stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} orientation="right" />
    <Tooltip contentStyle={{ backgroundColor: '#2D2D2D', borderColor: '#ffffff10', borderRadius: '8px', fontSize: '12px' }} />
    <Line type="monotone" dataKey="equity" stroke="#FF5F56" strokeWidth={2} dot={false} />
  </LineChart>
</ResponsiveContainer>
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/src/components/BacktestPanel.tsx
git commit -m "feat: add BacktestPanel with equity curve and trade table"
```

---

### Task 9: App.tsx — wire everything together

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Rewrite `App.tsx` to wire all components**

The App component:
1. Calls `useSnapshot()` for the main data
2. Calls `useSystem()` for alerts
3. Calls `useBacktest()` for equity curve + trades
4. Manages `selectedStock` state (default: first screener candidate)
5. Calls `useStock(selectedStock)` for the focused stock detail
6. Renders the full layout:

```
<div className="min-h-screen bg-black p-4 md:p-8 text-sm font-sans text-white/90">
  <div className="w-full max-w-[1600px] mx-auto h-[90vh] bg-[#1C1C1E] rounded-xl shadow-2xl border border-white/10 flex flex-col overflow-hidden">
    {/* Status Strip */}
    <StatusStrip snapshot={snapshot} health={health} />
    {/* Main Content */}
    <div className="flex flex-1 overflow-hidden">
      <TaskSidebar taskStatus={snapshot.task_status} alerts={alerts} />
      <div className="w-[360px] border-r border-white/10 flex flex-col shrink-0 bg-[#1C1C1E]">
        <MarketPanel market={snapshot.market_overview} />
        <WatchlistPanel screener={snapshot.screener} selectedStock={selectedStock} onSelectStock={setSelectedStock} />
      </div>
      <div className="flex-1 flex flex-col overflow-hidden bg-[#1C1C1E]">
        <StockDetail stockData={stockData} selectedSymbol={selectedStock} />
        <BacktestPanel backtest={snapshot.backtest} backtestDetail={backtestDetail} />
      </div>
    </div>
  </div>
</div>
```

**Step 2: Verify build**

```bash
cd frontend && npx vite build
```

Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire all panels together in App.tsx"
```

---

### Task 10: End-to-end verification

**Step 1: Start backend**

```bash
cd /Users/guzhangqi/web_ws/QuantA && python scripts/run_backend.py
```

**Step 2: Start frontend**

```bash
cd /Users/guzhangqi/web_ws/QuantA/frontend && npm run dev
```

**Step 3: Verify in browser**

Open `http://127.0.0.1:4173` and verify:
- Status strip shows 6 cards with real data
- Left sidebar shows task pipeline + alerts
- Center shows market indices, breadth, highlights
- Watchlist shows screener candidates with scores
- Clicking a stock loads its detail (chart, indicators, capital, fundamentals, disclosures)
- Backtest section shows metrics, equity curve, trade table
- Dark theme renders correctly
- No console errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete React UI migration with real API integration"
```

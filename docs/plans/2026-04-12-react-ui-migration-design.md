# React UI Migration Design

## Goal

Replace the vanilla HTML/CSS/JS frontend with a React + TypeScript + Tailwind + Recharts frontend matching the Gemini UI design, fully connected to the existing backend API.

## Decisions

- **Tech stack**: React 19 + TypeScript + Vite + Tailwind CSS v4 + Recharts + Lucide React icons
- **Location**: Replace `frontend/` directory entirely
- **No macOS title bar**: Top area is a simple status strip
- **Color scheme**: Deep black theme from Gemini UI (`#1C1C1E` / `#28282B` / `#2D2D2D`)
- **Red up / green down**: Chinese A-share convention (red=#FF5F56 for up, green=#27C93F for down)
- **Real API data**: No mocks, connect directly to `/api/v1/*` endpoints

## Layout Structure

```
+------------------------------------------------------+
|  Status Strip (6 status cards)                        |
+----------+-------------+------------------------------+
|  Left    |  Center     |  Right                       |
|  Sidebar |  Column     |  Column                      |
|  (task   |  (market +  |  (stock detail + backtest)   |
|  status  |  watchlist) |                              |
|  +       |             |                              |
|  alerts) |             |                              |
+----------+-------------+------------------------------+
```

- **Status Strip**: Horizontal scrollable row of 6 status cards (snapshot, universe, validation, alerts, screener run, backtest window)
- **Left Sidebar (w-64)**: Task pipeline status list + recent alerts
- **Center Column (w-[360px])**: Top 40% market overview (indices + breadth + highlights), bottom 60% watchlist/screener candidates
- **Right Column (flex-1)**: Top 65% stock detail (header + quote grid + chart + indicators + capital + fundamentals + disclosures), bottom 35% backtest summary (metrics + equity curve + trade table)

## Component Tree

```
App
├── StatusStrip
│   └── StatusCard x6
├── TaskSidebar
│   ├── TaskCard x N
│   └── AlertItem x N
├── MarketPanel
│   ├── IndexCard x4
│   ├── MarketBreadth
│   └── DailyHighlights
├── WatchlistPanel
│   ├── StrategyHeader
│   └── StockListItem x N
├── StockDetail
│   ├── StockHeader
│   ├── QuoteGrid (QuoteItem x4)
│   ├── PriceChart (AreaChart from Recharts)
│   ├── IndicatorPanel (TechItem x N)
│   ├── CapitalPanel (TechItem x N)
│   ├── FundamentalsPanel (TechItem x N)
│   └── DisclosuresPanel
└── BacktestPanel
    ├── MetricsGrid (QuoteItem x4)
    ├── EquityCurve (LineChart from Recharts)
    └── TradeTable
```

## Data Flow

1. App mounts -> `GET /api/v1/snapshot/latest` -> populates status strip, market overview, watchlist, task status, backtest summary
2. User clicks a stock in watchlist -> `GET /api/v1/stocks/{symbol}/snapshot` + `/kline` + `/indicators` + `/capital-flow` + `/fundamentals` + `/disclosures` -> populates stock detail panel
3. Alerts come from `GET /api/v1/system/alerts`
4. Backtest equity curve and trades from `GET /api/v1/backtests/runs/latest/equity-curve` and `/trades`

## API Client

Simple fetch wrapper with:
- Configurable base URL (defaults to current origin)
- JSON parsing
- Error handling (maps 4xx/5xx to typed errors)
- TypeScript response types generated from actual API shapes

## File Structure

```
frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── api/
│   │   ├── client.ts
│   │   └── types.ts
│   ├── hooks/
│   │   ├── useSnapshot.ts
│   │   ├── useStock.ts
│   │   ├── useBacktest.ts
│   │   └── useSystem.ts
│   └── components/
│       ├── StatusStrip.tsx
│       ├── TaskSidebar.tsx
│       ├── MarketPanel.tsx
│       ├── WatchlistPanel.tsx
│       ├── StockDetail.tsx
│       ├── BacktestPanel.tsx
│       └── ui/
│           ├── IndexCard.tsx
│           ├── StockListItem.tsx
│           ├── QuoteItem.tsx
│           └── TechItem.tsx
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.ts
```

## Styling Approach

- Tailwind CSS v4 with `@import "tailwindcss"` in index.css
- Custom scrollbar styles (thin, semi-transparent)
- `cn()` utility (clsx + tailwind-merge) for conditional classes
- Dark theme colors defined inline via Tailwind classes (no CSS variables needed)
- Responsive: fixed-width sidebars, flexible right column

## Key API Mappings

| UI Element | API Endpoint | Field Mapping |
|------------|-------------|---------------|
| Status strip - snapshot | `/snapshot/latest` | `snapshot_id`, `status` |
| Status strip - alerts | `/system/health` | `alert_summary` |
| Status strip - screener | `/snapshot/latest` | `screener` section |
| Status strip - backtest | `/snapshot/latest` | `backtest.window` |
| Left sidebar - tasks | `/snapshot/latest` | `task_status` |
| Left sidebar - alerts | `/system/alerts` | `items[]` |
| Market indices | `/snapshot/latest` | `market_overview.indices[]` |
| Market breadth | `/snapshot/latest` | `market_overview.breadth` |
| Watchlist | `/snapshot/latest` | `screener.top_candidates[]` |
| Stock detail header | `/stocks/{sym}/snapshot` | `display_name`, `latest_daily_bar` |
| Price chart | `/stocks/{sym}/kline` | `items[].trade_date, close` |
| Indicators | `/stocks/{sym}/indicators` | `latest_indicator`, `latest_patterns` |
| Capital flow | `/stocks/{sym}/capital-flow` | `latest_capital_feature` |
| Fundamentals | `/stocks/{sym}/fundamentals` | `latest_fundamental_feature` |
| Disclosures | `/stocks/{sym}/disclosures` | `items[]` |
| Backtest metrics | `/snapshot/latest` | `backtest.metrics` |
| Equity curve | `/backtests/runs/latest/equity-curve` | `equity_curve[]` |
| Trade table | `/backtests/runs/latest/trades` | `trades[]` |

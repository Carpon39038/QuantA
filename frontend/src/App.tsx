import { useState, useEffect } from 'react';
import { useSnapshot } from './hooks/useSnapshot';
import { useSystem } from './hooks/useSystem';
import { useStock } from './hooks/useStock';
import { useBacktest } from './hooks/useBacktest';
import { StatusStrip } from './components/StatusStrip';
import { TaskSidebar } from './components/TaskSidebar';
import { MarketPanel } from './components/MarketPanel';
import { WatchlistPanel } from './components/WatchlistPanel';
import { StockDetail } from './components/StockDetail';
import { BacktestPanel } from './components/BacktestPanel';

export default function App() {
  const { data: snapshot, loading: snapshotLoading, error: snapshotError } = useSnapshot();
  const { alerts, loading: alertsLoading } = useSystem();
  const { data: backtestDetail, loading: backtestLoading, error: backtestError } = useBacktest();

  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const { data: stockData, loading: stockLoading, error: stockError } = useStock(selectedStock);

  // Default to first screener candidate
  useEffect(() => {
    if (!selectedStock && snapshot?.screener?.top_candidates?.length) {
      setSelectedStock(snapshot.screener.top_candidates[0].symbol);
    }
  }, [snapshot, selectedStock]);

  // Loading / error state
  if (snapshotLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-white/50 text-sm">
        加载快照数据...
      </div>
    );
  }

  if (snapshotError) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-rose-400 text-sm">
        加载失败: {snapshotError}
      </div>
    );
  }

  if (!snapshot) return null;

  return (
    <div className="min-h-screen bg-black p-4 md:p-8 text-sm font-sans text-white/90">
      <div className="w-full max-w-[1600px] mx-auto h-[90vh] bg-[#1C1C1E] rounded-xl shadow-2xl border border-white/10 flex flex-col overflow-hidden">
        {/* Status Strip */}
        <StatusStrip snapshot={snapshot} health={null} />

        {/* Main Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar: Tasks + Alerts */}
          <TaskSidebar snapshot={snapshot} alerts={alertsLoading ? null : alerts} />

          {/* Center Column: Market + Watchlist */}
          <div className="w-[360px] border-r border-white/10 flex flex-col shrink-0 bg-[#1C1C1E]">
            <MarketPanel market={snapshot.market_overview} />
            <WatchlistPanel
              screener={snapshot.screener}
              selectedStock={selectedStock}
              onSelectStock={setSelectedStock}
            />
          </div>

          {/* Right Column: Stock Detail + Backtest */}
          <div className="flex-1 flex flex-col overflow-hidden bg-[#1C1C1E]">
            <StockDetail
              stockData={stockData}
              selectedSymbol={selectedStock}
              loading={stockLoading}
              error={stockError}
            />
            <BacktestPanel
              backtest={snapshot.backtest}
              backtestDetail={backtestDetail}
              loading={backtestLoading}
              error={backtestError}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

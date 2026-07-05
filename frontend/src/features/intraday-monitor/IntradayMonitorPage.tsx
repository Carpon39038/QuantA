import type {
  IntradayPreviewItem,
  IntradayPreviewSourceStatus,
  ScreenerSection,
  SnapshotResponse,
  StrategyWatchlistItem,
} from '../../api/types';
import type { StockData } from '../../hooks/useStock';
import { SnapshotMetaBar } from '../../app/components/SnapshotMetaBar';
import { MarketPanel } from '../market-overview/MarketPanel';
import { StockDetail } from '../stock-detail/StockDetail';
import { WatchlistPanel } from './WatchlistPanel';

interface IntradayMonitorPageProps {
  snapshot: SnapshotResponse;
  screener: ScreenerSection;
  monitorItems: StrategyWatchlistItem[];
  selectedStock: string | null;
  stockData: StockData;
  stockLoading: boolean;
  stockError: string | null;
  selectedStockIsMonitored: boolean;
  selectedMonitorItem: StrategyWatchlistItem | null;
  selectedIntradayItem: IntradayPreviewItem | null;
  strategyWatchLoading: boolean;
  strategyWatchMutating: boolean;
  strategyWatchError: string | null;
  intradayItemsBySymbol: Map<string, IntradayPreviewItem>;
  intradaySourceStatus: IntradayPreviewSourceStatus | null;
  intradayPreviewLoading: boolean;
  intradayPreviewError: string | null;
  onSelectStock: (symbol: string) => void;
  onAddMonitor: (symbol: string) => Promise<void>;
  onRemoveMonitor: (symbol: string) => Promise<void>;
  onToggleSelectedMonitor: () => Promise<void>;
}

export function IntradayMonitorPage({
  snapshot,
  screener,
  monitorItems,
  selectedStock,
  stockData,
  stockLoading,
  stockError,
  selectedStockIsMonitored,
  selectedMonitorItem,
  selectedIntradayItem,
  strategyWatchLoading,
  strategyWatchMutating,
  strategyWatchError,
  intradayItemsBySymbol,
  intradaySourceStatus,
  intradayPreviewLoading,
  intradayPreviewError,
  onSelectStock,
  onAddMonitor,
  onRemoveMonitor,
  onToggleSelectedMonitor,
}: IntradayMonitorPageProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <SnapshotMetaBar
        snapshot={snapshot}
        label="盘后研究依据"
        modeLabel="READY 研究依据 + preview 盘中触发"
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
        <section className="min-h-0 shrink-0 overflow-y-auto border-b border-white/10 xl:w-[340px] xl:border-b-0 xl:border-r hide-scrollbar">
          <MarketPanel
            market={snapshot.market_overview}
            priceBasis={snapshot.price_basis}
            snapshotId={snapshot.snapshot_id}
          />
        </section>
        <section className="min-h-0 shrink-0 overflow-y-auto border-b border-white/10 xl:w-[420px] xl:border-b-0 xl:border-r hide-scrollbar">
          <WatchlistPanel
            screener={screener}
            monitorItems={monitorItems}
            selectedStock={selectedStock}
            onSelectStock={onSelectStock}
            onAddMonitor={onAddMonitor}
            onRemoveMonitor={onRemoveMonitor}
            watchlistLoading={strategyWatchLoading}
            watchlistMutating={strategyWatchMutating}
            watchlistError={strategyWatchError}
            intradayItemsBySymbol={intradayItemsBySymbol}
            intradaySourceStatus={intradaySourceStatus}
            intradayLoading={intradayPreviewLoading}
            intradayError={intradayPreviewError}
            snapshotId={snapshot.snapshot_id}
            rawSnapshotId={snapshot.raw_snapshot_id}
            priceBasis={snapshot.price_basis}
          />
        </section>
        <section className="min-h-0 min-w-0 flex-1 overflow-hidden">
          <StockDetail
            stockData={stockData}
            selectedSymbol={selectedStock}
            loading={stockLoading}
            error={stockError}
            isMonitored={selectedStockIsMonitored}
            monitorItem={selectedMonitorItem}
            intradayMonitorItem={selectedIntradayItem}
            monitoringBusy={strategyWatchMutating}
            onToggleMonitor={onToggleSelectedMonitor}
            snapshotId={snapshot.snapshot_id}
            rawSnapshotId={snapshot.raw_snapshot_id}
            priceBasis={snapshot.price_basis}
          />
        </section>
      </div>
    </div>
  );
}

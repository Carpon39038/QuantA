import type { IntradayPreviewItem, SnapshotResponse, StrategyWatchlistItem } from '../../api/types';
import { SnapshotMetaBar } from '../../app/components/SnapshotMetaBar';
import type { StockData } from '../../hooks/useStock';
import { StockDetail } from './StockDetail';

interface StockDetailPageProps {
  snapshot: SnapshotResponse;
  selectedStock: string | null;
  stockData: StockData;
  stockLoading: boolean;
  stockError: string | null;
  selectedStockIsMonitored: boolean;
  selectedMonitorItem: StrategyWatchlistItem | null;
  selectedIntradayItem: IntradayPreviewItem | null;
  strategyWatchMutating: boolean;
  onToggleSelectedMonitor: () => Promise<void>;
}

export function StockDetailPage({
  snapshot,
  selectedStock,
  stockData,
  stockLoading,
  stockError,
  selectedStockIsMonitored,
  selectedMonitorItem,
  selectedIntradayItem,
  strategyWatchMutating,
  onToggleSelectedMonitor,
}: StockDetailPageProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <SnapshotMetaBar
        snapshot={snapshot}
        label="盘后研究依据"
        modeLabel="个股详情 · 量价诊断"
      />
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
    </div>
  );
}

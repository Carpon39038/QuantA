import type {
  IntradayPreviewItem,
  ScreenerCandidate,
  SnapshotResponse,
  StrategyWatchlistItem,
} from '../../api/types';
import { SnapshotMetaBar } from '../../app/components/SnapshotMetaBar';
import type { StockData } from '../../hooks/useStock';
import { StockListItem } from '../../shared/ui/StockListItem';
import { StockDetail } from '../stock-detail/StockDetail';

interface ScreenerResultsPageProps {
  snapshot: SnapshotResponse;
  selectedStock: string | null;
  stockData: StockData;
  stockLoading: boolean;
  stockError: string | null;
  selectedStockIsMonitored: boolean;
  selectedMonitorItem: StrategyWatchlistItem | null;
  selectedIntradayItem: IntradayPreviewItem | null;
  strategyWatchMutating: boolean;
  onSelectStock: (symbol: string) => void;
  onToggleSelectedMonitor: () => Promise<void>;
}

function CandidateSummary({ candidate }: { candidate: ScreenerCandidate }) {
  return (
    <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-white/45">
      <div>趋势 {candidate.trend_score ?? '--'}</div>
      <div>量价 {candidate.price_volume_score ?? '--'}</div>
      <div>资金 {candidate.capital_score ?? '--'}</div>
      <div>基本面 {candidate.fundamental_score ?? '--'}</div>
    </div>
  );
}

export function ScreenerResultsPage({
  snapshot,
  selectedStock,
  stockData,
  stockLoading,
  stockError,
  selectedStockIsMonitored,
  selectedMonitorItem,
  selectedIntradayItem,
  strategyWatchMutating,
  onSelectStock,
  onToggleSelectedMonitor,
}: ScreenerResultsPageProps) {
  const candidates = snapshot.screener.top_candidates ?? [];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <SnapshotMetaBar
        snapshot={snapshot}
        label="盘后研究依据"
        modeLabel={`选股结果 · ${snapshot.screener.signal_price_basis}`}
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
        <section className="min-h-0 shrink-0 overflow-y-auto border-b border-white/10 p-3 xl:w-[420px] xl:border-b-0 xl:border-r hide-scrollbar">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-medium text-white/70">选股结果</div>
              <div className="mt-0.5 text-[10px] text-white/40">
                {snapshot.screener.strategy_name} · {snapshot.screener.as_of_date}
              </div>
            </div>
            <div className="text-[10px] text-white/40">{candidates.length} 只</div>
          </div>
          <div className="space-y-2">
            {candidates.map((candidate) => (
              <div
                key={candidate.symbol}
                className="rounded-lg border border-white/10 bg-white/[0.03] p-2"
              >
                <StockListItem
                  name={candidate.name}
                  code={candidate.symbol}
                  score={candidate.score}
                  selected={selectedStock === candidate.symbol}
                  onClick={() => onSelectStock(candidate.symbol)}
                  trendScore={candidate.trend_score}
                  priceVolumeScore={candidate.price_volume_score}
                  capitalScore={candidate.capital_score}
                />
                <CandidateSummary candidate={candidate} />
                <div className="mt-2 text-[11px] leading-relaxed text-white/55">
                  {candidate.thesis}
                </div>
              </div>
            ))}
          </div>
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

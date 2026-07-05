import type { SnapshotResponse } from '../../api/types';
import { SnapshotMetaBar } from '../../app/components/SnapshotMetaBar';
import type { BacktestDetail } from '../../hooks/useBacktest';
import { BacktestPanel } from './BacktestPanel';

interface BacktestReportPageProps {
  snapshot: SnapshotResponse;
  backtestDetail: BacktestDetail;
  backtestLoading: boolean;
  backtestError: string | null;
}

export function BacktestReportPage({
  snapshot,
  backtestDetail,
  backtestLoading,
  backtestError,
}: BacktestReportPageProps) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <SnapshotMetaBar
        snapshot={snapshot}
        label="历史回放结果"
        modeLabel={`回测报告 · ${snapshot.backtest.window}`}
      />
      <div className="min-h-0 flex-1 overflow-y-auto hide-scrollbar">
        <BacktestPanel
          backtest={snapshot.backtest}
          backtestDetail={backtestDetail}
          loading={backtestLoading}
          error={backtestError}
          snapshotId={snapshot.snapshot_id}
          rawSnapshotId={snapshot.raw_snapshot_id}
          priceBasis={snapshot.price_basis}
        />
      </div>
    </div>
  );
}

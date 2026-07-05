import type { AlertsResponse, SnapshotResponse, SystemHealthResponse } from '../../api/types';
import { SnapshotMetaBar } from '../../app/components/SnapshotMetaBar';
import { MarketPanel } from './MarketPanel';

interface MarketOverviewPageProps {
  snapshot: SnapshotResponse;
  alerts: AlertsResponse | null;
  health: SystemHealthResponse | null;
}

export function MarketOverviewPage({ snapshot, alerts, health }: MarketOverviewPageProps) {
  const historyCoverage = health?.history_coverage;
  const alertSummary = alerts?.summary;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <SnapshotMetaBar
        snapshot={snapshot}
        label="盘后研究依据"
        modeLabel="市场事实 · READY snapshot"
      />
      <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto xl:grid-cols-[minmax(0,1fr)_340px] hide-scrollbar">
        <section className="border-b border-white/10 xl:border-b-0 xl:border-r">
          <MarketPanel
            market={snapshot.market_overview}
            priceBasis={snapshot.price_basis}
            snapshotId={snapshot.snapshot_id}
          />
        </section>
        <aside className="space-y-3 p-4">
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
            <div className="text-xs font-medium text-white/70">历史覆盖</div>
            <div className="mt-2 text-xl font-semibold text-white/90">
              {historyCoverage ? `${historyCoverage.open_day_count} 日` : '--'}
            </div>
            <div className="mt-1 text-[10px] text-white/45">
              {historyCoverage?.start_biz_date ?? '--'}{' -> '}{historyCoverage?.end_biz_date ?? '--'}
            </div>
            <div className="mt-2 text-[10px] text-white/35">
              建议起点 {historyCoverage?.recommended_target_start_biz_date ?? '--'}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
            <div className="text-xs font-medium text-white/70">告警摘要</div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
              <div className="rounded-md bg-black/20 p-2">
                <div className="text-white/35">INFO</div>
                <div className="mt-1 text-white/75">{alertSummary?.severity_counts.INFO ?? 0}</div>
              </div>
              <div className="rounded-md bg-black/20 p-2">
                <div className="text-white/35">WARNING</div>
                <div className="mt-1 text-amber-200">{alertSummary?.severity_counts.WARNING ?? 0}</div>
              </div>
              <div className="rounded-md bg-black/20 p-2">
                <div className="text-white/35">ERROR</div>
                <div className="mt-1 text-rose-300">{alertSummary?.severity_counts.ERROR ?? 0}</div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

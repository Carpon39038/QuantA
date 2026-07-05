import { Database, Filter, ShieldAlert, Bell, PlayCircle, Calendar, History } from 'lucide-react';
import type { SnapshotResponse, SystemHealthResponse } from '../../api/types';
import { StatusCard } from '../../shared/ui/StatusCard';

interface StatusStripProps {
  snapshot: SnapshotResponse;
  health?: SystemHealthResponse | null;
}

export function StatusStrip({ snapshot, health }: StatusStripProps) {
  const sv = snapshot.shadow_validation;
  const svStatus = sv?.status === 'PASSED' ? 'success' : sv?.status === 'FAILED' ? 'error' : 'neutral';

  const runtime = snapshot.runtime;
  const sourceCount = runtime?.source_symbol_count ?? 0;

  const alertErrorCount = health?.alert_summary?.severity_counts?.ERROR ?? 0;
  const alertWarnCount = health?.alert_summary?.severity_counts?.WARNING ?? 0;
  const alertTotal = alertErrorCount + alertWarnCount;
  const alertStatus = alertErrorCount > 0 ? 'error' : alertWarnCount > 0 ? 'warn' : 'success';
  const historyCoverage = health?.history_coverage;
  const historyCoverageSpan = historyCoverage?.start_biz_date && historyCoverage.end_biz_date
    ? `${historyCoverage.start_biz_date} -> ${historyCoverage.end_biz_date}`
    : undefined;

  const screener = snapshot.screener;
  const candidateCount = screener?.top_candidates?.length ?? 0;

  const backtest = snapshot.backtest;

  return (
    <div className="flex gap-3 overflow-x-auto border-b border-white/10 p-4">
      <StatusCard
        title="发布快照"
        value={snapshot.snapshot_id?.slice(0, 8) ?? '--'}
        subValue={snapshot.status}
        status={snapshot.status === 'PUBLISHED' ? 'success' : 'warn'}
        icon={<Database size={14} />}
      />
      <StatusCard
        title="研究池"
        value={String(sourceCount)}
        subValue={runtime?.source_universe}
        status="neutral"
        icon={<Filter size={14} />}
      />
      <StatusCard
        title="补充校验"
        value={sv?.status ?? '--'}
        status={svStatus}
        icon={<ShieldAlert size={14} />}
      />
      <StatusCard
        title="告警"
        value={String(alertTotal)}
        subValue={`${alertErrorCount} 错误 / ${alertWarnCount} 警告`}
        status={alertStatus}
        icon={<Bell size={14} />}
      />
      <StatusCard
        title="历史覆盖"
        value={historyCoverage ? `${historyCoverage.open_day_count}日` : '--'}
        subValue={historyCoverageSpan}
        status={historyCoverage && historyCoverage.open_day_count > 0 ? 'success' : 'neutral'}
        icon={<History size={14} />}
      />
      <StatusCard
        title="选股运行"
        value={String(candidateCount)}
        subValue={screener?.strategy_name}
        status="success"
        icon={<PlayCircle size={14} />}
      />
      <StatusCard
        title="回测窗口"
        value={backtest?.window ?? '--'}
        subValue={backtest?.strategy_name}
        status="neutral"
        icon={<Calendar size={14} />}
      />
    </div>
  );
}

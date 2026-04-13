import type { SnapshotResponse, AlertsResponse } from '../api/types';
import { TaskCard } from './ui/TaskCard';
import { AlertItem as AlertItemUI } from './ui/AlertItem';

interface TaskSidebarProps {
  snapshot: SnapshotResponse;
  alerts: AlertsResponse | null;
}

function taskStatusToCardStatus(status: string): 'success' | 'running' | 'neutral' {
  if (status === 'COMPLETED' || status === 'SUCCESS') return 'success';
  if (status === 'RUNNING' || status === 'PENDING') return 'running';
  return 'neutral';
}

export function TaskSidebar({ snapshot, alerts }: TaskSidebarProps) {
  const taskEntries = Object.entries(snapshot.task_status ?? {});
  const filteredAlerts = (alerts?.items ?? []).filter(
    (a) => a.severity === 'WARNING' || a.severity === 'ERROR',
  );

  return (
    <div className="w-[200px] border-r border-white/10 flex flex-col shrink-0 bg-[#1C1C1E] overflow-y-auto hide-scrollbar">
      {/* Task Pipeline */}
      <div className="p-3">
        <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">任务流水线</div>
        {taskEntries.map(([name, entry]) => (
          <TaskCard
            key={name}
            title={name}
            time={entry.last_run ? new Date(entry.last_run).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--'}
            status={taskStatusToCardStatus(entry.status)}
          />
        ))}
      </div>

      {/* Alerts */}
      <div className="p-3 border-t border-white/10">
        <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">告警</div>
        {filteredAlerts.length === 0 && (
          <div className="text-[10px] text-white/30 py-2">暂无告警</div>
        )}
        {filteredAlerts.map((alert, i) => (
          <AlertItemUI
            key={i}
            message={alert.message}
            time={alert.triggered_at ? new Date(alert.triggered_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--'}
            type={alert.severity === 'ERROR' ? 'error' : 'warn'}
          />
        ))}
      </div>
    </div>
  );
}

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

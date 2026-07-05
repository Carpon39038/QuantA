import { AlertTriangle, AlertCircle } from 'lucide-react';

interface AlertItemProps {
  message: string;
  time: string;
  type: 'warn' | 'error';
}

export function AlertItem({ message, time, type }: AlertItemProps) {
  return (
    <div className="flex items-start gap-2 p-2 rounded-md bg-white/[0.02] border border-white/5 mb-2">
      {type === 'warn' ? <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" /> : <AlertCircle size={14} className="text-rose-400 shrink-0 mt-0.5" />}
      <div className="flex-1">
        <div className="text-xs text-white/80">{message}</div>
        <div className="text-[10px] text-white/40 mt-0.5">{time}</div>
      </div>
    </div>
  );
}

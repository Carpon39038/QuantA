import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface StatusCardProps {
  title: string;
  value: string;
  subValue?: string;
  status: 'success' | 'warn' | 'error' | 'neutral';
  icon: ReactNode;
}

export function StatusCard({ title, value, subValue, status, icon }: StatusCardProps) {
  return (
    <div className="flex-1 min-w-[160px] bg-white/[0.03] rounded-lg p-3 border border-white/5 flex flex-col gap-2 hover:bg-white/[0.05] transition-colors cursor-default">
      <div className="flex items-center gap-1.5 text-xs text-white/50">
        {icon}
        <span>{title}</span>
      </div>
      <div className="flex items-end justify-between">
        <div className="text-sm font-medium text-white/90">{value}</div>
        {subValue && (
          <div className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', {
            'bg-emerald-500/10 text-emerald-400': status === 'success',
            'bg-amber-500/10 text-amber-400': status === 'warn',
            'bg-rose-500/10 text-rose-400': status === 'error',
            'bg-white/10 text-white/60': status === 'neutral',
          })}>
            {subValue}
          </div>
        )}
      </div>
    </div>
  );
}

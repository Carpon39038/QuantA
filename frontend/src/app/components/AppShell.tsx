import {
  BarChart3,
  BellRing,
  CandlestickChart,
  LineChart,
  ListFilter,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { AlertsResponse, SnapshotResponse, SystemHealthResponse } from '../../api/types';
import { cn } from '../../lib/cn';
import type { AppRouteId } from '../routes';
import { NAV_ROUTES, stockRoute } from '../routes';
import { StatusStrip } from './StatusStrip';
import { TaskSidebar } from './TaskSidebar';

interface AppShellProps {
  snapshot: SnapshotResponse;
  alerts: AlertsResponse | null;
  health: SystemHealthResponse | null;
  activeRouteId: AppRouteId;
  selectedSymbol: string | null;
  onNavigate: (path: string) => void;
  children: ReactNode;
}

const routeIcons: Record<AppRouteId, ReactNode> = {
  monitor: <BellRing size={14} />,
  market: <BarChart3 size={14} />,
  screener: <ListFilter size={14} />,
  stock: <CandlestickChart size={14} />,
  backtest: <LineChart size={14} />,
};

export function AppShell({
  snapshot,
  alerts,
  health,
  activeRouteId,
  selectedSymbol,
  onNavigate,
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-black p-3 text-sm font-sans text-white/90 md:p-6">
      <div className="mx-auto flex min-h-[calc(100vh-1.5rem)] w-full max-w-[1600px] flex-col overflow-hidden rounded-lg border border-white/10 bg-[#1C1C1E] shadow-2xl md:min-h-[calc(100vh-3rem)]">
        <StatusStrip snapshot={snapshot} health={health} />
        <div className="flex items-center gap-2 overflow-x-auto border-b border-white/10 px-3 py-2">
          {NAV_ROUTES.map((route) => {
            const active = route.id === activeRouteId;
            const path = route.id === 'stock' ? stockRoute(selectedSymbol) : route.path;
            return (
              <button
                key={route.id}
                type="button"
                onClick={() => onNavigate(path)}
                className={cn(
                  'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border px-3 text-xs transition-colors',
                  active
                    ? 'border-blue-400/35 bg-blue-500/15 text-blue-100'
                    : 'border-white/10 bg-white/[0.03] text-white/55 hover:bg-white/[0.06] hover:text-white/80',
                )}
              >
                {routeIcons[route.id]}
                {route.label}
              </button>
            );
          })}
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
          <TaskSidebar snapshot={snapshot} alerts={alerts} />
          <main className="min-h-0 min-w-0 flex-1 overflow-hidden">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

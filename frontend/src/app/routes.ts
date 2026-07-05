export type AppRouteId = 'monitor' | 'market' | 'screener' | 'stock' | 'backtest';

export interface NavRoute {
  id: AppRouteId;
  label: string;
  path: string;
}

export interface ParsedRoute {
  id: AppRouteId;
  symbol: string | null;
}

export const DEFAULT_ROUTE = '/monitor';

export const NAV_ROUTES: NavRoute[] = [
  { id: 'monitor', label: '盘中监控', path: '/monitor' },
  { id: 'market', label: '市场概览', path: '/market' },
  { id: 'screener', label: '选股结果', path: '/screener' },
  { id: 'stock', label: '个股详情', path: '/stocks' },
  { id: 'backtest', label: '回测报告', path: '/backtest' },
];

export function stockRoute(symbol: string | null | undefined): string {
  if (!symbol) return '/stocks';
  return `/stocks/${encodeURIComponent(symbol)}`;
}

export function parseAppRoute(pathname: string): ParsedRoute {
  if (pathname === '/' || pathname === '') {
    return { id: 'monitor', symbol: null };
  }

  if (pathname.startsWith('/market')) {
    return { id: 'market', symbol: null };
  }

  if (pathname.startsWith('/screener')) {
    return { id: 'screener', symbol: null };
  }

  if (pathname.startsWith('/stocks')) {
    const [, , rawSymbol] = pathname.split('/');
    return {
      id: 'stock',
      symbol: rawSymbol ? decodeURIComponent(rawSymbol) : null,
    };
  }

  if (pathname.startsWith('/backtest')) {
    return { id: 'backtest', symbol: null };
  }

  return { id: 'monitor', symbol: null };
}

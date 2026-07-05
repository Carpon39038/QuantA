import { useEffect, useMemo, useState } from 'react';
import { AppShell } from './app/components/AppShell';
import { parseAppRoute, stockRoute } from './app/routes';
import { useBrowserRoute } from './app/useBrowserRoute';
import { BacktestReportPage } from './features/backtest-report/BacktestReportPage';
import { IntradayMonitorPage } from './features/intraday-monitor/IntradayMonitorPage';
import { MarketOverviewPage } from './features/market-overview/MarketOverviewPage';
import { ScreenerResultsPage } from './features/screener-results/ScreenerResultsPage';
import { StockDetailPage } from './features/stock-detail/StockDetailPage';
import { useBacktest } from './hooks/useBacktest';
import { useIntradayPreviewWatchlist } from './hooks/useIntradayPreviewWatchlist';
import { useSnapshot } from './hooks/useSnapshot';
import { useStock } from './hooks/useStock';
import { useStrategyWatchlist } from './hooks/useStrategyWatchlist';
import { useSystem } from './hooks/useSystem';

export default function App() {
  const { pathname, navigate } = useBrowserRoute();
  const route = useMemo(() => parseAppRoute(pathname), [pathname]);
  const { data: snapshot, loading: snapshotLoading, error: snapshotError } = useSnapshot();
  const { alerts, health, loading: systemLoading } = useSystem();
  const { data: backtestDetail, loading: backtestLoading, error: backtestError } = useBacktest();
  const {
    data: intradayPreview,
    loading: intradayPreviewLoading,
    error: intradayPreviewError,
  } = useIntradayPreviewWatchlist();
  const {
    items: strategyWatchItems,
    loading: strategyWatchLoading,
    mutating: strategyWatchMutating,
    error: strategyWatchError,
    add: addStrategyWatch,
    remove: removeStrategyWatch,
  } = useStrategyWatchlist();

  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const { data: stockData, loading: stockLoading, error: stockError } = useStock(selectedStock);
  const intradayItems = intradayPreview?.items;
  const intradayItemBySymbol = useMemo(
    () => new Map((intradayItems ?? []).map((item) => [item.symbol, item])),
    [intradayItems],
  );

  useEffect(() => {
    if (route.id === 'stock' && route.symbol && route.symbol !== selectedStock) {
      setSelectedStock(route.symbol);
    }
  }, [route.id, route.symbol, selectedStock]);

  useEffect(() => {
    if (!selectedStock && snapshot?.screener?.top_candidates?.length) {
      setSelectedStock(snapshot.screener.top_candidates[0].symbol);
    }
  }, [snapshot, selectedStock]);

  if (snapshotLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-sm text-white/50">
        加载快照数据...
      </div>
    );
  }

  if (snapshotError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-sm text-rose-400">
        加载失败: {snapshotError}
      </div>
    );
  }

  if (!snapshot) return null;

  const selectedStockIsMonitored = strategyWatchItems.some((item) => item.symbol === selectedStock);
  const selectedMonitorItem =
    strategyWatchItems.find((item) => item.symbol === selectedStock) ?? null;
  const selectedIntradayItem = selectedStock
    ? intradayItemBySymbol.get(selectedStock) ?? null
    : null;

  const handleSelectStock = (symbol: string) => {
    setSelectedStock(symbol);
  };

  const handleAddMonitor = async (symbol: string) => {
    const item = await addStrategyWatch(symbol);
    setSelectedStock(item.symbol);
  };

  const handleRemoveMonitor = async (symbol: string) => {
    await removeStrategyWatch(symbol);
  };

  const handleToggleSelectedMonitor = async () => {
    if (!selectedStock) return;
    if (selectedStockIsMonitored) {
      await handleRemoveMonitor(selectedStock);
    } else {
      await handleAddMonitor(selectedStock);
    }
  };

  const openStockDetail = (symbol: string) => {
    setSelectedStock(symbol);
    navigate(stockRoute(symbol));
  };

  const commonStockProps = {
    selectedStock,
    stockData,
    stockLoading,
    stockError,
    selectedStockIsMonitored,
    selectedMonitorItem,
    selectedIntradayItem,
    strategyWatchMutating,
    onToggleSelectedMonitor: handleToggleSelectedMonitor,
  };

  const page = (() => {
    if (route.id === 'market') {
      return (
        <MarketOverviewPage
          snapshot={snapshot}
          alerts={systemLoading ? null : alerts}
          health={systemLoading ? null : health}
        />
      );
    }

    if (route.id === 'screener') {
      return (
        <ScreenerResultsPage
          snapshot={snapshot}
          {...commonStockProps}
          onSelectStock={openStockDetail}
        />
      );
    }

    if (route.id === 'stock') {
      return (
        <StockDetailPage
          snapshot={snapshot}
          {...commonStockProps}
        />
      );
    }

    if (route.id === 'backtest') {
      return (
        <BacktestReportPage
          snapshot={snapshot}
          backtestDetail={backtestDetail}
          backtestLoading={backtestLoading}
          backtestError={backtestError}
        />
      );
    }

    return (
      <IntradayMonitorPage
        snapshot={snapshot}
        screener={snapshot.screener}
        monitorItems={strategyWatchItems}
        selectedStock={selectedStock}
        stockData={stockData}
        stockLoading={stockLoading}
        stockError={stockError}
        selectedStockIsMonitored={selectedStockIsMonitored}
        selectedMonitorItem={selectedMonitorItem}
        selectedIntradayItem={selectedIntradayItem}
        strategyWatchLoading={strategyWatchLoading}
        strategyWatchMutating={strategyWatchMutating}
        strategyWatchError={strategyWatchError}
        intradayItemsBySymbol={intradayItemBySymbol}
        intradaySourceStatus={intradayPreview?.source_status ?? null}
        intradayPreviewLoading={intradayPreviewLoading}
        intradayPreviewError={intradayPreviewError}
        onSelectStock={handleSelectStock}
        onAddMonitor={handleAddMonitor}
        onRemoveMonitor={handleRemoveMonitor}
        onToggleSelectedMonitor={handleToggleSelectedMonitor}
      />
    );
  })();

  return (
    <AppShell
      snapshot={snapshot}
      alerts={systemLoading ? null : alerts}
      health={systemLoading ? null : health}
      activeRouteId={route.id}
      selectedSymbol={selectedStock}
      onNavigate={navigate}
    >
      {page}
    </AppShell>
  );
}

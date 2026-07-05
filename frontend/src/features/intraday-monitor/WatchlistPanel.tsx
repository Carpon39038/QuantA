import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import type {
  IntradayPreviewItem,
  IntradayPreviewSourceStatus,
  ScreenerSection,
  StrategyWatchlistItem,
} from '../../api/types';
import { StockListItem } from '../../shared/ui/StockListItem';

interface WatchlistPanelProps {
  screener: ScreenerSection;
  monitorItems: StrategyWatchlistItem[];
  selectedStock: string | null;
  onSelectStock: (symbol: string) => void;
  onAddMonitor: (symbol: string) => Promise<void>;
  onRemoveMonitor: (symbol: string) => Promise<void>;
  watchlistLoading?: boolean;
  watchlistMutating?: boolean;
  watchlistError?: string | null;
  intradayItemsBySymbol?: Map<string, IntradayPreviewItem>;
  intradaySourceStatus?: IntradayPreviewSourceStatus | null;
  intradayLoading?: boolean;
  intradayError?: string | null;
  snapshotId?: string;
  rawSnapshotId?: string;
  priceBasis?: string;
}

function statusTone(status: StrategyWatchlistItem['monitoring_status']): string {
  if (status === 'BUY') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/20';
  if (status === 'SELL') return 'bg-rose-500/15 text-rose-300 border-rose-500/20';
  if (status === 'WATCH') return 'bg-amber-500/15 text-amber-200 border-amber-500/20';
  return 'bg-white/5 text-white/45 border-white/10';
}

function realtimeSignalTone(signalStage: IntradayPreviewItem['signal_stage'] | undefined): string {
  if (signalStage === 'STOP_LOSS_TRIGGERED') return 'text-rose-300';
  if (signalStage === 'RISK_WARNING') return 'text-amber-200';
  if (signalStage === 'TAKE_PROFIT_TRIGGERED') return 'text-sky-200';
  if (signalStage === 'BUY_TRIGGERED') return 'text-emerald-300';
  return 'text-white/40';
}

export function WatchlistPanel({
  screener,
  monitorItems,
  selectedStock,
  onSelectStock,
  onAddMonitor,
  onRemoveMonitor,
  watchlistLoading,
  watchlistMutating,
  watchlistError,
  intradayItemsBySymbol,
  intradaySourceStatus,
  intradayLoading,
  intradayError,
  snapshotId,
  rawSnapshotId,
  priceBasis,
}: WatchlistPanelProps) {
  const candidates = screener?.top_candidates ?? [];
  const [symbolInput, setSymbolInput] = useState('');

  const handleAdd = async () => {
    const trimmed = symbolInput.trim();
    if (!trimmed) return;
    try {
      await onAddMonitor(trimmed);
      setSymbolInput('');
    } catch {
      // Parent hook already surfaces the error state for the panel.
    }
  };

  return (
    <div className="flex-1 p-3 overflow-y-auto hide-scrollbar">
      <div className="mb-4 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        <div className="text-xs font-medium text-white/70 mb-2">策略监控队列</div>
        <div className="flex gap-2">
          <input
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void handleAdd();
              }
            }}
            placeholder="输入 300750 或 300750.SZ"
            className="flex-1 rounded-md border border-white/10 bg-black/20 px-2.5 py-2 text-xs text-white/80 outline-none placeholder:text-white/30 focus:border-blue-400/40"
          />
          <button
            type="button"
            onClick={() => void handleAdd()}
            disabled={watchlistMutating}
            className="inline-flex items-center gap-1 rounded-md border border-blue-400/20 bg-blue-500/10 px-2.5 py-2 text-xs text-blue-200 transition-colors hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus size={12} />
            加入
          </button>
        </div>
        <div className="mt-2 text-[10px] text-white/35">
          READY 研究依据 {snapshotId?.slice(0, 8) ?? '--'} · raw {rawSnapshotId?.slice(0, 8) ?? '--'} · {priceBasis ?? '--'}
        </div>
        {watchlistError && (
          <div className="mt-2 text-[10px] text-rose-300">{watchlistError}</div>
        )}
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs font-medium text-white/70">监控列表</div>
          <div className="text-right text-[10px] text-white/40">
            <div>{watchlistLoading ? '加载中...' : `${monitorItems.length} 只`}</div>
            <div>
              盘中预览 {intradayLoading ? '刷新中...' : intradaySourceStatus?.status ?? '--'}
            </div>
          </div>
        </div>
        <div className="mb-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-[10px] text-white/45">
          <div>
            {intradaySourceStatus?.mode === 'experimental'
              ? 'preview 盘中触发为 experimental，不进入 READY snapshot 或回测。'
              : 'preview 盘中触发仅用于盘中观察。'}
          </div>
          <div className="mt-1">
            {intradayError
              ? `预览错误: ${intradayError}`
              : intradaySourceStatus?.message ?? '等待盘中数据。'}
          </div>
          <div className="mt-1">
            {intradaySourceStatus?.last_updated_at
              ? `最后更新时间 ${intradaySourceStatus.last_updated_at}`
              : `市场阶段 ${intradaySourceStatus?.market_phase ?? '--'}`}
          </div>
        </div>
        {monitorItems.length === 0 && !watchlistLoading && (
          <div className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-[11px] text-white/35">
            还没有手动监控的股票。先输入代码，或从候选池里选中后在右侧加入监控。
          </div>
        )}
        <div className="space-y-2">
          {monitorItems.map((item) => {
            const intradayItem = intradayItemsBySymbol?.get(item.symbol);
            return (
              <div
                key={item.symbol}
                onClick={() => onSelectStock(item.symbol)}
                className={`rounded-lg border p-3 transition-all cursor-pointer ${
                  selectedStock === item.symbol
                    ? 'border-blue-400/35 bg-blue-500/10'
                    : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.05]'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white/90">{item.display_name}</span>
                      <span className="text-[10px] text-white/35">{item.symbol}</span>
                    </div>
                    <div className="mt-1 text-[10px] text-white/40">
                      {item.strategy_name} · {item.trade_date ?? '--'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] ${statusTone(item.monitoring_status)}`}>
                      {item.monitoring_status}
                    </span>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        void onRemoveMonitor(item.symbol).catch(() => undefined);
                      }}
                      disabled={watchlistMutating}
                      className="rounded-md border border-white/10 p-1 text-white/40 transition-colors hover:bg-white/5 hover:text-white/70 disabled:cursor-not-allowed disabled:opacity-50"
                      aria-label={`remove ${item.symbol}`}
                    >
                      <X size={12} />
                    </button>
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-white/55">
                  <div>盘后价 {item.current_price ?? '--'}</div>
                  <div>买点 {item.buy_trigger_price ?? '--'}</div>
                  <div>止盈 {item.sell_trigger_price ?? '--'}</div>
                </div>
                <div className="mt-1 text-[10px] text-white/45">
                  风控 {item.defensive_exit_price ?? '--'} · 止损 {item.stop_loss_price ?? '--'}
                </div>
                <div className="mt-2 rounded-md border border-white/10 bg-black/20 px-2.5 py-2 text-[10px] text-white/55">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      盘中价 {intradayItem?.realtime_price ?? '--'}
                      {intradayItem?.realtime_pct_chg != null && ` (${intradayItem.realtime_pct_chg > 0 ? '+' : ''}${intradayItem.realtime_pct_chg.toFixed(2)}%)`}
                    </div>
                    <div className={realtimeSignalTone(intradayItem?.signal_stage)}>
                      {intradayItem?.signal_stage ?? 'UNAVAILABLE'}
                    </div>
                  </div>
                  <div className="mt-1 text-[10px] text-white/45">
                    {intradayItem?.signal_message ?? '等待盘中报价。'}
                  </div>
                  <div className="mt-1 text-[10px] text-white/35">
                    {intradayItem?.realtime_trade_time
                      ? `盘中时间 ${intradayItem.realtime_trade_time}`
                      : '当前无盘中时间戳'}
                  </div>
                </div>
                <div className="mt-2 text-[11px] text-white/55 leading-relaxed">{item.thesis}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-white/70">候选股票</div>
        <div className="text-[10px] text-white/40">
          {candidates.length} 只 · {screener?.as_of_date}
        </div>
      </div>
      <div className="space-y-1">
        {candidates.map((c) => (
          <StockListItem
            key={c.symbol}
            name={c.name}
            code={c.symbol}
            score={c.score}
            selected={selectedStock === c.symbol}
            onClick={() => onSelectStock(c.symbol)}
            trendScore={c.trend_score}
            priceVolumeScore={c.price_volume_score}
            capitalScore={c.capital_score}
          />
        ))}
      </div>
    </div>
  );
}

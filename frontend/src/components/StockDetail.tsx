import {
  AreaChart, Area, ResponsiveContainer,
  CartesianGrid, XAxis, YAxis, Tooltip,
} from 'recharts';
import type { StockData } from '../hooks/useStock';
import type { IntradayPreviewItem, StrategyWatchlistItem } from '../api/types';
import { cn } from '../lib/cn';
import { QuoteItem } from './ui/QuoteItem';
import { TechItem } from './ui/TechItem';

interface StockDetailProps {
  stockData: StockData;
  selectedSymbol: string | null;
  loading?: boolean;
  error?: string | null;
  isMonitored?: boolean;
  monitorItem?: StrategyWatchlistItem | null;
  intradayMonitorItem?: IntradayPreviewItem | null;
  monitoringBusy?: boolean;
  onToggleMonitor?: () => Promise<void>;
}

function formatNum(v: number | null | undefined, digits = 2): string {
  if (v == null) return '--';
  return v.toFixed(digits);
}

function formatPct(v: number | null | undefined): string {
  if (v == null) return '--';
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function fmtAmount(v: number | null | undefined): string {
  if (v == null) return '--';
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(2)}万`;
  return v.toFixed(2);
}

export function StockDetail({
  stockData,
  selectedSymbol,
  loading,
  error,
  isMonitored,
  monitorItem,
  intradayMonitorItem,
  monitoringBusy,
  onToggleMonitor,
}: StockDetailProps) {
  if (!selectedSymbol) {
    return (
      <div className="flex-1 flex items-center justify-center text-white/30 text-sm">
        请选择一只股票查看详情
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-white/30 text-sm">
        加载中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-rose-400 text-sm">
        {error}
      </div>
    );
  }

  const { snapshot, kline, indicators, capitalFlow, fundamentals, disclosures } = stockData;

  // Price & change
  const dailyBar = snapshot?.latest_daily_bar;
  const close = dailyBar?.close_raw;
  const preClose = dailyBar?.pre_close_raw;
  const changePct = close != null && preClose ? ((close - preClose) / preClose) * 100 : null;
  const isUp = changePct != null ? changePct >= 0 : true;

  // Chart data from kline
  const chartData = (kline?.items ?? []).map((item) => ({
    date: item.trade_date,
    price: item.close,
  }));

  // Indicator data
  const ind = indicators?.latest_indicator;
  const patterns = indicators?.latest_patterns ?? [];

  // Capital flow
  const cap = capitalFlow?.latest_capital_feature;

  // Fundamentals
  const fund = fundamentals?.latest_fundamental_feature;
  const monitorTone =
    monitorItem?.monitoring_status === 'BUY'
      ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-200'
      : monitorItem?.monitoring_status === 'SELL'
        ? 'border-rose-500/25 bg-rose-500/10 text-rose-200'
        : monitorItem?.monitoring_status === 'WATCH'
          ? 'border-amber-500/25 bg-amber-500/10 text-amber-100'
          : 'border-white/10 bg-white/[0.03] text-white/70';

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 hide-scrollbar">
      {/* Stock Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-white/90">
              {snapshot?.display_name ?? selectedSymbol}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/50">
              {snapshot?.exchange ?? '--'}
            </span>
            {snapshot?.industry && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/50">
                {snapshot.industry}
              </span>
            )}
          </div>
          <div className="text-[10px] text-white/40 mt-0.5">{selectedSymbol}</div>
        </div>
        <div className="text-right">
          {onToggleMonitor && (
            <button
              type="button"
              onClick={() => void onToggleMonitor()}
              disabled={monitoringBusy}
              className="mb-2 rounded-md border border-blue-400/20 bg-blue-500/10 px-2.5 py-1 text-[10px] text-blue-200 transition-colors hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isMonitored ? '移出监控' : '加入监控'}
            </button>
          )}
          <div className={cn('text-xl font-semibold', isUp ? 'text-[#FF5F56]' : 'text-[#27C93F]')}>
            {close != null ? close.toFixed(2) : '--'}
          </div>
          <div className={cn('text-xs', isUp ? 'text-[#FF5F56]/80' : 'text-[#27C93F]/80')}>
            {formatPct(changePct)}
          </div>
        </div>
      </div>

      {monitorItem && (
        <div className={`rounded-xl border p-3 ${monitorTone}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-white/45">
                策略监控
              </div>
              <div className="mt-1 text-sm font-medium text-white/90">
                {monitorItem.strategy_name} · {monitorItem.monitoring_status}
              </div>
            </div>
            <div className="text-right text-[10px] text-white/55">
              <div>快照 {monitorItem.snapshot_id}</div>
              <div>{monitorItem.trade_date ?? '--'}</div>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-[11px] md:grid-cols-4">
            <div>买点 {formatNum(monitorItem.buy_trigger_price)}</div>
            <div>止盈 {formatNum(monitorItem.sell_trigger_price)}</div>
            <div>风控 {formatNum(monitorItem.defensive_exit_price)}</div>
            <div>止损 {formatNum(monitorItem.stop_loss_price)}</div>
          </div>
          <div className="mt-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-[11px] text-white/70">
            <div className="flex items-center justify-between gap-3">
              <div>
                盘中价 {formatNum(intradayMonitorItem?.realtime_price)}
                {intradayMonitorItem?.realtime_pct_chg != null && ` (${intradayMonitorItem.realtime_pct_chg > 0 ? '+' : ''}${intradayMonitorItem.realtime_pct_chg.toFixed(2)}%)`}
              </div>
              <div className="text-[10px] text-white/45">
                {intradayMonitorItem?.realtime_trade_time ?? '无盘中时间'}
              </div>
            </div>
            <div className="mt-1 text-[10px] text-white/55">
              {intradayMonitorItem?.signal_message ?? '等待盘中预览刷新。'}
            </div>
          </div>
          <div className="mt-3 text-[11px] leading-relaxed text-white/75">
            {monitorItem.entry_reason}
          </div>
          <div className="mt-1 text-[11px] leading-relaxed text-white/60">
            {monitorItem.exit_reason}
          </div>
        </div>
      )}

      {/* Quote Grid */}
      <div className="grid grid-cols-4 gap-3">
        <QuoteItem label="昨收" value={formatNum(preClose)} />
        <QuoteItem label="候选得分" value="--" />
        <QuoteItem label="财务得分" value={formatNum(fund?.fundamental_score)} />
        <QuoteItem
          label="形态信号"
          value={String(patterns.filter((p) => p.is_triggered).length)}
          highlight="text-white/90"
        />
      </div>

      {/* Price Chart */}
      {chartData.length > 0 && (
        <div className="h-[180px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="date" stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis domain={['dataMin - 10', 'dataMax + 10']} stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} orientation="right" />
              <Tooltip contentStyle={{ backgroundColor: '#2D2D2D', borderColor: '#ffffff10', borderRadius: '8px', fontSize: '12px' }} />
              <Area type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Technical Indicators */}
      <div>
        <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">技术指标</div>
        <div className="space-y-1.5">
          <TechItem label="MA5" value={formatNum(ind?.ma5)} isUp={null} />
          <TechItem label="MACD" value={formatNum(ind?.macd_dif)} isUp={(ind?.macd_hist ?? 0) > 0 ? true : (ind?.macd_hist ?? 0) < 0 ? false : null} />
          <TechItem label="RSI6" value={formatNum(ind?.rsi6)} isUp={null} />
          <TechItem label="量比" value={formatNum(ind?.volume_ratio)} isUp={null} />
        </div>
      </div>

      {/* Pattern Signals */}
      {patterns.length > 0 && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">形态信号</div>
          <div className="flex flex-wrap gap-1.5">
            {patterns.map((p, i) => (
              <span
                key={i}
                className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded',
                  p.is_triggered
                    ? p.direction === 'BULLISH'
                      ? 'bg-[#FF5F56]/10 text-[#FF5F56]'
                      : 'bg-[#27C93F]/10 text-[#27C93F]'
                    : 'bg-white/5 text-white/40',
                )}
              >
                {p.signal_code} {p.is_triggered && `(${p.signal_score})`}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Capital Flow */}
      {cap && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">资金流向</div>
          <div className="space-y-1.5">
            <TechItem
              label="主力净流入"
              value={fmtAmount(cap.main_net_inflow)}
              isUp={(cap.main_net_inflow ?? 0) >= 0}
            />
            <TechItem
              label="北向资金"
              value={fmtAmount(cap.northbound_net_inflow)}
              isUp={(cap.northbound_net_inflow ?? 0) >= 0}
            />
            <TechItem
              label="龙虎榜"
              value={cap.has_dragon_tiger ? '有' : '无'}
              isUp={cap.has_dragon_tiger ? true : null}
            />
          </div>
        </div>
      )}

      {/* Fundamentals */}
      {fund && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">基本面</div>
          <div className="space-y-1.5">
            <TechItem label="ROE" value={formatPct(fund.roe_dt)} isUp={null} />
            <TechItem label="资产负债率" value={formatPct(fund.debt_to_assets)} isUp={null} />
            <TechItem label="现利比" value={formatNum(fund.cash_to_profit)} isUp={null} />
            <TechItem label="营业收入" value={fmtAmount(fund.total_revenue)} isUp={null} />
          </div>
        </div>
      )}

      {/* Disclosures */}
      {(disclosures?.items ?? []).length > 0 && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-2">公告</div>
          <div className="space-y-1.5">
            {disclosures!.items.map((d, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-white/70 truncate flex-1">{d.title}</span>
                <span className="text-[10px] text-white/40 shrink-0 ml-2">
                  {d.announcement_time ? new Date(d.announcement_time).toLocaleDateString('zh-CN') : '--'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

import {
  LineChart, Line, ResponsiveContainer,
  CartesianGrid, XAxis, YAxis, Tooltip,
} from 'recharts';
import type { BacktestSection } from '../api/types';
import type { BacktestDetail } from '../hooks/useBacktest';
import { cn } from '../lib/cn';

interface BacktestPanelProps {
  backtest: BacktestSection;
  backtestDetail: BacktestDetail;
  loading?: boolean;
  error?: string | null;
}

export function BacktestPanel({ backtest, backtestDetail, loading, error }: BacktestPanelProps) {
  const metrics = backtest?.metrics;
  const notes = backtest?.notes ?? [];
  const curveData = (backtestDetail.equityCurve?.equity_curve ?? []).map((p) => ({
    date: p.trade_date,
    equity: p.equity,
  }));
  const trades = backtestDetail.trades?.trades ?? [];

  if (loading) {
    return (
      <div className="h-[280px] flex items-center justify-center text-white/30 text-sm border-t border-white/10">
        加载回测数据...
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-[280px] flex items-center justify-center text-rose-400 text-sm border-t border-white/10">
        {error}
      </div>
    );
  }

  return (
    <div className="border-t border-white/10 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-white/70">回测分析</div>
        <div className="text-[10px] text-white/40">{backtest?.window ?? '--'}</div>
      </div>

      {/* Metrics Grid */}
      {metrics && (
        <div className="grid grid-cols-4 gap-3">
          <MetricItem label="年化收益" value={`${metrics.cagr_pct.toFixed(2)}%`} positive={metrics.cagr_pct > 0} />
          <MetricItem label="最大回撤" value={`${metrics.max_drawdown_pct.toFixed(2)}%`} positive={false} />
          <MetricItem label="胜率" value={`${metrics.win_rate_pct.toFixed(1)}%`} positive={metrics.win_rate_pct > 50} />
          <MetricItem label="利润因子" value={metrics.profit_factor.toFixed(2)} positive={metrics.profit_factor > 1} />
        </div>
      )}

      {/* Equity Curve */}
      {curveData.length > 0 && (
        <div className="h-[140px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={curveData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
              <XAxis dataKey="date" stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
              <YAxis domain={['auto', 'auto']} stroke="#ffffff30" fontSize={10} tickLine={false} axisLine={false} orientation="right" />
              <Tooltip contentStyle={{ backgroundColor: '#2D2D2D', borderColor: '#ffffff10', borderRadius: '8px', fontSize: '12px' }} />
              <Line type="monotone" dataKey="equity" stroke="#FF5F56" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Trade Table */}
      {trades.length > 0 && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-1.5">交易记录</div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-white/40 border-b border-white/5">
                  <th className="text-left py-1 font-normal">日期</th>
                  <th className="text-left py-1 font-normal">方向</th>
                  <th className="text-left py-1 font-normal">标的</th>
                  <th className="text-right py-1 font-normal">价格</th>
                  <th className="text-right py-1 font-normal">数量</th>
                  <th className="text-right py-1 font-normal">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="border-b border-white/[0.03]">
                    <td className="py-1 text-white/60">{t.trade_date}</td>
                    <td className={cn('py-1', t.side === 'BUY' ? 'text-[#FF5F56]' : 'text-[#27C93F]')}>{t.side === 'BUY' ? '买入' : '卖出'}</td>
                    <td className="py-1 text-white/70">{t.symbol}</td>
                    <td className="py-1 text-right text-white/60">{t.trade_price.toFixed(2)}</td>
                    <td className="py-1 text-right text-white/60">{t.quantity}</td>
                    <td className={cn('py-1 text-right font-medium', t.pnl != null ? (t.pnl >= 0 ? 'text-[#FF5F56]' : 'text-[#27C93F]') : 'text-white/40')}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}` : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Notes */}
      {notes.length > 0 && (
        <div>
          <div className="text-[10px] text-white/40 uppercase tracking-wider mb-1.5">备注</div>
          <div className="space-y-1">
            {notes.map((n, i) => (
              <div key={i} className="text-[11px] text-white/50">{n.text}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricItem({ label, value, positive }: { label: string; value: string; positive: boolean }) {
  return (
    <div>
      <div className="text-[10px] text-white/40 mb-1">{label}</div>
      <div className={cn('text-sm font-medium', positive ? 'text-[#FF5F56]' : 'text-[#27C93F]')}>{value}</div>
    </div>
  );
}

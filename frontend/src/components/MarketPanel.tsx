import type { MarketOverview } from '../api/types';
import { IndexCard } from './ui/IndexCard';

interface MarketPanelProps {
  market: MarketOverview;
}

export function MarketPanel({ market }: MarketPanelProps) {
  const breadth = market.breadth;
  const total = breadth?.total || 1;

  return (
    <div className="p-3 border-b border-white/10">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-white/70">市场概览</div>
        <div className="text-[10px] text-white/40">{market.trade_date}</div>
      </div>

      {/* Index Grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        {(market.indices ?? []).map((idx) => (
          <IndexCard
            key={idx.symbol ?? idx.name}
            name={idx.name}
            price={idx.close.toFixed(2)}
            change={`${idx.is_up ? '+' : ''}${idx.change_pct.toFixed(2)}%`}
            isUp={idx.is_up}
          />
        ))}
      </div>

      {/* Market Breadth Bar */}
      {breadth && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-[10px] text-white/40 mb-1">
            <span>涨跌分布</span>
            <span>{breadth.up_count} 涨 / {breadth.flat_count} 平 / {breadth.down_count} 跌</span>
          </div>
          <div className="flex h-1.5 rounded-full overflow-hidden bg-white/5">
            <div className="bg-[#FF5F56] rounded-l-full" style={{ width: `${(breadth.up_count / total) * 100}%` }} />
            <div className="bg-white/20" style={{ width: `${(breadth.flat_count / total) * 100}%` }} />
            <div className="bg-[#27C93F] rounded-r-full" style={{ width: `${(breadth.down_count / total) * 100}%` }} />
          </div>
        </div>
      )}

      {/* Daily Highlights */}
      {(market.highlights ?? []).length > 0 && (
        <div>
          <div className="text-[10px] text-white/40 mb-1.5">市场要点</div>
          <div className="space-y-1.5">
            {market.highlights.map((h, i) => (
              <MarketHighlightItem key={i} highlight={h} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MarketHighlightItem({ highlight }: { highlight: MarketOverview['highlights'][number] }) {
  if (typeof highlight === 'string') {
    return (
      <div className="text-[11px] text-white/60 leading-relaxed">
        <span className="text-white/80 font-medium">{highlight}</span>
      </div>
    );
  }

  return (
    <div className="text-[11px] text-white/60 leading-relaxed">
      <span className="text-white/80 font-medium">{highlight.title}</span>
      {highlight.detail && <span className="text-white/40"> - {highlight.detail}</span>}
    </div>
  );
}

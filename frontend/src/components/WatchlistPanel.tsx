import type { ScreenerSection } from '../api/types';
import { StockListItem } from './ui/StockListItem';

interface WatchlistPanelProps {
  screener: ScreenerSection;
  selectedStock: string | null;
  onSelectStock: (symbol: string) => void;
}

export function WatchlistPanel({ screener, selectedStock, onSelectStock }: WatchlistPanelProps) {
  const candidates = screener?.top_candidates ?? [];

  return (
    <div className="flex-1 p-3 overflow-y-auto hide-scrollbar">
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

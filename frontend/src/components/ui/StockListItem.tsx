import { cn } from '../../lib/cn';

interface StockListItemProps {
  name: string;
  code: string;
  score: number;
  selected: boolean;
  onClick: () => void;
  trendScore?: number | null;
  priceVolumeScore?: number | null;
  capitalScore?: number | null;
}

export function StockListItem({ name, code, score, selected, onClick, trendScore, priceVolumeScore, capitalScore }: StockListItemProps) {
  return (
    <div onClick={onClick} className={cn('p-2.5 rounded-lg cursor-pointer transition-all border', selected ? 'bg-blue-500/10 border-blue-500/30' : 'bg-transparent border-transparent hover:bg-white/5')}>
      <div className="flex justify-between items-center mb-1.5">
        <div className="flex items-center gap-2">
          <span className={cn('font-medium text-sm', selected ? 'text-blue-400' : 'text-white/90')}>{name}</span>
          <span className="text-[10px] text-white/40">{code}</span>
        </div>
        <div className="text-sm font-medium text-[#FF5F56]">{score}</div>
      </div>
      <div className="flex justify-between items-center">
        <div className="flex gap-2 text-[10px] text-white/40">
          <span>趋势 {trendScore ?? '--'}</span>
          <span>量价 {priceVolumeScore ?? '--'}</span>
          <span>资金 {capitalScore ?? '--'}</span>
        </div>
      </div>
    </div>
  );
}

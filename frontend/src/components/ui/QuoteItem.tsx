import { cn } from '../../lib/cn';

interface QuoteItemProps {
  label: string;
  value: string;
  highlight?: string;
}

export function QuoteItem({ label, value, highlight }: QuoteItemProps) {
  return (
    <div>
      <div className="text-[10px] text-white/40 mb-1">{label}</div>
      <div className={cn('text-lg font-medium', highlight || 'text-white/90')}>{value}</div>
    </div>
  );
}

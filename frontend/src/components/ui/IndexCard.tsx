import { cn } from '../../lib/cn';

interface IndexCardProps {
  name: string;
  price: string;
  change: string;
  isUp: boolean;
}

export function IndexCard({ name, price, change, isUp }: IndexCardProps) {
  return (
    <div className="bg-white/[0.03] rounded-lg p-2.5 border border-white/5">
      <div className="text-xs text-white/50 mb-1">{name}</div>
      <div className={cn('text-sm font-medium', isUp ? 'text-[#FF5F56]' : 'text-[#27C93F]')}>{price}</div>
      <div className={cn('text-[10px]', isUp ? 'text-[#FF5F56]/80' : 'text-[#27C93F]/80')}>{change}</div>
    </div>
  );
}

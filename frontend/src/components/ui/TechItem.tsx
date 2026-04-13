import { cn } from '../../lib/cn';

interface TechItemProps {
  label: string;
  value: string;
  isUp?: boolean | null;
}

export function TechItem({ label, value, isUp }: TechItemProps) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-white/50">{label}</span>
      <span className={cn('font-medium', isUp === true ? 'text-[#FF5F56]' : isUp === false ? 'text-[#27C93F]' : 'text-white/90')}>{value}</span>
    </div>
  );
}

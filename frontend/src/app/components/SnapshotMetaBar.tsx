import type { SnapshotResponse } from '../../api/types';

interface SnapshotMetaBarProps {
  snapshot: SnapshotResponse;
  label: string;
  modeLabel: string;
}

export function SnapshotMetaBar({ snapshot, label, modeLabel }: SnapshotMetaBarProps) {
  return (
    <div className="grid gap-2 border-b border-white/10 bg-black/10 p-3 text-[10px] text-white/45 md:grid-cols-4">
      <div>
        <div className="text-white/30">{label}</div>
        <div className="mt-0.5 text-white/70">{modeLabel}</div>
      </div>
      <div>
        <div className="text-white/30">snapshot_id</div>
        <div className="mt-0.5 truncate text-white/70">{snapshot.snapshot_id}</div>
      </div>
      <div>
        <div className="text-white/30">raw_snapshot_id</div>
        <div className="mt-0.5 truncate text-white/70">{snapshot.raw_snapshot_id}</div>
      </div>
      <div>
        <div className="text-white/30">price_basis / generated_at</div>
        <div className="mt-0.5 truncate text-white/70">
          {snapshot.price_basis} · {snapshot.generated_at}
        </div>
      </div>
    </div>
  );
}

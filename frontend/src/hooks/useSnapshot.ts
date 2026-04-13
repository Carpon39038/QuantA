import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { SnapshotResponse } from '../api/types';

export function useSnapshot() {
  const [data, setData] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.snapshot()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

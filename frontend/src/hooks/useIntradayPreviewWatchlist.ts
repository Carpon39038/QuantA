import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { IntradayPreviewWatchlistResponse } from '../api/types';

export function useIntradayPreviewWatchlist() {
  const [data, setData] = useState<IntradayPreviewWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    const clearTimer = () => {
      if (pollTimerRef.current != null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };

    const scheduleNext = (payload?: IntradayPreviewWatchlistResponse | null) => {
      clearTimer();
      const pollSeconds = payload?.source_status?.poll_interval_seconds ?? 15;
      pollTimerRef.current = window.setTimeout(
        () => {
          void fetchPreview();
        },
        Math.max(pollSeconds, 5) * 1000,
      );
    };

    const fetchPreview = async () => {
      try {
        const payload = await api.intradayPreviewWatchlist();
        if (cancelled) return;
        setData(payload);
        setError(null);
        scheduleNext(payload);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        scheduleNext(null);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchPreview();
    return () => {
      cancelled = true;
      clearTimer();
    };
  }, []);

  return { data, loading, error };
}

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { StrategyWatchlistItem, StrategyWatchlistResponse } from '../api/types';

export function useStrategyWatchlist() {
  const [data, setData] = useState<StrategyWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await api.strategyWatchlist();
      setData(payload);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const add = useCallback(async (symbol: string): Promise<StrategyWatchlistItem> => {
    setMutating(true);
    try {
      const payload = await api.addStrategyWatch(symbol);
      const refreshed = await api.strategyWatchlist();
      setData(refreshed);
      setError(null);
      return payload.item;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      throw new Error(message);
    } finally {
      setMutating(false);
    }
  }, []);

  const remove = useCallback(async (symbol: string): Promise<void> => {
    setMutating(true);
    try {
      await api.removeStrategyWatch(symbol);
      const refreshed = await api.strategyWatchlist();
      setData(refreshed);
      setError(null);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
      throw new Error(message);
    } finally {
      setMutating(false);
    }
  }, []);

  return {
    data,
    items: data?.items ?? [],
    loading,
    mutating,
    error,
    reload,
    add,
    remove,
  };
}

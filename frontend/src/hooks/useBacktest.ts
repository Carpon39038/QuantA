import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { EquityCurveResponse, TradesResponse } from '../api/types';

export interface BacktestDetail {
  equityCurve: EquityCurveResponse | null;
  trades: TradesResponse | null;
}

export function useBacktest() {
  const [data, setData] = useState<BacktestDetail>({ equityCurve: null, trades: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.equityCurve(), api.trades()])
      .then(([equityCurve, trades]) => setData({ equityCurve, trades }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

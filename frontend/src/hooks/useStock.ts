import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type {
  StockSnapshotResponse, KlineResponse, IndicatorsResponse,
  CapitalFlowResponse, FundamentalsResponse, DisclosuresResponse,
  PriceVolumeAnalysisResponse,
} from '../api/types';

export interface StockData {
  snapshot: StockSnapshotResponse | null;
  kline: KlineResponse | null;
  indicators: IndicatorsResponse | null;
  capitalFlow: CapitalFlowResponse | null;
  fundamentals: FundamentalsResponse | null;
  disclosures: DisclosuresResponse | null;
  priceVolumeAnalysis: PriceVolumeAnalysisResponse | null;
}

export function useStock(symbol: string | null) {
  const [data, setData] = useState<StockData>({
    snapshot: null, kline: null, indicators: null,
    capitalFlow: null, fundamentals: null, disclosures: null,
    priceVolumeAnalysis: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError(null);

    Promise.all([
      api.stockSnapshot(symbol),
      api.stockKline(symbol),
      api.stockIndicators(symbol),
      api.stockCapitalFlow(symbol),
      api.stockFundamentals(symbol),
      api.stockDisclosures(symbol),
      api.stockPriceVolumeAnalysis(symbol),
    ])
      .then(([
        snapshot,
        kline,
        indicators,
        capitalFlow,
        fundamentals,
        disclosures,
        priceVolumeAnalysis,
      ]) => {
        setData({
          snapshot,
          kline,
          indicators,
          capitalFlow,
          fundamentals,
          disclosures,
          priceVolumeAnalysis,
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [symbol]);

  return { data, loading, error };
}

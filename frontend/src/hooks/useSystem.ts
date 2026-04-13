import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { AlertsResponse } from '../api/types';

export function useSystem() {
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.alerts()
      .then(setAlerts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { alerts, loading, error };
}

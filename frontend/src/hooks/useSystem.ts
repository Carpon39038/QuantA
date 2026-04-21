import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { AlertsResponse } from '../api/types';

export function useSystem() {
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const seenAlertKeysRef = useRef<Set<string>>(new Set());
  const hasBootstrappedAlertsRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const fetchAlerts = async () => {
      try {
        const payload = await api.alerts();
        if (cancelled) return;
        setAlerts(payload);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchAlerts();
    const timer = window.setInterval(() => {
      void fetchAlerts();
    }, 15_000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!alerts || typeof window === 'undefined' || !('Notification' in window)) {
      return;
    }

    if (window.Notification.permission === 'default') {
      void window.Notification.requestPermission().catch(() => undefined);
    }

    if (!hasBootstrappedAlertsRef.current) {
      for (const alert of alerts.items ?? []) {
        const alertKey = [
          alert.triggered_at,
          alert.alert_type,
          alert.message,
        ].join('::');
        seenAlertKeysRef.current.add(alertKey);
      }
      hasBootstrappedAlertsRef.current = true;
      return;
    }

    for (const alert of alerts.items ?? []) {
      const alertKey = [
        alert.triggered_at,
        alert.alert_type,
        alert.message,
      ].join('::');
      if (seenAlertKeysRef.current.has(alertKey)) {
        continue;
      }
      seenAlertKeysRef.current.add(alertKey);
      if (
        window.Notification.permission === 'granted'
        && alert.alert_type.startsWith('intraday_')
        && (alert.severity === 'WARNING' || alert.severity === 'ERROR')
      ) {
        new window.Notification('QuantA 实盘提醒', {
          body: alert.message,
        });
      }
    }
  }, [alerts]);

  return { alerts, loading, error };
}

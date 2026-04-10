import { useState, useEffect, useCallback } from 'react';
import {
  fetchGovernanceSettings,
  updateGovernanceSettings,
  type GovernanceSettings,
} from '../api/governance';

export function useGovernanceSettings() {
  const [settings, setSettings] = useState<GovernanceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchGovernanceSettings();
      setSettings(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch settings');
    } finally {
      setLoading(false);
    }
  }, []);

  const update = useCallback(async (patch: Partial<GovernanceSettings>) => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await updateGovernanceSettings({ ...settings, ...patch });
      setSettings(updated);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  }, [settings]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { settings, loading, saving, error, update, refresh };
}

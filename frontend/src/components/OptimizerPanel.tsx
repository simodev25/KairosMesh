import { useCallback, useEffect, useRef, useState } from 'react';
import { Zap, Loader2, Check, X, Ban } from 'lucide-react';
import { api } from '../api/client';

interface OptimizerCampaign {
  id: number;
  strategy_id: number;
  status: string;
  current_iteration: number;
  max_iterations: number;
  best_score: number | null;
  best_params: Record<string, unknown> | null;
  initial_params: Record<string, unknown>;
  initial_score: number | null;
  best_metrics: Record<string, unknown> | null;
  elapsed_seconds: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

interface OptimizerPanelProps {
  strategyId: number;
  strategyStatus: string;
  token: string;
  onStrategyUpdated: () => void;
}

export function OptimizerPanel({ strategyId, strategyStatus, token, onStrategyUpdated }: OptimizerPanelProps) {
  const [campaign, setCampaign] = useState<OptimizerCampaign | null>(null);
  const [loading, setLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [maxIterations, setMaxIterations] = useState(50);
  const [timeBudget, setTimeBudget] = useState(300);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const fetchCampaign = useCallback(async () => {
    try {
      const data = await api.getOptimizerCampaign(token, strategyId) as OptimizerCampaign;
      setCampaign(data);
      return data;
    } catch {
      setCampaign(null);
      return null;
    }
  }, [token, strategyId]);

  // Initial load
  useEffect(() => {
    void fetchCampaign();
  }, [fetchCampaign]);

  // Polling when campaign is active
  useEffect(() => {
    if (campaign && (campaign.status === 'RUNNING' || campaign.status === 'PENDING')) {
      pollRef.current = window.setInterval(() => {
        void fetchCampaign();
      }, 4000);
    } else if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [campaign?.status, fetchCampaign]);

  const launchOptimization = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.launchOptimizer(token, strategyId, {
        max_iterations: maxIterations,
        time_budget_seconds: timeBudget,
      }) as OptimizerCampaign;
      setCampaign(data);
      setShowConfig(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to launch optimizer');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!campaign) return;
    setLoading(true);
    try {
      await api.acceptCampaign(token, campaign.id);
      onStrategyUpdated();
      await fetchCampaign();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Accept failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!campaign) return;
    setLoading(true);
    try {
      await api.rejectCampaign(token, campaign.id);
      await fetchCampaign();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reject failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!campaign) return;
    setLoading(true);
    try {
      await api.cancelCampaign(token, campaign.id);
      await fetchCampaign();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancel failed');
    } finally {
      setLoading(false);
    }
  };

  const canLaunch = ['VALIDATED', 'STRATEGY_DISCARDED'].includes(strategyStatus) && (!campaign || !['RUNNING', 'PENDING'].includes(campaign.status));
  const isActive = campaign && ['RUNNING', 'PENDING'].includes(campaign.status);
  const isCompleted = campaign?.status === 'COMPLETED';
  const progressPct = campaign && campaign.max_iterations > 0
    ? Math.round((campaign.current_iteration / campaign.max_iterations) * 100)
    : 0;

  return (
    <div className="mt-2">
      {/* Launch Button */}
      {canLaunch && !showConfig && (
        <button
          className="btn-ghost text-[9px] flex items-center gap-1 text-purple-400 border-purple-500/30 hover:bg-purple-500/10"
          onClick={() => setShowConfig(true)}
          disabled={loading}
        >
          <Zap className="w-3 h-3" /> OPTIMISER
        </button>
      )}

      {/* Config Modal */}
      {showConfig && (
        <div className="hw-surface-alt p-3 space-y-2 border border-purple-500/20 rounded">
          <span className="text-[8px] font-mono text-purple-400 uppercase tracking-widest">OPTIMIZER_CONFIG</span>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[7px] font-mono text-text-dim block">Max Iterations</label>
              <input
                type="number"
                value={maxIterations}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
                min={1}
                max={200}
                className="w-full text-[10px] bg-surface-alt border border-border rounded px-2 py-1 text-text font-mono"
              />
            </div>
            <div>
              <label className="text-[7px] font-mono text-text-dim block">Time Budget (s)</label>
              <input
                type="number"
                value={timeBudget}
                onChange={(e) => setTimeBudget(Number(e.target.value))}
                min={10}
                max={1800}
                className="w-full text-[10px] bg-surface-alt border border-border rounded px-2 py-1 text-text font-mono"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-primary text-[9px] flex items-center gap-1" onClick={launchOptimization} disabled={loading}>
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              LANCER
            </button>
            <button className="btn-ghost text-[9px]" onClick={() => setShowConfig(false)} disabled={loading}>ANNULER</button>
          </div>
        </div>
      )}

      {/* Progress */}
      {isActive && campaign && (
        <div className="hw-surface-alt p-3 space-y-2 border border-purple-500/20 rounded">
          <div className="flex items-center justify-between">
            <span className="text-[8px] font-mono text-purple-400 flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              OPTIMISATION_EN_COURS
            </span>
            <button className="text-[8px] text-red-400 hover:text-red-300" onClick={handleCancel} disabled={loading}>
              <Ban className="w-3 h-3 inline mr-0.5" />ANNULER
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className="h-full rounded-full bg-purple-500 transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-[9px] font-mono text-text">{campaign.current_iteration}/{campaign.max_iterations}</span>
          </div>
          {campaign.best_score != null && (
            <div className="text-[8px] font-mono text-text-dim">
              Best Score: <span className="text-text font-bold">{campaign.best_score.toFixed(2)}</span>
              {campaign.initial_score != null && (
                <span className="ml-2 text-text-dim">
                  (initial: {campaign.initial_score.toFixed(2)}, Δ{(campaign.best_score - campaign.initial_score).toFixed(2)})
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {isCompleted && campaign && (
        <div className="hw-surface-alt p-3 space-y-2 border border-green-500/20 rounded">
          <span className="text-[8px] font-mono text-green-400 uppercase tracking-widest">OPTIMISATION_TERMINÉE</span>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-[7px] font-mono text-text-dim block">Score Initial</span>
              <span className="text-[11px] font-mono font-bold text-text">{campaign.initial_score?.toFixed(2) ?? '--'}</span>
            </div>
            <div>
              <span className="text-[7px] font-mono text-text-dim block">Best Score</span>
              <span className="text-[11px] font-mono font-bold text-green-400">{campaign.best_score?.toFixed(2) ?? '--'}</span>
            </div>
          </div>
          {campaign.best_params && campaign.initial_params && (
            <div className="text-[8px] font-mono space-y-0.5">
              <span className="text-text-dim">Params delta:</span>
              {Object.entries(campaign.best_params).map(([key, val]) => {
                const initial = campaign.initial_params[key];
                const changed = String(val) !== String(initial);
                return changed ? (
                  <div key={key} className="pl-2 text-accent">
                    {key}: {String(initial)} → {String(val)}
                  </div>
                ) : null;
              })}
            </div>
          )}
          <div className="flex items-center gap-2 pt-1">
            <button className="btn-primary text-[9px] flex items-center gap-1" onClick={handleAccept} disabled={loading}>
              <Check className="w-3 h-3" /> APPLIQUER
            </button>
            <button className="btn-ghost text-[9px] flex items-center gap-1 text-red-400" onClick={handleReject} disabled={loading}>
              <X className="w-3 h-3" /> REJETER
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && <p className="text-[8px] text-red-400 mt-1">{error}</p>}

      {/* Failed campaign */}
      {campaign?.status === 'FAILED' && (
        <div className="text-[8px] font-mono text-red-400 mt-1">
          OPTIMISATION_ÉCHOUÉE: {campaign.error_message || 'Unknown error'}
        </div>
      )}
    </div>
  );
}

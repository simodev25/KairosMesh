import { ExpansionPanel } from '../../components/ExpansionPanel';
import type { BenchmarkRunDetail } from '../../types/benchmark';
import { formatBenchmarkScore, getBenchmarkScoreClass } from '../../utils/benchmarkScores';

interface RunDetailPanelProps {
  runDetail: BenchmarkRunDetail | null;
  loading: boolean;
  error: string | null;
}

export function RunDetailPanel({ runDetail, loading, error }: RunDetailPanelProps) {
  return (
    <ExpansionPanel title="RUN_DETAIL" id="benchmark-run-detail" defaultOpen={false}>
      {loading && <p className="text-[11px] text-text-dim">Chargement du détail run…</p>}
      {error && <p className="alert">{error}</p>}
      {!loading && !error && !runDetail && (
        <p className="text-[11px] text-text-dim">Aucun run sélectionné.</p>
      )}
      {!loading && !error && runDetail && (
        <div className="space-y-4">
          {runDetail.cases.map((benchmarkCase) => (
            <div key={benchmarkCase.id} className="hw-surface-alt p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold text-text">Case #{benchmarkCase.case_order} — {benchmarkCase.agent_name}</span>
                <span className={`text-[11px] font-semibold ${getBenchmarkScoreClass(benchmarkCase.aggregate_score ?? 0)}`}>
                  Score: {formatBenchmarkScore(benchmarkCase.aggregate_score)}
                </span>
              </div>
              <div className="space-y-3">
                {benchmarkCase.attempts.map((attempt) => (
                  <div key={attempt.id} className="border border-border rounded p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] text-text">Attempt #{attempt.attempt_number}</span>
                      <span className={`text-[10px] font-semibold ${getBenchmarkScoreClass(attempt.aggregate_score)}`}>
                        Global: {formatBenchmarkScore(attempt.aggregate_score)}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[10px]">
                      <span className="text-text-dim">Statut: <strong className="text-text">{attempt.aggregate_score >= 0.7 ? 'OK' : 'À vérifier'}</strong></span>
                      <span className="text-text-dim">Latence: <strong className="text-text">N/A (non exposé par GH-24)</strong></span>
                      <span className="text-text-dim">Schema: <strong className={getBenchmarkScoreClass(attempt.schema_validity_score)}>{formatBenchmarkScore(attempt.schema_validity_score)}</strong></span>
                      <span className="text-text-dim">Complétude: <strong className={getBenchmarkScoreClass(attempt.completeness_score)}>{formatBenchmarkScore(attempt.completeness_score)}</strong></span>
                      <span className="text-text-dim">Policy: <strong className={getBenchmarkScoreClass(attempt.tool_policy_compliance_score)}>{formatBenchmarkScore(attempt.tool_policy_compliance_score)}</strong></span>
                      <span className="text-text-dim">Référence: <strong className={getBenchmarkScoreClass(attempt.reference_consistency_score)}>{formatBenchmarkScore(attempt.reference_consistency_score)}</strong></span>
                      <span className="text-text-dim">Stabilité: <strong className={getBenchmarkScoreClass(attempt.stability_score ?? 0)}>{formatBenchmarkScore(attempt.stability_score)}</strong></span>
                      <span className="text-text-dim">LLM calls: <strong className="text-text">{attempt.llm_calls_count}</strong></span>
                    </div>
                    <details className="trace-details mt-2">
                      <summary>Raw output</summary>
                      <pre className="json-view">{JSON.stringify(attempt.raw_output, null, 2)}</pre>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </ExpansionPanel>
  );
}

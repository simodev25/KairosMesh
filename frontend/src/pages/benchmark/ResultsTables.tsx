import type { BenchmarkRun, BenchmarkRunDetail, BenchmarkRunResults } from '../../types/benchmark';
import {
  BENCHMARK_METRIC_KEYS,
  BENCHMARK_METRIC_LABELS,
  computeBenchmarkRunScores,
  formatBenchmarkScore,
  getBenchmarkScoreClass,
} from '../../utils/benchmarkScores';

interface ResultsTableProps {
  selectedRun: BenchmarkRun | null;
  runDetail: BenchmarkRunDetail | null;
  loading: boolean;
  error: string | null;
  runResults: BenchmarkRunResults | null;
  runResultsNotice: string | null;
}

interface ComparisonTableProps {
  runs: BenchmarkRun[];
  runDetailsById: Record<number, BenchmarkRunDetail>;
  comparisonIds: number[];
  onClose: () => void;
}

function modelLabel(run: BenchmarkRun): string {
  const provider = typeof run.model_spec.provider === 'string' ? run.model_spec.provider : '--';
  const modelName = typeof run.model_spec.model_name === 'string' ? run.model_spec.model_name : '--';
  return `${provider}/${modelName}`;
}

export function ResultsTable({ selectedRun, runDetail, loading, error, runResults, runResultsNotice }: ResultsTableProps) {
  if (!selectedRun) {
    return <p className="text-[11px] text-text-dim">Sélectionnez un run pour afficher les résultats.</p>;
  }
  if (loading) {
    return <p className="text-[11px] text-text-dim">Chargement des résultats…</p>;
  }
  if (error) {
    return <p className="alert">{error}</p>;
  }
  if (!runDetail) {
    return <p className="text-[11px] text-text-dim">Détail run indisponible.</p>;
  }

  const scores = computeBenchmarkRunScores(runDetail);
  const endpointRow = runResults?.rows[0];
  const endpointScores = endpointRow?.scores ?? null;
  const effectiveScores = endpointScores ?? scores;

  return (
    <div className="hw-surface p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
        <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">RÉSULTATS_V1</span>
        <span className="text-[10px] text-text-dim">Run #{selectedRun.id} — {modelLabel(selectedRun)}</span>
      </div>
      {runResultsNotice && (
        <div className="px-5 pt-3">
          <p className="text-[10px] text-text-dim">{runResultsNotice}</p>
        </div>
      )}
      <div className="p-5 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              {BENCHMARK_METRIC_KEYS.map((metricKey) => (
                <th key={metricKey} className="px-3 py-2">
                  {BENCHMARK_METRIC_LABELS[metricKey]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border/30">
              {BENCHMARK_METRIC_KEYS.map((metricKey) => {
                const value = effectiveScores[metricKey];
                return (
                  <td key={metricKey} className={`px-3 py-2 text-[11px] font-semibold ${getBenchmarkScoreClass(value)}`}>
                    {formatBenchmarkScore(value)}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ComparisonTable({ runs, runDetailsById, comparisonIds, onClose }: ComparisonTableProps) {
  const selectedRuns = comparisonIds
    .map((id) => runs.find((run) => run.id === id) ?? null)
    .filter((run): run is BenchmarkRun => run !== null)
    .filter((run) => runDetailsById[run.id] !== undefined);

  if (selectedRuns.length < 2) {
    return null;
  }

  const scoresByRunId = Object.fromEntries(
    selectedRuns.map((run) => [run.id, computeBenchmarkRunScores(runDetailsById[run.id])]),
  ) as Record<number, ReturnType<typeof computeBenchmarkRunScores>>;

  return (
    <div className="hw-surface p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
        <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">COMPARAISON_MODÈLES</span>
        <button type="button" className="btn-ghost ml-auto" onClick={onClose} aria-label="Fermer la comparaison des modèles">
          RETOUR
        </button>
      </div>
      <div className="p-5 overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2">Métrique</th>
              {selectedRuns.map((run) => (
                <th key={run.id} className="px-3 py-2">
                  {modelLabel(run)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {BENCHMARK_METRIC_KEYS.map((metricKey) => {
              const bestValue = Math.max(...selectedRuns.map((run) => scoresByRunId[run.id][metricKey]));
              return (
                <tr key={metricKey} className="border-b border-border/30">
                  <td className="px-3 py-2 text-[11px] text-text">{BENCHMARK_METRIC_LABELS[metricKey]}</td>
                  {selectedRuns.map((run) => {
                    const value = scoresByRunId[run.id][metricKey];
                    const isBest = value === bestValue;
                    return (
                      <td
                        key={`${run.id}-${metricKey}`}
                        className={`px-3 py-2 text-[11px] font-semibold ${getBenchmarkScoreClass(value)} ${isBest ? 'border border-accent/40 rounded' : ''}`}
                      >
                        {formatBenchmarkScore(value)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

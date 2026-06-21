import type { BenchmarkRun } from '../../types/benchmark';

interface RunsTableProps {
  runs: BenchmarkRun[];
  loading: boolean;
  selectedRunId: number | null;
  comparisonIds: number[];
  onRefreshRuns: () => void;
  onSelectRun: (runId: number) => void;
  onToggleCompare: (runId: number) => void;
  onOpenCompare: () => void;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function RunsTable({
  runs,
  loading,
  selectedRunId,
  comparisonIds,
  onRefreshRuns,
  onSelectRun,
  onToggleCompare,
  onOpenCompare,
}: RunsTableProps) {
  return (
    <div className="hw-surface p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
        <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">RUNS</span>
        <button
          type="button"
          className="btn-ghost"
          onClick={onRefreshRuns}
          aria-label="Rafraîchir la liste des runs"
        >
          ↻ RAFRAÎCHIR
        </button>
        <button
          type="button"
          className="btn-ghost ml-auto"
          disabled={comparisonIds.length < 2}
          onClick={onOpenCompare}
          aria-label="Comparer les modèles sélectionnés"
        >
          COMPARER ({comparisonIds.length})
        </button>
      </div>
      <div className="p-5">
        {loading ? (
          <p className="text-[11px] text-text-dim">Chargement des runs…</p>
        ) : runs.length === 0 ? (
          <p className="text-[11px] text-text-dim">Aucun run pour cette fixture.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-3 py-2">Compare</th>
                  <th className="px-3 py-2">Run</th>
                  <th className="px-3 py-2">Modèle</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const provider = typeof run.model_spec.provider === 'string' ? run.model_spec.provider : '--';
                  const modelName = typeof run.model_spec.model_name === 'string' ? run.model_spec.model_name : '--';
                  const selected = run.id === selectedRunId;
                  const checked = comparisonIds.includes(run.id);
                  return (
                    <tr key={run.id} className="border-b border-border/30 hover:bg-surface-alt/30">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggleCompare(run.id)}
                          aria-label={`Ajouter le run ${run.id} à la comparaison`}
                        />
                      </td>
                      <td className="px-3 py-2 text-[11px] text-text">#{run.id}</td>
                      <td className="px-3 py-2 text-[11px] text-text-dim">{provider}/{modelName}</td>
                      <td className="px-3 py-2 text-[11px] text-text-dim">{run.status}</td>
                      <td className="px-3 py-2 text-[11px] text-text-dim">{formatDate(run.created_at)}</td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          className={`btn-ghost ${selected ? 'text-accent border-accent/30' : ''}`}
                          onClick={() => onSelectRun(run.id)}
                          aria-label={`Voir les résultats du run ${run.id}`}
                        >
                          {selected ? 'SÉLECTIONNÉ' : 'VOIR'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

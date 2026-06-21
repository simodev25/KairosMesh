import type { BenchmarkFixture } from '../../types/benchmark';

interface FixturesTableProps {
  fixtures: BenchmarkFixture[];
  selectedFixtureId: number | null;
  loading: boolean;
  error: string | null;
  onSelectFixture: (fixtureId: number) => void;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function FixturesTable({
  fixtures,
  selectedFixtureId,
  loading,
  error,
  onSelectFixture,
}: FixturesTableProps) {
  if (loading) {
    return <p className="text-[11px] text-text-dim">Chargement des fixtures…</p>;
  }

  if (error) {
    return <p className="alert">{error}</p>;
  }

  if (fixtures.length === 0) {
    return <p className="text-[11px] text-text-dim">Aucune fixture disponible</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="px-3 py-2">Nom</th>
            <th className="px-3 py-2">Agent</th>
            <th className="px-3 py-2">Scenario</th>
            <th className="px-3 py-2">Créée le</th>
            <th className="px-3 py-2">Action</th>
          </tr>
        </thead>
        <tbody>
          {fixtures.map((fixture) => {
            const scenarioType = typeof fixture.config?.scenario_type === 'string'
              ? fixture.config.scenario_type
              : 'single-agent';
            const isSelected = fixture.id === selectedFixtureId;
            return (
              <tr key={fixture.id} className="border-b border-border/30 hover:bg-surface-alt/30">
                <td className="px-3 py-2 text-[11px] text-text">{fixture.name}</td>
                <td className="px-3 py-2 text-[11px] text-text-dim">{fixture.agent_name}</td>
                <td className="px-3 py-2 text-[11px] text-text-dim">{scenarioType}</td>
                <td className="px-3 py-2 text-[11px] text-text-dim">{formatDate(fixture.created_at)}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className={`btn-ghost ${isSelected ? 'text-accent border-accent/30' : ''}`}
                    onClick={() => onSelectFixture(fixture.id)}
                    aria-label={`Sélectionner la fixture ${fixture.name}`}
                  >
                    {isSelected ? 'SÉLECTIONNÉE' : 'SÉLECTIONNER'}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

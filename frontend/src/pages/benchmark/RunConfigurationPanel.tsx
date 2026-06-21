import { Plus, Trash2, Play } from 'lucide-react';
import { ButtonSpinner } from '../../components/LoadingIndicators';
import type { BenchmarkFixture, BenchmarkRun, ModelSpec } from '../../types/benchmark';

const PROVIDER_OPTIONS = ['ollama', 'openai', 'mistral'] as const;
const CUSTOM_MODEL_VALUE = '__custom__';

interface RunConfigurationPanelProps {
  fixtures: BenchmarkFixture[];
  selectedFixtureId: number | null;
  modelSpecs: ModelSpec[];
  modelChoicesByProvider: Record<string, string[]>;
  modelChoicesLoadingByProvider: Record<string, boolean>;
  repeatCount: string;
  tagsInput: string;
  submittingRun: boolean;
  submitError: string | null;
  runs: BenchmarkRun[];
  onFixtureChange: (fixtureId: number) => void;
  onModelSpecChange: (index: number, field: keyof ModelSpec, value: string) => void;
  onAddModelSpec: () => void;
  onRemoveModelSpec: (index: number) => void;
  onRepeatCountChange: (value: string) => void;
  onTagsChange: (value: string) => void;
  onSubmit: () => void;
}

function getFieldValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

export function RunConfigurationPanel({
  fixtures,
  selectedFixtureId,
  modelSpecs,
  modelChoicesByProvider,
  modelChoicesLoadingByProvider,
  repeatCount,
  tagsInput,
  submittingRun,
  submitError,
  runs,
  onFixtureChange,
  onModelSpecChange,
  onAddModelSpec,
  onRemoveModelSpec,
  onRepeatCountChange,
  onTagsChange,
  onSubmit,
}: RunConfigurationPanelProps) {
  return (
    <div className="hw-surface p-0 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
        <Play className="w-3.5 h-3.5 text-accent" />
        <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">RUN_CONFIGURATION</span>
      </div>
      <div className="p-5 flex flex-col gap-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="micro-label block mb-1.5" htmlFor="benchmark-fixture-select">Fixture</label>
            <select
              id="benchmark-fixture-select"
              value={selectedFixtureId ?? ''}
              onChange={(event) => onFixtureChange(Number(event.target.value))}
              aria-label="Sélection de la fixture benchmark"
            >
              <option value="" disabled>Choisir une fixture</option>
              {fixtures.map((fixture) => (
                <option key={fixture.id} value={fixture.id}>
                  {fixture.name} ({fixture.agent_name})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="micro-label block mb-1.5" htmlFor="benchmark-repeat-count">Repeat count</label>
            <input
              id="benchmark-repeat-count"
              type="number"
              min={2}
              value={repeatCount}
              onChange={(event) => onRepeatCountChange(event.target.value)}
              aria-label="Nombre de répétitions"
            />
          </div>
          <div>
            <label className="micro-label block mb-1.5" htmlFor="benchmark-tags">Tags</label>
            <input
              id="benchmark-tags"
              type="text"
              value={tagsInput}
              onChange={(event) => onTagsChange(event.target.value)}
              placeholder="ex: nightly, regression"
              aria-label="Tags du run benchmark"
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="micro-label">Model specs</span>
          <button
            type="button"
            className="btn-ghost"
            onClick={onAddModelSpec}
            aria-label="Ajouter un modèle à benchmarker"
          >
            <Plus className="w-3.5 h-3.5" /> AJOUTER MODÈLE
          </button>
        </div>

        <div className="space-y-2">
          {modelSpecs.map((spec, index) => (
            <div key={`${index}-${getFieldValue(spec.provider)}-${getFieldValue(spec.model_name)}`} className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
              {(() => {
                const provider = getFieldValue(spec.provider).trim().toLowerCase();
                const modelName = getFieldValue(spec.model_name);
                const providerChoices = modelChoicesByProvider[provider] ?? [];
                const providerLoading = Boolean(modelChoicesLoadingByProvider[provider]);
                const hasChoices = providerChoices.length > 0;
                const isCustomModel = modelName.length > 0 && !providerChoices.includes(modelName);

                return (
                  <>
              <div>
                <label className="micro-label block mb-1.5" htmlFor={`provider-${index}`}>Provider</label>
                <select
                  id={`provider-${index}`}
                  value={getFieldValue(spec.provider)}
                  onChange={(event) => onModelSpecChange(index, 'provider', event.target.value)}
                  aria-label={`Provider modèle ${index + 1}`}
                >
                  {PROVIDER_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="micro-label block mb-1.5" htmlFor={`model-name-${index}`}>Model name</label>
                <select
                  id={`model-name-${index}`}
                  value={isCustomModel ? CUSTOM_MODEL_VALUE : modelName}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    if (nextValue === CUSTOM_MODEL_VALUE) {
                      if (!isCustomModel && modelName.length === 0) {
                        onModelSpecChange(index, 'model_name', '');
                      }
                      return;
                    }
                    onModelSpecChange(index, 'model_name', nextValue);
                  }}
                  aria-label={`Nom du modèle ${index + 1}`}
                >
                  {providerLoading ? <option value="">Chargement...</option> : null}
                  {!providerLoading && !hasChoices ? <option value="">Aucun modèle disponible</option> : null}
                  {!providerLoading && hasChoices
                    ? providerChoices.map((choice) => (
                      <option key={choice} value={choice}>{choice}</option>
                    ))
                    : null}
                  <option value={CUSTOM_MODEL_VALUE}>Autre...</option>
                </select>
                {isCustomModel || (!providerLoading && !hasChoices) ? (
                  <input
                    className="mt-1.5"
                    type="text"
                    value={modelName}
                    onChange={(event) => onModelSpecChange(index, 'model_name', event.target.value)}
                    placeholder="Saisir un nom de modèle"
                    aria-label={`Nom libre du modèle ${index + 1}`}
                  />
                ) : null}
              </div>
              <div>
                <label className="micro-label block mb-1.5" htmlFor={`temperature-${index}`}>Temperature</label>
                <input
                  id={`temperature-${index}`}
                  type="number"
                  step="0.1"
                  value={typeof spec.parameters?.temperature === 'number' ? String(spec.parameters.temperature) : ''}
                  onChange={(event) => onModelSpecChange(index, 'parameters', event.target.value)}
                  aria-label={`Température modèle ${index + 1}`}
                />
              </div>
              <div>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={modelSpecs.length <= 1}
                  onClick={() => onRemoveModelSpec(index)}
                  aria-label={`Retirer le modèle ${index + 1}`}
                >
                  <Trash2 className="w-3.5 h-3.5" /> RETIRER
                </button>
              </div>
                  </>
                );
              })()}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={submittingRun}
            onClick={onSubmit}
            aria-label="Lancer un run benchmark"
          >
            {submittingRun ? (
              <>
                <ButtonSpinner /> LANCEMENT...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" /> LANCER RUN
              </>
            )}
          </button>
          <span className="text-[10px] text-text-dim">Runs disponibles: {runs.length}</span>
        </div>

        {submitError && <p className="alert">{submitError}</p>}
      </div>
    </div>
  );
}

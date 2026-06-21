import { FlaskConical } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { FixturesTable } from './benchmark/FixturesTable';
import { CreateFixturePanel } from './benchmark/CreateFixturePanel';
import { RunConfigurationPanel } from './benchmark/RunConfigurationPanel';
import { RunsTable } from './benchmark/RunsTable';
import { ComparisonTable, ResultsTable } from './benchmark/ResultsTables';
import { RunDetailPanel } from './benchmark/RunDetailPanel';
import { useBenchmarkPageState } from './benchmark/useBenchmarkPageState';

export function BenchmarkPage() {
  const { token, user } = useAuth();
  const state = useBenchmarkPageState(token, user?.role ?? null);

  return (
    <div className="flex flex-col gap-5">
      <div className="hw-surface p-0 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
          <FlaskConical className="w-3.5 h-3.5 text-accent" />
          <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">BENCHMARK</span>
          <span className="text-[10px] text-text-dim">Dashboard fixtures, runs, scores V1 et comparaison modèles</span>
        </div>
      </div>

      <div className="hw-surface p-0 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
          <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">FIXTURES</span>
        </div>
        <div className="p-5">
          <CreateFixturePanel
            open={state.showCreateFixtureForm}
            fixtureName={state.fixtureName}
            fixtureAgentName={state.fixtureAgentName}
            fixturePresetId={state.fixturePresetId}
            fixtureInputsText={state.fixtureInputsText}
            fixtureConfigText={state.fixtureConfigText}
            createFixtureSubmitting={state.createFixtureSubmitting}
            createFixtureError={state.createFixtureError}
            fixtureInputsError={state.fixtureInputsError}
            fixtureConfigError={state.fixtureConfigError}
            onToggleOpen={() => {
              if (state.showCreateFixtureForm) {
                state.handleCancelCreateFixture();
              } else {
                state.setShowCreateFixtureForm(true);
              }
            }}
            onNameChange={state.setFixtureName}
            onAgentChange={state.handleFixtureAgentChange}
            onPresetChange={state.handleFixturePresetChange}
            onInputsChange={state.setFixtureInputsText}
            onConfigChange={state.setFixtureConfigText}
            onCreate={() => {
              void state.handleCreateFixture();
            }}
            onCancel={state.handleCancelCreateFixture}
            canManage={state.canManage}
          />

          {!state.canManage ? (
            <p className="mt-3 text-[11px] text-text-dim">Lecture seule — rôle admin requis pour créer</p>
          ) : null}

          <div className="mt-4">
            <FixturesTable
              fixtures={state.fixtures}
              selectedFixtureId={state.selectedFixtureId}
              loading={state.fixturesLoading}
              error={state.fixturesError}
              onSelectFixture={state.handleSelectFixture}
            />
          </div>
        </div>
      </div>

      {state.canManage ? (
        <RunConfigurationPanel
          fixtures={state.fixtures}
          selectedFixtureId={state.selectedFixtureId}
          modelSpecs={state.modelSpecs}
          modelChoicesByProvider={state.modelChoicesByProvider}
          modelChoicesLoadingByProvider={state.modelChoicesLoadingByProvider}
          repeatCount={state.repeatCount}
          tagsInput={state.tagsInput}
          submittingRun={state.submittingRun}
          submitError={state.submitError}
          runs={state.runs}
          onFixtureChange={(fixtureId) => {
            state.setSelectedFixtureId(fixtureId);
          }}
          onModelSpecChange={state.handleModelSpecChange}
          onAddModelSpec={() =>
            state.setModelSpecs((prev) => [
              ...prev,
              { provider: 'openai', model_name: 'gpt-4o-mini', parameters: { temperature: 0 } },
            ])
          }
          onRemoveModelSpec={(index) => state.setModelSpecs((prev) => prev.filter((_, idx) => idx !== index))}
          onRepeatCountChange={state.setRepeatCount}
          onTagsChange={state.setTagsInput}
          onSubmit={state.handleSubmitRun}
        />
      ) : (
        <div className="hw-surface p-5">
          <p className="text-[11px] text-text-dim">Lecture seule — rôle admin requis pour créer</p>
        </div>
      )}

      <RunsTable
        runs={state.runs}
        loading={state.runsLoading}
        selectedRunId={state.selectedRunId}
        comparisonIds={state.comparisonIds}
        onRefreshRuns={() => {
          void state.loadRuns(state.selectedFixtureId);
        }}
        onSelectRun={state.setSelectedRunId}
        onToggleCompare={(runId) => {
          void state.toggleCompare(runId);
        }}
        onOpenCompare={() => state.setComparisonOpen(true)}
      />

      {state.runsError && <p className="alert">{state.runsError}</p>}

      {state.comparisonOpen ? (
        <ComparisonTable
          runs={state.runs}
          runDetailsById={state.comparisonDetailsById}
          comparisonIds={state.comparisonIds}
          onClose={() => state.setComparisonOpen(false)}
        />
      ) : (
        <ResultsTable
          selectedRun={state.selectedRun}
          runDetail={state.runDetail}
          loading={state.runDetailLoading}
          error={state.runDetailError}
          runResults={state.runResults}
          runResultsNotice={state.runResultsNotice}
        />
      )}

      <RunDetailPanel
        runDetail={state.runDetail}
        loading={state.runDetailLoading}
        error={state.runDetailError}
      />

      <div className="hw-surface p-0 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border">
          <span className="text-[11px] font-bold tracking-[0.12em] text-accent uppercase">PROCHAINES_SECTIONS</span>
        </div>
        <div className="p-5">
          <p className="text-[11px] text-text-dim">
            Vérifier version bump/changelog et alignement final AC/NFR avant création de PR.
          </p>
        </div>
      </div>
    </div>
  );
}

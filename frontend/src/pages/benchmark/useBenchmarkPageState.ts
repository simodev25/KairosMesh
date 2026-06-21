import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type {
  BenchmarkCreateFixturePayload,
  BenchmarkCreateRunPayload,
  BenchmarkFixture,
  BenchmarkRun,
  BenchmarkRunDetail,
  BenchmarkRunResults,
  ModelSpec,
} from '../../types/benchmark';
import {
  BENCHMARK_AGENTS,
  DEFAULT_MARKET_PRESET_ID,
  formatFixtureConfig,
  formatFixtureInputs,
  type BenchmarkAgentName,
  type FixturePresetId,
} from './fixturePresets';

const MODEL_PROVIDER_OPTIONS = ['ollama', 'openai', 'mistral'] as const;

const DEFAULT_MODEL_BY_PROVIDER: Record<(typeof MODEL_PROVIDER_OPTIONS)[number], string> = {
  ollama: 'deepseek-v3.2',
  openai: 'gpt-4o-mini',
  mistral: 'mistral-small-latest',
};

const DEFAULT_MODEL_SPEC: ModelSpec = {
  provider: 'openai',
  model_name: 'gpt-4o-mini',
  parameters: { temperature: 0 },
};

type ScenarioType = 'single-agent' | 'debate-bundle' | 'full-pipeline';

function toScenarioType(value: unknown): ScenarioType {
  if (value === 'debate-bundle' || value === 'full-pipeline') return value;
  return 'single-agent';
}

export function useBenchmarkPageState(token: string | null, userRole: string | null) {
  const [fixtures, setFixtures] = useState<BenchmarkFixture[]>([]);
  const [fixturesLoading, setFixturesLoading] = useState(false);
  const [fixturesError, setFixturesError] = useState<string | null>(null);
  const [selectedFixtureId, setSelectedFixtureId] = useState<number | null>(null);

  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [runDetail, setRunDetail] = useState<BenchmarkRunDetail | null>(null);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [runDetailError, setRunDetailError] = useState<string | null>(null);
  const [runResults, setRunResults] = useState<BenchmarkRunResults | null>(null);
  const [runResultsNotice, setRunResultsNotice] = useState<string | null>(null);

  const [modelSpecs, setModelSpecs] = useState<ModelSpec[]>([DEFAULT_MODEL_SPEC]);
  const [modelChoicesByProvider, setModelChoicesByProvider] = useState<Record<string, string[]>>({});
  const [modelChoicesLoadingByProvider, setModelChoicesLoadingByProvider] = useState<Record<string, boolean>>({});
  const [modelChoices, setModelChoices] = useState<string[]>([]);
  const [modelChoicesLoading, setModelChoicesLoading] = useState(false);
  const [repeatCount, setRepeatCount] = useState('3');
  const [tagsInput, setTagsInput] = useState('');
  const [submittingRun, setSubmittingRun] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [comparisonIds, setComparisonIds] = useState<number[]>([]);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [comparisonDetailsById, setComparisonDetailsById] = useState<Record<number, BenchmarkRunDetail>>({});

  const [showCreateFixtureForm, setShowCreateFixtureForm] = useState(false);
  const [fixtureName, setFixtureName] = useState('');
  const [fixtureAgentName, setFixtureAgentName] = useState<BenchmarkAgentName>('technical-analyst');
  const [fixturePresetId, setFixturePresetId] = useState<FixturePresetId>(DEFAULT_MARKET_PRESET_ID);
  const [fixtureInputsText, setFixtureInputsText] = useState(() =>
    formatFixtureInputs('technical-analyst', DEFAULT_MARKET_PRESET_ID),
  );
  const [fixtureConfigText, setFixtureConfigText] = useState(() => formatFixtureConfig());
  const [createFixtureSubmitting, setCreateFixtureSubmitting] = useState(false);
  const [createFixtureError, setCreateFixtureError] = useState<string | null>(null);
  const [fixtureInputsError, setFixtureInputsError] = useState<string | null>(null);
  const [fixtureConfigError, setFixtureConfigError] = useState<string | null>(null);

  const selectedFixture = useMemo(
    () => fixtures.find((fixture) => fixture.id === selectedFixtureId) ?? null,
    [fixtures, selectedFixtureId],
  );

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );

  const canManage = useMemo(() => {
    const normalizedRole = userRole?.toLowerCase() ?? '';
    return normalizedRole === 'admin' || normalizedRole === 'super_admin' || normalizedRole === 'super-admin';
  }, [userRole]);

  const loadRuns = useCallback(
    async (fixtureId: number | null) => {
      if (!fixtureId) {
        setRuns([]);
        setRunsError(null);
        return;
      }
      if (!token) return;

      setRunsLoading(true);
      setRunsError(null);
      try {
        const data = await api.listBenchmarkRuns(token, { fixture_id: fixtureId });
        setRuns(data);
      } catch (error) {
        setRuns([]);
        setRunsError(error instanceof Error ? error.message : 'Impossible de charger les runs');
      } finally {
        setRunsLoading(false);
      }
    },
    [token],
  );

  const loadFixtures = async () => {
    if (!token) return;
    setFixturesLoading(true);
    setFixturesError(null);
    try {
      const data = await api.listBenchmarkFixtures(token);
      const active = data.filter((fixture) => !fixture.is_deleted);
      setFixtures(active);
      if (active.length > 0 && selectedFixtureId == null) {
        setSelectedFixtureId(active[0].id);
      }
    } catch (error) {
      setFixturesError(error instanceof Error ? error.message : 'Impossible de charger les fixtures');
    } finally {
      setFixturesLoading(false);
    }
  };

  useEffect(() => {
    void loadFixtures();
  }, [token]);

  useEffect(() => {
    void loadRuns(selectedFixtureId);
  }, [selectedFixtureId, loadRuns]);

  useEffect(() => {
    const hasActiveRuns = runs.some((run) => run.status === 'PENDING' || run.status === 'RUNNING');
    if (!selectedFixtureId || !hasActiveRuns) return;

    const intervalId = window.setInterval(() => {
      void loadRuns(selectedFixtureId);
    }, 5000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [runs, selectedFixtureId, loadRuns]);

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null);
      setRunResults(null);
      setRunResultsNotice(null);
      return;
    }

    const loadRunDetail = async () => {
      if (!token) return;
      setRunDetailLoading(true);
      setRunDetailError(null);
      setRunResults(null);
      setRunResultsNotice(null);
      try {
        const detail = await api.getBenchmarkRun(token, selectedRunId);
        setRunDetail(detail);
        try {
          const results = await api.getBenchmarkRunResults(token, selectedRunId);
          if (Array.isArray(results.rows) && results.rows.length > 0) {
            setRunResults(results);
            setRunResultsNotice('Résultats issus de /benchmark/runs/{id}/results.');
          } else {
            setRunResultsNotice('Fallback: résultat agrégé reconstruit depuis /benchmark/runs/{id}.');
          }
        } catch (resultsError) {
          const reason = resultsError instanceof Error ? resultsError.message : 'indisponible';
          setRunResultsNotice(`Fallback actif: /benchmark/runs/{id}/results indisponible (${reason}).`);
        }
      } catch (error) {
        setRunDetail(null);
        setRunResults(null);
        setRunResultsNotice(null);
        setRunDetailError(error instanceof Error ? error.message : 'Impossible de charger le détail du run');
      } finally {
        setRunDetailLoading(false);
      }
    };

    void loadRunDetail();
  }, [token, selectedRunId]);

  const handleModelSpecChange = (index: number, field: keyof ModelSpec, value: string) => {
    setModelSpecs((prev) => {
      const next = [...prev];
      const current = next[index] ?? DEFAULT_MODEL_SPEC;
      if (field === 'parameters') {
        next[index] = {
          ...current,
          parameters: {
            ...(current.parameters ?? {}),
            temperature: value === '' ? undefined : Number(value),
          },
        };
        return next;
      }
      next[index] = {
        ...current,
        [field]: value,
      };
      return next;
    });
  };

  const loadModelChoices = useCallback(
    async (provider: string) => {
      const normalizedProvider = provider.trim().toLowerCase();
      if (!normalizedProvider || !MODEL_PROVIDER_OPTIONS.includes(normalizedProvider as (typeof MODEL_PROVIDER_OPTIONS)[number])) {
        return;
      }
      if (!token) return;

      setModelChoicesLoadingByProvider((prev) => ({ ...prev, [normalizedProvider]: true }));
      try {
        const payload = await api.listOllamaModels(token, normalizedProvider);
        const nextChoices = Array.isArray(payload.models)
          ? payload.models.map((item) => String(item).trim()).filter((item) => item.length > 0)
          : [];
        setModelChoicesByProvider((prev) => ({ ...prev, [normalizedProvider]: nextChoices }));
      } catch {
        setModelChoicesByProvider((prev) => ({ ...prev, [normalizedProvider]: [] }));
      } finally {
        setModelChoicesLoadingByProvider((prev) => ({ ...prev, [normalizedProvider]: false }));
      }
    },
    [token],
  );

  useEffect(() => {
    const providers = Array.from(
      new Set(
        modelSpecs
          .map((spec) => (typeof spec.provider === 'string' ? spec.provider.trim().toLowerCase() : ''))
          .filter((provider) => MODEL_PROVIDER_OPTIONS.includes(provider as (typeof MODEL_PROVIDER_OPTIONS)[number])),
      ),
    );
    providers.forEach((provider) => {
      const alreadyLoaded = Array.isArray(modelChoicesByProvider[provider]);
      const alreadyLoading = Boolean(modelChoicesLoadingByProvider[provider]);
      if (alreadyLoaded || alreadyLoading) return;
      void loadModelChoices(provider);
    });
  }, [modelSpecs, modelChoicesByProvider, modelChoicesLoadingByProvider, loadModelChoices]);

  useEffect(() => {
    setModelSpecs((prev) => {
      let hasChanges = false;
      const next = prev.map((spec) => {
        const provider = typeof spec.provider === 'string' ? spec.provider.trim().toLowerCase() : '';
        if (!MODEL_PROVIDER_OPTIONS.includes(provider as (typeof MODEL_PROVIDER_OPTIONS)[number])) {
          return spec;
        }

        const providerChoices = modelChoicesByProvider[provider] ?? [];
        if (providerChoices.length === 0) {
          return spec;
        }

        const currentModelName = typeof spec.model_name === 'string' ? spec.model_name.trim() : '';
        const preferredDefault = DEFAULT_MODEL_BY_PROVIDER[provider as (typeof MODEL_PROVIDER_OPTIONS)[number]];
        const nextDefault = providerChoices.includes(preferredDefault) ? preferredDefault : providerChoices[0];
        const shouldResetModel = !currentModelName || !providerChoices.includes(currentModelName);

        if (!shouldResetModel || !nextDefault) {
          return spec;
        }

        hasChanges = true;
        return {
          ...spec,
          model_name: nextDefault,
        };
      });

      return hasChanges ? next : prev;
    });
  }, [modelChoicesByProvider]);

  useEffect(() => {
    const activeProviderRaw = modelSpecs[0]?.provider;
    const activeProvider = typeof activeProviderRaw === 'string' ? activeProviderRaw.trim().toLowerCase() : '';
    if (!MODEL_PROVIDER_OPTIONS.includes(activeProvider as (typeof MODEL_PROVIDER_OPTIONS)[number])) {
      setModelChoices([]);
      setModelChoicesLoading(false);
      return;
    }
    setModelChoices(modelChoicesByProvider[activeProvider] ?? []);
    setModelChoicesLoading(Boolean(modelChoicesLoadingByProvider[activeProvider]));
  }, [modelChoicesByProvider, modelChoicesLoadingByProvider, modelSpecs]);

  const handleSubmitRun = async () => {
    if (!canManage || !token || !selectedFixture) return;

    const validSpecs = modelSpecs.filter(
      (spec) => spec.provider.trim().length > 0 && spec.model_name.trim().length > 0,
    );

    if (validSpecs.length === 0) {
      setSubmitError('Ajoutez au moins un modèle valide (provider + model_name).');
      return;
    }

    setSubmittingRun(true);
    setSubmitError(null);

    try {
      for (const spec of validSpecs) {
        const payload: BenchmarkCreateRunPayload = {
          fixture_id: selectedFixture.id,
          fixture_hash: selectedFixture.hash,
          model_spec: spec,
          scenario_type: toScenarioType(selectedFixture.config?.scenario_type),
          repetitions: Number(repeatCount) || 3,
        };
        await api.createBenchmarkRun(token, payload);
      }

      await loadRuns(selectedFixture.id);
      // TODO(GH-26/OQ-3): tags préparés côté UI, endpoint backend actuel ne supporte pas encore le champ.
      void tagsInput;
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Échec du lancement benchmark');
    } finally {
      setSubmittingRun(false);
    }
  };

  const handleSelectFixture = (fixtureId: number) => {
    setSelectedFixtureId(fixtureId);
    setSelectedRunId(null);
    setComparisonIds([]);
    setComparisonOpen(false);
    setComparisonDetailsById({});
  };

  const toggleCompare = async (runId: number) => {
    setComparisonIds((prev) => {
      if (prev.includes(runId)) return prev.filter((id) => id !== runId);
      return [...prev, runId];
    });

    if (!token || comparisonDetailsById[runId] != null) return;
    try {
      const detail = await api.getBenchmarkRun(token, runId);
      setComparisonDetailsById((prev) => ({ ...prev, [runId]: detail }));
    } catch {
      // Le détail peut être indisponible, on laisse la comparaison partielle.
    }
  };

  const parseJsonObject = (value: string, fieldLabel: string): Record<string, unknown> => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(value);
    } catch {
      throw new Error(`${fieldLabel} doit être un JSON valide.`);
    }

    if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error(`${fieldLabel} doit être un objet JSON.`);
    }

    return parsed as Record<string, unknown>;
  };

  const resetCreateFixtureForm = () => {
    setFixtureName('');
    setFixtureAgentName('technical-analyst');
    setFixturePresetId(DEFAULT_MARKET_PRESET_ID);
    setFixtureInputsText(formatFixtureInputs('technical-analyst', DEFAULT_MARKET_PRESET_ID));
    setFixtureConfigText(formatFixtureConfig());
    setCreateFixtureError(null);
    setFixtureInputsError(null);
    setFixtureConfigError(null);
  };

  const handleFixtureAgentChange = (agentName: string) => {
    const nextAgent = BENCHMARK_AGENTS.includes(agentName as BenchmarkAgentName)
      ? (agentName as BenchmarkAgentName)
      : 'technical-analyst';
    setFixtureAgentName(nextAgent);
    setFixturePresetId(DEFAULT_MARKET_PRESET_ID);
    setFixtureInputsText(formatFixtureInputs(nextAgent, DEFAULT_MARKET_PRESET_ID));
    setFixtureConfigText(formatFixtureConfig());
    setFixtureInputsError(null);
    setFixtureConfigError(null);
  };

  const handleFixturePresetChange = (presetId: FixturePresetId) => {
    setFixturePresetId(presetId);
    setFixtureInputsText(formatFixtureInputs(fixtureAgentName, presetId));
    setFixtureConfigText(formatFixtureConfig());
    setFixtureInputsError(null);
    setFixtureConfigError(null);
  };

  const handleCancelCreateFixture = () => {
    setShowCreateFixtureForm(false);
    resetCreateFixtureForm();
  };

  const handleCreateFixture = async () => {
    if (!canManage || !token || createFixtureSubmitting) return;

    const name = fixtureName.trim();
    if (!name) {
      setCreateFixtureError('Le nom de la fixture est requis.');
      return;
    }

    setCreateFixtureError(null);
    setFixtureInputsError(null);
    setFixtureConfigError(null);

    let inputs: Record<string, unknown>;
    let config: Record<string, unknown>;

    try {
      inputs = parseJsonObject(fixtureInputsText, 'Inputs');
    } catch (error) {
      setFixtureInputsError(error instanceof Error ? error.message : 'Inputs doit être un JSON valide.');
      return;
    }

    try {
      config = parseJsonObject(fixtureConfigText, 'Config');
    } catch (error) {
      setFixtureConfigError(error instanceof Error ? error.message : 'Config doit être un JSON valide.');
      return;
    }

    const payload: BenchmarkCreateFixturePayload = {
      name,
      agent_name: fixtureAgentName,
      inputs,
      config,
    };

    setCreateFixtureSubmitting(true);
    try {
      const createdFixture = await api.createBenchmarkFixture(token, payload);
      await loadFixtures();
      handleSelectFixture(createdFixture.id);
      setShowCreateFixtureForm(false);
      resetCreateFixtureForm();
    } catch (error) {
      setCreateFixtureError(error instanceof Error ? error.message : 'Impossible de créer la fixture');
    } finally {
      setCreateFixtureSubmitting(false);
    }
  };

  return {
    fixtures,
    fixturesLoading,
    fixturesError,
    selectedFixtureId,
    selectedFixture,
    runs,
    runsLoading,
    runsError,
    selectedRun,
    selectedRunId,
    runDetail,
    runDetailLoading,
    runDetailError,
    runResults,
    runResultsNotice,
    modelSpecs,
    modelChoices,
    modelChoicesLoading,
    modelChoicesByProvider,
    modelChoicesLoadingByProvider,
    repeatCount,
    tagsInput,
    submittingRun,
    submitError,
    comparisonIds,
    comparisonOpen,
    comparisonDetailsById,
    showCreateFixtureForm,
    fixtureName,
    fixtureAgentName,
    fixturePresetId,
    fixtureInputsText,
    fixtureConfigText,
    createFixtureSubmitting,
    createFixtureError,
    fixtureInputsError,
    fixtureConfigError,
    canManage,
    setSelectedFixtureId,
    setSelectedRunId,
    setComparisonIds,
    setComparisonOpen,
    setModelSpecs,
    setRepeatCount,
    setTagsInput,
    setShowCreateFixtureForm,
    setFixtureName,
    setFixtureAgentName,
    setFixturePresetId,
    setFixtureInputsText,
    setFixtureConfigText,
    handleFixtureAgentChange,
    handleFixturePresetChange,
    handleModelSpecChange,
    handleSubmitRun,
    handleSelectFixture,
    handleCreateFixture,
    handleCancelCreateFixture,
    toggleCompare,
    loadRuns,
  };
}

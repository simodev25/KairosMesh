import { FormEvent, useMemo, useState } from 'react';
import { AgentChip } from './AgentChip';
import type { EvolutionCampaignCreatePayload } from '../../types/evolution';

interface CampaignFormProps {
  onSubmit: (payload: EvolutionCampaignCreatePayload) => Promise<void>;
  loading: boolean;
}

const AGENTS = [
  'technical-analyst',
  'news-analyst',
  'market-context-analyst',
  'bullish-researcher',
  'bearish-researcher',
  'trader-agent',
  'risk-manager',
  'execution-manager',
  'governance-trader',
];

export function CampaignForm({ onSubmit, loading }: CampaignFormProps) {
  const [name, setName] = useState('Evolution Campaign');
  const [agent, setAgent] = useState('technical-analyst');
  const [provider, setProvider] = useState('openai');
  const [modelName, setModelName] = useState('gpt-4.1-mini');
  const [baselinePromptTemplateId, setBaselinePromptTemplateId] = useState(1);
  const [baselineSkillId, setBaselineSkillId] = useState(1);
  const [maxIterations, setMaxIterations] = useState(100);
  const [maxCandidates, setMaxCandidates] = useState(50);
  const [maxLlmCalls, setMaxLlmCalls] = useState(1000);
  const [budgetUsd, setBudgetUsd] = useState(10);

  const canSubmit = useMemo(
    () => !loading && name.trim().length > 0 && baselinePromptTemplateId > 0,
    [baselinePromptTemplateId, loading, name],
  );

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;

    await onSubmit({
      name: name.trim(),
      agent_name: agent,
      provider,
      model_name: modelName,
      model_parameters: { temperature: 0.7 },
      baseline_prompt_template_id: baselinePromptTemplateId,
      baseline_skill_id: baselineSkillId > 0 ? baselineSkillId : undefined,
      max_iterations: maxIterations,
      max_candidates: maxCandidates,
      max_llm_calls: maxLlmCalls,
      budget_usd_limit: budgetUsd,
      evaluation_config: { benchmark_profile: 'standard', scenario_type: 'single-agent', repetitions: 2 },
    });
  };

  return (
    <form onSubmit={handleSubmit} className="hw-surface p-4 space-y-4">
      <div className="section-header">
        <span className="section-title">+ NOUVELLE CAMPAGNE</span>
      </div>

      <div>
        <label className="micro-label">Agent cible</label>
        <div className="flex flex-wrap gap-2 mt-2">
          {AGENTS.map((agentName) => (
            <AgentChip key={agentName} agent={agentName} selected={agentName === agent} onClick={setAgent} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nom campagne" />
        <input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="Modèle mutator" />
        <select value={provider} onChange={(event) => setProvider(event.target.value)}>
          <option value="openai">openai</option>
          <option value="ollama">ollama</option>
          <option value="mistral">mistral</option>
        </select>
        <input
          type="number"
          min={1}
          value={baselinePromptTemplateId}
          onChange={(event) => setBaselinePromptTemplateId(Number(event.target.value))}
          placeholder="Baseline prompt id"
        />
        <input
          type="number"
          min={0}
          value={baselineSkillId}
          onChange={(event) => setBaselineSkillId(Number(event.target.value))}
          placeholder="Baseline skill id"
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <input type="number" min={1} value={maxIterations} onChange={(event) => setMaxIterations(Number(event.target.value))} />
        <input type="number" min={1} value={maxCandidates} onChange={(event) => setMaxCandidates(Number(event.target.value))} />
        <input type="number" min={1} value={maxLlmCalls} onChange={(event) => setMaxLlmCalls(Number(event.target.value))} />
        <input type="number" min={0} step="0.1" value={budgetUsd} onChange={(event) => setBudgetUsd(Number(event.target.value))} />
      </div>

      <div className="flex justify-end">
        <button className="btn-primary" type="submit" disabled={!canSubmit}>
          {loading ? 'CRÉATION...' : 'LANCER CAMPAGNE'}
        </button>
      </div>
    </form>
  );
}

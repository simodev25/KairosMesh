export interface ModelSpec {
  provider: string;
  model_name: string;
  parameters?: Record<string, unknown>;
}

export interface BenchmarkFixture {
  id: number;
  name: string;
  agent_name: string;
  version: number;
  hash: string;
  inputs: Record<string, unknown>;
  config: Record<string, unknown>;
  default_scoring_weights?: Record<string, number> | null;
  is_active: boolean;
  is_deleted: boolean;
  created_by_id: number;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkCreateFixturePayload {
  name: string;
  agent_name: string;
  inputs: Record<string, unknown>;
  config: Record<string, unknown>;
  default_scoring_weights?: Record<string, number> | null;
}

export interface BenchmarkRun {
  id: number;
  fixture_id: number;
  fixture_hash: string;
  model_spec: ModelSpec;
  scenario_type: string;
  status: string;
  repetitions: number;
  max_llm_calls?: number | null;
  effective_scoring_weights?: Record<string, number> | null;
  error?: string | null;
  created_by_id: number;
  celery_task_id?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at: string;
}

export interface BenchmarkScoresV1 {
  schema_validity: number;
  completeness: number;
  tool_policy: number;
  reference_consistency: number;
  stability: number;
  overall: number;
}

export interface BenchmarkAttempt {
  id: number;
  attempt_number: number;
  raw_output: Record<string, unknown>;
  schema_validity_score: number;
  completeness_score: number;
  tool_policy_compliance_score: number;
  reference_consistency_score: number;
  stability_score?: number | null;
  aggregate_score: number;
  llm_calls_count: number;
  analysis_run_id?: number | null;
  executed_at: string;
}

export interface BenchmarkCase {
  id: number;
  agent_name: string;
  case_order: number;
  aggregate_score?: number | null;
  created_at: string;
  attempts: BenchmarkAttempt[];
}

export interface BenchmarkRunDetail extends BenchmarkRun {
  cases: BenchmarkCase[];
}

export interface BenchmarkRunResultsRow {
  model_key: string;
  provider: string;
  model_name: string;
  scores: BenchmarkScoresV1;
  sample_size?: number;
  metadata?: Record<string, unknown>;
}

export interface BenchmarkRunResults {
  run_id: number;
  rows: BenchmarkRunResultsRow[];
  // TODO(GH-26/OQ-1): stabiliser le contrat exact backend de /benchmark/runs/{id}/results.
  // Les champs non documentés sont conservés pour compatibilité ascendante.
  extra?: Record<string, unknown>;
  raw?: unknown;
}

export interface BenchmarkCreateRunPayload {
  fixture_id: number;
  fixture_hash: string;
  model_spec: ModelSpec;
  scenario_type: 'single-agent' | 'debate-bundle' | 'full-pipeline';
  repetitions?: number;
  max_llm_calls?: number;
  scoring_weights?: Record<string, number>;
}

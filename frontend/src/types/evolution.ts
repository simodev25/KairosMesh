export interface EvolutionCampaign {
  id: number;
  name: string;
  agent_name: string;
  provider: string;
  model_name: string;
  model_parameters: Record<string, unknown>;
  baseline_prompt_template_id: number;
  baseline_skill_id: number | null;
  status: string;
  max_iterations: number;
  max_candidates: number;
  max_llm_calls: number;
  budget_usd_limit: number;
  evaluation_config: Record<string, unknown>;
  best_candidate_id: number | null;
  celery_task_id: string | null;
  consumed_budget_usd: number;
  llm_calls_used: number;
  consumed_iterations: number;
  consumed_candidates: number;
  created_by_id: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  updated_at: string;
}

export interface EvolutionCampaignList {
  items: EvolutionCampaign[];
  total: number;
}

export interface EvolutionCampaignCreatePayload {
  name: string;
  agent_name: string;
  provider: string;
  model_name: string;
  model_parameters: Record<string, unknown>;
  baseline_prompt_template_id: number;
  baseline_skill_id?: number;
  max_iterations: number;
  max_candidates: number;
  max_llm_calls: number;
  budget_usd_limit: number;
  evaluation_config: Record<string, unknown>;
}

export interface EvolutionCandidate {
  id: number;
  campaign_id: number;
  generation: number;
  parent_candidate_id: number | null;
  system_prompt: string;
  user_prompt_template: string;
  skills: string[];
  fitness_score: number | null;
  metrics_summary: Record<string, unknown> | null;
  llm_cost_usd: number;
  llm_calls_count: number;
  is_baseline: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface EvolutionFitnessSeries {
  points: Array<{
    generation: number;
    best: number;
    avg: number;
  }>;
}

export interface EvolutionPromotion {
  promotion_id: number;
  prompt_template_id: number | null;
  agent_skill_id: number | null;
  created_at: string;
}

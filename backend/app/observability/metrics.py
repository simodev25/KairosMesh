from prometheus_client import Counter, Histogram

analysis_runs_total = Counter('analysis_runs_total', 'Number of analysis runs', ['status'])
orchestrator_step_duration_seconds = Histogram('orchestrator_step_duration_seconds', 'Agent step latency', ['agent'])
llm_calls_total = Counter('llm_calls_total', 'Total LLM calls', ['provider', 'status'])
llm_prompt_tokens_total = Counter('llm_prompt_tokens_total', 'Total prompt tokens consumed', ['provider', 'model'])
llm_completion_tokens_total = Counter('llm_completion_tokens_total', 'Total completion tokens consumed', ['provider', 'model'])
llm_cost_usd_total = Counter('llm_cost_usd_total', 'Estimated LLM cost in USD', ['provider', 'model'])
llm_latency_seconds = Histogram('llm_latency_seconds', 'LLM end-to-end latency in seconds', ['provider', 'model', 'status'])
external_provider_failures_total = Counter('external_provider_failures_total', 'External provider failures', ['provider'])

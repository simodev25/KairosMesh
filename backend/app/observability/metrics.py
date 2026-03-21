from prometheus_client import Counter, Histogram

analysis_runs_total = Counter('analysis_runs_total', 'Number of analysis runs', ['status'])
orchestrator_step_duration_seconds = Histogram('orchestrator_step_duration_seconds', 'Agent step latency', ['agent'])
agentic_runtime_runs_total = Counter(
    'agentic_runtime_runs_total',
    'Number of agentic runtime runs',
    ['status', 'mode', 'resumed'],
)
agentic_runtime_tool_selections_total = Counter(
    'agentic_runtime_tool_selections_total',
    'Planner selections by runtime tool',
    ['tool', 'source', 'degraded'],
)
agentic_runtime_tool_calls_total = Counter(
    'agentic_runtime_tool_calls_total',
    'Runtime tool invocations',
    ['tool', 'status'],
)
agentic_runtime_tool_duration_seconds = Histogram(
    'agentic_runtime_tool_duration_seconds',
    'Runtime tool duration in seconds',
    ['tool', 'status'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60),
)
agentic_runtime_subagent_sessions_total = Counter(
    'agentic_runtime_subagent_sessions_total',
    'Specialist subagent session lifecycle events',
    ['source_tool', 'session_mode', 'status', 'resumed'],
)
agentic_runtime_final_decisions_total = Counter(
    'agentic_runtime_final_decisions_total',
    'Final trading decisions produced by the agentic runtime',
    ['decision', 'mode'],
)
agentic_runtime_execution_outcomes_total = Counter(
    'agentic_runtime_execution_outcomes_total',
    'Execution outcomes produced by the agentic runtime',
    ['status', 'mode'],
)
agentic_runtime_session_messages_total = Counter(
    'agentic_runtime_session_messages_total',
    'Messages sent to runtime sessions',
    ['resume_requested'],
)
agentic_runtime_memory_refresh_total = Counter(
    'agentic_runtime_memory_refresh_total',
    'Memory refresh cycles triggered by the runtime',
    ['mode'],
)
llm_calls_total = Counter('llm_calls_total', 'Total LLM calls', ['provider', 'status'])
llm_prompt_tokens_total = Counter('llm_prompt_tokens_total', 'Total prompt tokens consumed', ['provider', 'model'])
llm_completion_tokens_total = Counter('llm_completion_tokens_total', 'Total completion tokens consumed', ['provider', 'model'])
llm_cost_usd_total = Counter('llm_cost_usd_total', 'Estimated LLM cost in USD', ['provider', 'model'])
llm_latency_seconds = Histogram('llm_latency_seconds', 'LLM end-to-end latency in seconds', ['provider', 'model', 'status'])
external_provider_failures_total = Counter('external_provider_failures_total', 'External provider failures', ['provider'])

backend_http_requests_total = Counter(
    'backend_http_requests_total',
    'Total backend HTTP requests',
    ['method', 'route', 'status'],
)
backend_http_request_duration_seconds = Histogram(
    'backend_http_request_duration_seconds',
    'Backend HTTP request duration in seconds',
    ['method', 'route'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)

metaapi_cache_hits_total = Counter(
    'metaapi_cache_hits_total',
    'MetaApi Redis cache hits',
    ['resource'],
)
metaapi_cache_misses_total = Counter(
    'metaapi_cache_misses_total',
    'MetaApi Redis cache misses',
    ['resource'],
)
yfinance_cache_hits_total = Counter(
    'yfinance_cache_hits_total',
    'Yahoo Finance Redis cache hits',
    ['resource'],
)
yfinance_cache_misses_total = Counter(
    'yfinance_cache_misses_total',
    'Yahoo Finance Redis cache misses',
    ['resource'],
)

metaapi_sdk_circuit_open_total = Counter(
    'metaapi_sdk_circuit_open_total',
    'Number of MetaApi SDK circuit breaker openings',
    ['region', 'operation'],
)

from pydantic import BaseModel


class LlmAnalyticsSummary(BaseModel):
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_latency_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float

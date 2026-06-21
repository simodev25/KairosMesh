from app.services.agentscope.schemas import (
    DebateThesis,
    ExecutionPlanResult,
    MarketContextResult,
    NewsAnalysisResult,
    RiskAssessmentResult,
    TechnicalAnalysisResult,
    TraderDecisionDraft,
)


AGENT_OUTPUT_SCHEMA_MAP = {
    'technical-analyst': TechnicalAnalysisResult,
    'news-analyst': NewsAnalysisResult,
    'market-context-analyst': MarketContextResult,
    'bullish-researcher': DebateThesis,
    'bearish-researcher': DebateThesis,
    'trader-agent': TraderDecisionDraft,
    'risk-manager': RiskAssessmentResult,
    'execution-manager': ExecutionPlanResult,
}

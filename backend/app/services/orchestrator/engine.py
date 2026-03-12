import logging
import time
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models.agent_step import AgentStep
from app.db.models.run import AnalysisRun
from app.observability.metrics import analysis_runs_total, orchestrator_step_duration_seconds
from app.services.execution.executor import ExecutionService
from app.services.market.yfinance_provider import YFinanceMarketProvider
from app.services.memory.vector_memory import VectorMemoryService
from app.services.orchestrator.agents import (
    AgentContext,
    BearishResearcherAgent,
    BullishResearcherAgent,
    MacroAnalystAgent,
    NewsAnalystAgent,
    SentimentAgent,
    TechnicalAnalystAgent,
    TraderAgent,
)
from app.services.prompts.registry import PromptTemplateService
from app.services.risk.rules import RiskEngine

logger = logging.getLogger(__name__)


class ForexOrchestrator:
    def __init__(self) -> None:
        self.market_provider = YFinanceMarketProvider()
        self.memory_service = VectorMemoryService()
        self.prompt_service = PromptTemplateService()
        self.risk_engine = RiskEngine()
        self.execution_service = ExecutionService()

        self.technical_agent = TechnicalAnalystAgent()
        self.news_agent = NewsAnalystAgent(self.prompt_service)
        self.macro_agent = MacroAnalystAgent()
        self.sentiment_agent = SentimentAgent()
        self.bullish_researcher = BullishResearcherAgent(self.prompt_service)
        self.bearish_researcher = BearishResearcherAgent(self.prompt_service)
        self.trader_agent = TraderAgent()

    def _record_step(self, db: Session, run: AnalysisRun, agent_name: str, input_payload: dict[str, Any], output_payload: dict[str, Any]) -> None:
        step = AgentStep(
            run_id=run.id,
            agent_name=agent_name,
            status='completed',
            input_payload=input_payload,
            output_payload=output_payload,
        )
        db.add(step)
        db.flush()

    def _run_step(
        self,
        db: Session,
        run: AnalysisRun,
        agent_name: str,
        input_payload: dict[str, Any],
        fn: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        output = fn()
        elapsed = time.perf_counter() - started
        orchestrator_step_duration_seconds.labels(agent=agent_name).observe(elapsed)
        self._record_step(db, run, agent_name, input_payload, output)
        return output

    async def execute(
        self,
        db: Session,
        run: AnalysisRun,
        risk_percent: float,
        metaapi_account_ref: int | None = None,
    ) -> AnalysisRun:
        run.status = 'running'
        db.commit()
        db.refresh(run)

        self.prompt_service.seed_defaults(db)

        market = self.market_provider.get_market_snapshot(run.pair, run.timeframe)
        news = self.market_provider.get_news_context(run.pair)
        memory_context = self.memory_service.search(
            db=db,
            pair=run.pair,
            timeframe=run.timeframe,
            query=f'{run.pair} {run.timeframe} trend {market.get("trend", "unknown")}',
            limit=5,
        )

        context = AgentContext(
            pair=run.pair,
            timeframe=run.timeframe,
            mode=run.mode,
            risk_percent=risk_percent,
            market_snapshot=market,
            news_context=news,
            memory_context=memory_context,
        )

        analysis_outputs: dict[str, dict[str, Any]] = {}

        try:
            tech_out = self._run_step(
                db,
                run,
                self.technical_agent.name,
                {'pair': run.pair, 'timeframe': run.timeframe},
                lambda: self.technical_agent.run(context),
            )
            analysis_outputs[self.technical_agent.name] = tech_out

            news_out = self._run_step(
                db,
                run,
                self.news_agent.name,
                {'news_count': len(news.get('news', [])), 'memory_context': memory_context},
                lambda: self.news_agent.run(context, db=db),
            )
            analysis_outputs[self.news_agent.name] = news_out

            macro_out = self._run_step(
                db,
                run,
                self.macro_agent.name,
                {'market': market},
                lambda: self.macro_agent.run(context),
            )
            analysis_outputs[self.macro_agent.name] = macro_out

            sentiment_out = self._run_step(
                db,
                run,
                self.sentiment_agent.name,
                {'market': market},
                lambda: self.sentiment_agent.run(context),
            )
            analysis_outputs[self.sentiment_agent.name] = sentiment_out

            bullish = self._run_step(
                db,
                run,
                self.bullish_researcher.name,
                {'analysis_outputs': analysis_outputs, 'memory_context': memory_context},
                lambda: self.bullish_researcher.run(context, analysis_outputs, db=db),
            )

            bearish = self._run_step(
                db,
                run,
                self.bearish_researcher.name,
                {'analysis_outputs': analysis_outputs, 'memory_context': memory_context},
                lambda: self.bearish_researcher.run(context, analysis_outputs, db=db),
            )

            trader_decision = self._run_step(
                db,
                run,
                self.trader_agent.name,
                {'analysis_outputs': analysis_outputs, 'bullish': bullish, 'bearish': bearish},
                lambda: self.trader_agent.run(context, analysis_outputs, bullish, bearish),
            )

            risk = self.risk_engine.evaluate(
                mode=run.mode,
                decision=trader_decision['decision'],
                risk_percent=risk_percent,
                price=trader_decision['entry'] or 1.0,
                stop_loss=trader_decision.get('stop_loss'),
            )
            risk_output = {'accepted': risk.accepted, 'reasons': risk.reasons, 'suggested_volume': risk.suggested_volume}
            self._record_step(db, run, 'risk-manager', trader_decision, risk_output)

            if metaapi_account_ref is None:
                metaapi_account_ref = int((run.trace or {}).get('requested_metaapi_account_ref', 0) or 0) or None

            execution_result: dict[str, Any] = {'status': 'skipped'}
            if risk.accepted and trader_decision['decision'] in {'BUY', 'SELL'}:
                execution_result = await self.execution_service.execute(
                    db=db,
                    run_id=run.id,
                    mode=run.mode,
                    symbol=run.pair,
                    side=trader_decision['decision'],
                    volume=risk.suggested_volume,
                    stop_loss=trader_decision.get('stop_loss'),
                    take_profit=trader_decision.get('take_profit'),
                    metaapi_account_ref=metaapi_account_ref,
                )
            self._record_step(db, run, 'execution-manager', risk_output, execution_result)

            run.decision = {
                **trader_decision,
                'risk': risk_output,
                'execution': execution_result,
            }
            run.trace = {
                'market': market,
                'news': news,
                'analysis_outputs': analysis_outputs,
                'bullish': bullish,
                'bearish': bearish,
                'memory_context': memory_context,
                'requested_metaapi_account_ref': metaapi_account_ref,
            }
            run.status = 'completed'
            db.commit()
            db.refresh(run)

            self.memory_service.add_run_memory(db, run)
            analysis_runs_total.labels(status='completed').inc()
            return run
        except Exception as exc:
            logger.exception('orchestration failed run_id=%s', run.id)
            run.status = 'failed'
            run.error = str(exc)
            db.commit()
            db.refresh(run)
            analysis_runs_total.labels(status='failed').inc()
            return run

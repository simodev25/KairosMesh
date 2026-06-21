from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.benchmark_attempt import BenchmarkAttempt
from app.db.models.benchmark_case import BenchmarkCase
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.llm_call_log import LlmCallLog
from app.db.models.run import AnalysisRun
from app.services.agentscope.agents import ALL_AGENT_FACTORIES
from app.services.agentscope.formatter_factory import build_formatter
from app.services.agentscope.model_factory import build_model
from app.services.agentscope.toolkit import build_toolkit
from app.services.benchmark.constants import BenchmarkRunStatus, BenchmarkScenarioType
from app.services.benchmark.scenarios import (
    run_debate_bundle_scenario,
    run_full_pipeline_scenario,
    run_single_agent_scenario,
)
from app.services.benchmark.scoring_v1 import compute_stability_score, score_attempt


class BenchmarkEngine:
    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _resolve_provider_config(model_spec: dict[str, Any]) -> tuple[str, str, str, str]:
        provider = str(model_spec.get('provider') or 'ollama').strip().lower()
        model_name = str(model_spec.get('model_name') or '').strip()
        if not model_name:
            raise HTTPException(status_code=422, detail='model_spec.model_name is required')

        settings = get_settings()
        if provider == 'openai':
            return provider, model_name, settings.openai_base_url, settings.openai_api_key
        if provider == 'mistral':
            return provider, model_name, settings.mistral_base_url, settings.mistral_api_key
        return 'ollama', model_name, settings.ollama_base_url, settings.ollama_api_key

    async def _build_agent(
        self,
        *,
        db: Session,
        agent_name: str,
        fixture: BenchmarkFixture,
        model_spec: dict[str, Any],
    ):
        provider, model_name, base_url, api_key = self._resolve_provider_config(model_spec)
        model = build_model(provider, model_name, base_url, api_key, temperature=float(model_spec.get('parameters', {}).get('temperature', 0.0)))
        formatter = build_formatter(provider, multi_agent=False, base_url=base_url)
        toolkit = await build_toolkit(
            agent_name,
            ohlc=fixture.inputs.get('ohlc') if isinstance(fixture.inputs, dict) else None,
            snapshot=fixture.inputs.get('snapshot') if isinstance(fixture.inputs, dict) else None,
        )
        factory = ALL_AGENT_FACTORIES.get(agent_name)
        if not factory:
            raise HTTPException(status_code=422, detail=f'Unsupported agent_name {agent_name}')
        sys_prompt = str((fixture.config or {}).get('system_prompt') or f'Benchmark mode for {agent_name}')
        return factory(model=model, formatter=formatter, toolkit=toolkit, sys_prompt=sys_prompt)

    async def execute_run(self, db: Session, benchmark_run: BenchmarkRun) -> BenchmarkRun:
        fixture = db.get(BenchmarkFixture, benchmark_run.fixture_id)
        if not fixture or fixture.is_deleted:
            raise HTTPException(status_code=404, detail='Benchmark fixture not found')

        benchmark_run.status = BenchmarkRunStatus.RUNNING
        db.commit()
        db.refresh(benchmark_run)

        scenario_type = benchmark_run.scenario_type
        repetitions = int(benchmark_run.repetitions)
        model_spec = benchmark_run.model_spec or {}

        context_msg = str((fixture.inputs or {}).get('context') or '')

        def _create_analysis_run_record(agent_name: str) -> int:
            pair = str((fixture.inputs or {}).get('symbol') or (fixture.inputs or {}).get('pair') or 'BENCH')
            timeframe = str((fixture.inputs or {}).get('timeframe') or 'H1')
            analysis_run = AnalysisRun(
                pair=pair,
                timeframe=timeframe,
                mode='simulation',
                status='running',
                progress=0,
                decision={},
                trace={
                    'runtime_engine': 'benchmark_v1',
                    'benchmark_run_id': benchmark_run.id,
                    'benchmark_agent_name': agent_name,
                },
                created_by_id=benchmark_run.created_by_id,
            )
            db.add(analysis_run)
            db.flush()
            return int(analysis_run.id)

        created_analysis_run_ids: set[int] = set()

        analysis_run_id_single: int | None = None
        analysis_run_id_debate: int | None = None
        analysis_run_id_pipeline: int | None = None

        if scenario_type == BenchmarkScenarioType.SINGLE_AGENT:
            analysis_run_id_single = _create_analysis_run_record(fixture.agent_name)
            created_analysis_run_ids.add(analysis_run_id_single)
            agent = await self._build_agent(db=db, agent_name=fixture.agent_name, fixture=fixture, model_spec=model_spec)
            execution = await run_single_agent_scenario(
                analysis_run_id=analysis_run_id_single,
                agent_name=fixture.agent_name,
                agent=agent,
                context_msg=context_msg,
                repetitions=repetitions,
            )
        elif scenario_type == BenchmarkScenarioType.DEBATE_BUNDLE:
            analysis_run_id_debate = _create_analysis_run_record('debate-bundle')
            created_analysis_run_ids.add(analysis_run_id_debate)
            bullish = await self._build_agent(db=db, agent_name='bullish-researcher', fixture=fixture, model_spec=model_spec)
            bearish = await self._build_agent(db=db, agent_name='bearish-researcher', fixture=fixture, model_spec=model_spec)
            trader = await self._build_agent(db=db, agent_name='trader-agent', fixture=fixture, model_spec=model_spec)
            llm_enabled_flags = {
                'bullish-researcher': bool((fixture.config or {}).get('llm_enabled', True)),
                'bearish-researcher': bool((fixture.config or {}).get('llm_enabled', True)),
                'trader-agent': bool((fixture.config or {}).get('llm_enabled', True)),
            }
            execution = await run_debate_bundle_scenario(
                analysis_run_id=analysis_run_id_debate,
                llm_enabled_flags=llm_enabled_flags,
                bullish_agent=bullish,
                bearish_agent=bearish,
                trader_agent=trader,
                context_msg=context_msg,
                repetitions=repetitions,
            )
        elif scenario_type == BenchmarkScenarioType.FULL_PIPELINE:
            analysis_run_id_pipeline = _create_analysis_run_record('full-pipeline')
            created_analysis_run_ids.add(analysis_run_id_pipeline)
            ordered_agent_names = [
                'technical-analyst',
                'news-analyst',
                'market-context-analyst',
                'bullish-researcher',
                'bearish-researcher',
                'trader-agent',
                'risk-manager',
            ]
            ordered_agents = [
                (
                    agent_name,
                    await self._build_agent(db=db, agent_name=agent_name, fixture=fixture, model_spec=model_spec),
                )
                for agent_name in ordered_agent_names
            ]
            execution = await run_full_pipeline_scenario(
                analysis_run_id=analysis_run_id_pipeline,
                ordered_agents=ordered_agents,
                context_msg=context_msg,
                repetitions=repetitions,
            )
        else:
            raise HTTPException(status_code=422, detail=f'Unsupported scenario_type {scenario_type}')

        if execution.status == BenchmarkRunStatus.SKIPPED_DEBATE:
            analysis_run = db.get(AnalysisRun, analysis_run_id_debate) if analysis_run_id_debate is not None else None
            if analysis_run is not None:
                analysis_run.status = 'completed'
                analysis_run.progress = 100
                analysis_run.trace = {**(analysis_run.trace or {}), 'benchmark_status': BenchmarkRunStatus.SKIPPED_DEBATE}
            benchmark_run.status = BenchmarkRunStatus.SKIPPED_DEBATE
            db.commit()
            db.refresh(benchmark_run)
            return benchmark_run

        case_by_agent: dict[str, BenchmarkCase] = {}
        case_order_by_agent: dict[str, int] = {}
        next_case_order = 1

        aggregate_scores_by_agent: dict[str, list[float]] = defaultdict(list)
        attempts_by_agent: dict[str, list[BenchmarkAttempt]] = defaultdict(list)

        scoring_weights = benchmark_run.effective_scoring_weights or fixture.default_scoring_weights

        for scenario_attempt in execution.attempts:
            case = case_by_agent.get(scenario_attempt.agent_name)
            if case is None:
                case = BenchmarkCase(
                    run_id=benchmark_run.id,
                    agent_name=scenario_attempt.agent_name,
                    case_order=next_case_order,
                )
                case_by_agent[scenario_attempt.agent_name] = case
                case_order_by_agent[scenario_attempt.agent_name] = next_case_order
                next_case_order += 1
                db.add(case)
                db.flush()

            score = score_attempt(
                agent_name=scenario_attempt.agent_name,
                raw_output=scenario_attempt.raw_output,
                fixture_inputs=fixture.inputs or {},
                fixture_config=fixture.config or {},
                tool_calls=[],
                scoring_weights=scoring_weights,
            )

            attempt = BenchmarkAttempt(
                case_id=case.id,
                attempt_number=scenario_attempt.attempt_number,
                raw_output=scenario_attempt.raw_output,
                schema_validity_score=score['schema_validity_score'],
                completeness_score=score['completeness_score'],
                tool_policy_compliance_score=score['tool_policy_compliance_score'],
                reference_consistency_score=score['reference_consistency_score'],
                stability_score=None,
                aggregate_score=score['aggregate_score'],
                llm_calls_count=0,
                analysis_run_id=scenario_attempt.analysis_run_id,
            )
            db.add(attempt)

            aggregate_scores_by_agent[scenario_attempt.agent_name].append(score['aggregate_score'])
            attempts_by_agent[scenario_attempt.agent_name].append(attempt)

        db.flush()

        total_llm_calls = 0
        for attempts in attempts_by_agent.values():
            for attempt in attempts:
                if attempt.analysis_run_id is None:
                    attempt.llm_calls_count = 0
                    continue
                llm_calls_count = (
                    db.query(LlmCallLog)
                    .filter(LlmCallLog.analysis_run_id == attempt.analysis_run_id)
                    .count()
                )
                attempt.llm_calls_count = llm_calls_count
                total_llm_calls += llm_calls_count

        if benchmark_run.max_llm_calls is not None and total_llm_calls > int(benchmark_run.max_llm_calls):
            benchmark_run.status = BenchmarkRunStatus.FAILED
            benchmark_run.error = (
                f'max_llm_calls exceeded: total={total_llm_calls} limit={benchmark_run.max_llm_calls}'
            )
            for analysis_run_id in {analysis_run_id_single, analysis_run_id_debate, analysis_run_id_pipeline}:
                analysis_run = db.get(AnalysisRun, analysis_run_id)
                if analysis_run is None:
                    continue
                analysis_run.status = 'failed'
                analysis_run.trace = {**(analysis_run.trace or {}), 'benchmark_status': benchmark_run.status}
            db.commit()
            db.refresh(benchmark_run)
            return benchmark_run

        for agent_name, scores in aggregate_scores_by_agent.items():
            stability = compute_stability_score(scores)
            attempts = attempts_by_agent[agent_name]
            for attempt in attempts:
                attempt.stability_score = stability
            case = case_by_agent[agent_name]
            case.aggregate_score = sum(scores) / len(scores) if scores else 0.0

        benchmark_run.status = BenchmarkRunStatus.COMPLETED

        for analysis_run_id in created_analysis_run_ids:
            analysis_run = db.get(AnalysisRun, analysis_run_id)
            if analysis_run is None:
                continue
            analysis_run.status = 'completed'
            analysis_run.progress = 100
            analysis_run.trace = {**(analysis_run.trace or {}), 'benchmark_status': benchmark_run.status}

        db.commit()
        db.refresh(benchmark_run)
        return benchmark_run

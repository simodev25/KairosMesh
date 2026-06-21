from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from agentscope.message import Msg
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
from app.services.prompts.registry import DEFAULT_PROMPTS, PromptTemplateService


logger = logging.getLogger(__name__)
MAX_DEBUG_TEXT_LENGTH = 10000


def _truncate_text(value: str | None, *, max_length: int = MAX_DEBUG_TEXT_LENGTH) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:max_length]


def _safe_json_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_json_payload(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe_json_payload(item) for item in value]
    if isinstance(value, str):
        return _truncate_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _truncate_text(str(value))


def _dump_benchmark_run_summary(
    *,
    run_id: int,
    fixture_id: int,
    scenario_type: str,
    model_spec: dict[str, Any],
    attempts_summary: list[dict[str, Any]],
    final_status: str,
    error: str | None,
) -> None:
    settings = get_settings()
    if not settings.debug_benchmark_enabled:
        return

    try:
        trace_dir = settings.debug_benchmark_dir or './debug-benchmark'
        os.makedirs(trace_dir, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        filename = f'bench-{run_id}-summary-{ts}.json'
        filepath = os.path.join(trace_dir, filename)

        payload = {
            'run_id': run_id,
            'fixture_id': fixture_id,
            'scenario_type': scenario_type,
            'model_spec': _safe_json_payload(model_spec),
            'attempts': _safe_json_payload(attempts_summary),
            'status': final_status,
            'error': _truncate_text(error),
            'timestamp': ts,
        }

        with open(filepath, 'w', encoding='utf-8') as file_handle:
            json.dump(payload, file_handle, ensure_ascii=False, indent=2, default=str)

        logger.info('benchmark debug summary written: %s', filepath)
    except Exception as exc:
        logger.warning('benchmark run_id=%s failed to write debug summary error=%s', run_id, exc)


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
        run_id: int,
        db: Session,
        agent_name: str,
        fixture: BenchmarkFixture,
        model_spec: dict[str, Any],
    ):
        provider, model_name, base_url, api_key = self._resolve_provider_config(model_spec)
        logger.info(
            'benchmark run_id=%s building agent agent_name=%s provider=%s model_name=%s',
            run_id,
            agent_name,
            provider,
            model_name,
        )
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
        fixture_inputs = fixture.inputs if isinstance(fixture.inputs, dict) else {}
        fixture_config = fixture.config if isinstance(fixture.config, dict) else {}

        override_system_prompt = str(fixture_config.get('system_prompt') or '').strip()
        if override_system_prompt:
            sys_prompt = override_system_prompt
        else:
            fallback = DEFAULT_PROMPTS.get(agent_name, {})
            fallback_system = fallback.get('system', f'You are the {agent_name} agent.')
            fallback_user = fallback.get('user', '')
            variables = {
                'pair': fixture_inputs.get('symbol') or fixture_inputs.get('pair') or 'BENCH',
                'timeframe': fixture_inputs.get('timeframe') or 'H1',
            }
            try:
                rendered = PromptTemplateService().render(
                    db,
                    agent_name,
                    fallback_system,
                    fallback_user,
                    variables,
                )
                sys_prompt = str(rendered.get('system_prompt') or fallback_system)
            except Exception as exc:
                logger.warning(
                    'benchmark run_id=%s prompt render failed for agent_name=%s; using fallback: %s',
                    run_id,
                    agent_name,
                    exc,
                )
                sys_prompt = str(fallback_system)
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
        model_provider = str(model_spec.get('provider') or 'ollama').strip().lower()
        model_name = str(model_spec.get('model_name') or '').strip()
        model_parameter_keys = sorted(list((model_spec.get('parameters') or {}).keys())) if isinstance(model_spec.get('parameters'), dict) else []

        logger.info(
            'benchmark run_id=%s start execution fixture_id=%s scenario_type=%s model_provider=%s model_name=%s model_parameter_keys=%s repetitions=%s',
            benchmark_run.id,
            benchmark_run.fixture_id,
            scenario_type,
            model_provider,
            model_name,
            model_parameter_keys,
            repetitions,
        )

        # Build an AgentScope Msg from fixture inputs — agents expect Msg, not str
        raw_inputs = fixture.inputs or {}
        context_text = str(raw_inputs.get('context') or '')
        input_keys = sorted(list(raw_inputs.keys())) if isinstance(raw_inputs, dict) else []
        # Enrich with structured fixture inputs if available
        extra_parts: list[str] = []
        for key in ('news_context', 'portfolio_state', 'execution_context',
                     'phase1_results', 'debate_results'):
            val = raw_inputs.get(key)
            if val:
                extra_parts.append(f"{key}: {json.dumps(val) if isinstance(val, (dict, list)) else val}")
        if extra_parts:
            context_text = context_text + '\n\n' + '\n'.join(extra_parts) if context_text else '\n'.join(extra_parts)
        if not context_text:
            context_text = f"Benchmark analysis for {fixture.agent_name}"
        context_msg = Msg("user", context_text, "user")
        logger.debug(
            'benchmark run_id=%s built context_msg length=%s input_keys=%s',
            benchmark_run.id,
            len(context_text),
            input_keys,
        )

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
            agent = await self._build_agent(run_id=int(benchmark_run.id), db=db, agent_name=fixture.agent_name, fixture=fixture, model_spec=model_spec)
            logger.info(
                'benchmark run_id=%s calling scenario=%s analysis_run_id=%s',
                benchmark_run.id,
                BenchmarkScenarioType.SINGLE_AGENT,
                analysis_run_id_single,
            )
            execution = await run_single_agent_scenario(
                run_id=int(benchmark_run.id),
                analysis_run_id=analysis_run_id_single,
                agent_name=fixture.agent_name,
                agent=agent,
                context_msg=context_msg,
                repetitions=repetitions,
            )
            logger.info(
                'benchmark run_id=%s scenario=%s completed status=%s attempts=%s',
                benchmark_run.id,
                BenchmarkScenarioType.SINGLE_AGENT,
                execution.status,
                len(execution.attempts),
            )
        elif scenario_type == BenchmarkScenarioType.DEBATE_BUNDLE:
            analysis_run_id_debate = _create_analysis_run_record('debate-bundle')
            created_analysis_run_ids.add(analysis_run_id_debate)
            bullish = await self._build_agent(run_id=int(benchmark_run.id), db=db, agent_name='bullish-researcher', fixture=fixture, model_spec=model_spec)
            bearish = await self._build_agent(run_id=int(benchmark_run.id), db=db, agent_name='bearish-researcher', fixture=fixture, model_spec=model_spec)
            trader = await self._build_agent(run_id=int(benchmark_run.id), db=db, agent_name='trader-agent', fixture=fixture, model_spec=model_spec)
            llm_enabled_flags = {
                'bullish-researcher': bool((fixture.config or {}).get('llm_enabled', True)),
                'bearish-researcher': bool((fixture.config or {}).get('llm_enabled', True)),
                'trader-agent': bool((fixture.config or {}).get('llm_enabled', True)),
            }
            logger.info(
                'benchmark run_id=%s calling scenario=%s analysis_run_id=%s llm_enabled_flags=%s',
                benchmark_run.id,
                BenchmarkScenarioType.DEBATE_BUNDLE,
                analysis_run_id_debate,
                llm_enabled_flags,
            )
            execution = await run_debate_bundle_scenario(
                run_id=int(benchmark_run.id),
                analysis_run_id=analysis_run_id_debate,
                llm_enabled_flags=llm_enabled_flags,
                bullish_agent=bullish,
                bearish_agent=bearish,
                trader_agent=trader,
                context_msg=context_msg,
                repetitions=repetitions,
            )
            logger.info(
                'benchmark run_id=%s scenario=%s completed status=%s attempts=%s',
                benchmark_run.id,
                BenchmarkScenarioType.DEBATE_BUNDLE,
                execution.status,
                len(execution.attempts),
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
                    await self._build_agent(run_id=int(benchmark_run.id), db=db, agent_name=agent_name, fixture=fixture, model_spec=model_spec),
                )
                for agent_name in ordered_agent_names
            ]
            logger.info(
                'benchmark run_id=%s calling scenario=%s analysis_run_id=%s agents=%s',
                benchmark_run.id,
                BenchmarkScenarioType.FULL_PIPELINE,
                analysis_run_id_pipeline,
                ordered_agent_names,
            )
            execution = await run_full_pipeline_scenario(
                run_id=int(benchmark_run.id),
                analysis_run_id=analysis_run_id_pipeline,
                ordered_agents=ordered_agents,
                context_msg=context_msg,
                repetitions=repetitions,
            )
            logger.info(
                'benchmark run_id=%s scenario=%s completed status=%s attempts=%s',
                benchmark_run.id,
                BenchmarkScenarioType.FULL_PIPELINE,
                execution.status,
                len(execution.attempts),
            )
        else:
            raise HTTPException(status_code=422, detail=f'Unsupported scenario_type {scenario_type}')

        if execution.status == BenchmarkRunStatus.SKIPPED_DEBATE:
            logger.info('benchmark run_id=%s scenario skipped status=%s', benchmark_run.id, execution.status)
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
        attempts_summary: list[dict[str, Any]] = []
        attempt_to_summary: list[tuple[BenchmarkAttempt, dict[str, Any]]] = []

        for scenario_attempt in execution.attempts:
            raw_output_preview = json.dumps(scenario_attempt.raw_output, default=str)[:500]
            raw_output_keys = sorted(list(scenario_attempt.raw_output.keys())) if isinstance(scenario_attempt.raw_output, dict) else []
            logger.debug(
                'benchmark run_id=%s extracted raw_output agent_name=%s attempt_number=%s raw_output_keys=%s raw_output_preview=%s',
                benchmark_run.id,
                scenario_attempt.agent_name,
                scenario_attempt.attempt_number,
                raw_output_keys,
                raw_output_preview,
            )
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
            logger.info(
                'benchmark run_id=%s scored attempt agent_name=%s attempt_number=%s schema_validity=%.4f completeness=%.4f tool_policy=%.4f reference_consistency=%.4f aggregate=%.4f',
                benchmark_run.id,
                scenario_attempt.agent_name,
                scenario_attempt.attempt_number,
                score['schema_validity_score'],
                score['completeness_score'],
                score['tool_policy_compliance_score'],
                score['reference_consistency_score'],
                score['aggregate_score'],
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
            summary_row = {
                'agent_name': scenario_attempt.agent_name,
                'attempt_number': scenario_attempt.attempt_number,
                'scores': {
                    'schema_validity': score['schema_validity_score'],
                    'completeness': score['completeness_score'],
                    'tool_policy': score['tool_policy_compliance_score'],
                    'reference_consistency': score['reference_consistency_score'],
                    'stability': None,
                    'overall': score['aggregate_score'],
                },
                'raw_output_keys': raw_output_keys,
                'analysis_run_id': scenario_attempt.analysis_run_id,
                'llm_calls_count': 0,
            }
            attempts_summary.append(summary_row)
            attempt_to_summary.append((attempt, summary_row))

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

        for attempt_obj, summary_row in attempt_to_summary:
            summary_row['llm_calls_count'] = int(attempt_obj.llm_calls_count or 0)

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
            logger.error(
                'benchmark run_id=%s final status=%s attempts=%s cases=%s reason=max_llm_calls_exceeded total_llm_calls=%s limit=%s',
                benchmark_run.id,
                benchmark_run.status,
                len(execution.attempts),
                len(case_by_agent),
                total_llm_calls,
                benchmark_run.max_llm_calls,
            )
            _dump_benchmark_run_summary(
                run_id=int(benchmark_run.id),
                fixture_id=int(benchmark_run.fixture_id),
                scenario_type=str(benchmark_run.scenario_type),
                model_spec=benchmark_run.model_spec or {},
                attempts_summary=attempts_summary,
                final_status=str(benchmark_run.status),
                error=benchmark_run.error,
            )
            return benchmark_run

        for agent_name, scores in aggregate_scores_by_agent.items():
            stability = compute_stability_score(scores)
            attempts = attempts_by_agent[agent_name]
            for attempt in attempts:
                attempt.stability_score = stability
                for attempt_obj, summary_row in attempt_to_summary:
                    if attempt_obj is attempt:
                        summary_row['scores']['stability'] = stability
                        break
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
        logger.info(
            'benchmark run_id=%s final status=%s attempts=%s cases=%s',
            benchmark_run.id,
            benchmark_run.status,
            len(execution.attempts),
            len(case_by_agent),
        )
        _dump_benchmark_run_summary(
            run_id=int(benchmark_run.id),
            fixture_id=int(benchmark_run.fixture_id),
            scenario_type=str(benchmark_run.scenario_type),
            model_spec=benchmark_run.model_spec or {},
            attempts_summary=attempts_summary,
            final_status=str(benchmark_run.status),
            error=benchmark_run.error,
        )
        return benchmark_run

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.benchmark.constants import BenchmarkRunStatus
from app.services.llm.call_context import use_analysis_run_id


@dataclass
class ScenarioAttemptResult:
    agent_name: str
    attempt_number: int
    raw_output: dict[str, Any]
    analysis_run_id: int | None = None


@dataclass
class ScenarioExecutionResult:
    status: str
    attempts: list[ScenarioAttemptResult]


def _extract_output_payload(msg: Any) -> dict[str, Any]:
    if msg is None:
        return {}
    metadata = getattr(msg, 'metadata', None)
    if isinstance(metadata, dict):
        return metadata
    content = getattr(msg, 'content', None)
    if isinstance(content, dict):
        return content
    return {'text': str(getattr(msg, 'text', ''))}


async def run_single_agent_scenario(
    *,
    analysis_run_id: int | None,
    agent_name: str,
    agent,
    context_msg,
    repetitions: int,
) -> ScenarioExecutionResult:
    attempts: list[ScenarioAttemptResult] = []
    for attempt_number in range(1, repetitions + 1):
        with use_analysis_run_id(analysis_run_id):
            result_msg = await agent(context_msg)
        attempts.append(
            ScenarioAttemptResult(
                agent_name=agent_name,
                attempt_number=attempt_number,
                raw_output=_extract_output_payload(result_msg),
                analysis_run_id=analysis_run_id,
            )
        )
    return ScenarioExecutionResult(status=BenchmarkRunStatus.COMPLETED, attempts=attempts)


async def run_debate_bundle_scenario(
    *,
    analysis_run_id: int | None,
    llm_enabled_flags: dict[str, bool],
    bullish_agent,
    bearish_agent,
    trader_agent,
    context_msg,
    repetitions: int,
) -> ScenarioExecutionResult:
    if not all(llm_enabled_flags.get(agent_name, True) for agent_name in ('bullish-researcher', 'bearish-researcher', 'trader-agent')):
        return ScenarioExecutionResult(status=BenchmarkRunStatus.SKIPPED_DEBATE, attempts=[])

    attempts: list[ScenarioAttemptResult] = []
    for attempt_number in range(1, repetitions + 1):
        with use_analysis_run_id(analysis_run_id):
            bullish_msg = await bullish_agent(context_msg)
            bearish_msg = await bearish_agent(bullish_msg)
            trader_msg = await trader_agent(bearish_msg)

        attempts.append(
            ScenarioAttemptResult(
                agent_name='bullish-researcher',
                attempt_number=attempt_number,
                raw_output=_extract_output_payload(bullish_msg),
                analysis_run_id=analysis_run_id,
            )
        )
        attempts.append(
            ScenarioAttemptResult(
                agent_name='bearish-researcher',
                attempt_number=attempt_number,
                raw_output=_extract_output_payload(bearish_msg),
                analysis_run_id=analysis_run_id,
            )
        )
        attempts.append(
            ScenarioAttemptResult(
                agent_name='trader-agent',
                attempt_number=attempt_number,
                raw_output=_extract_output_payload(trader_msg),
                analysis_run_id=analysis_run_id,
            )
        )

    return ScenarioExecutionResult(status=BenchmarkRunStatus.COMPLETED, attempts=attempts)


async def run_full_pipeline_scenario(
    *,
    analysis_run_id: int | None,
    ordered_agents: list[tuple[str, Any]],
    context_msg,
    repetitions: int,
) -> ScenarioExecutionResult:
    attempts: list[ScenarioAttemptResult] = []
    for attempt_number in range(1, repetitions + 1):
        current_context = context_msg
        for agent_name, agent in ordered_agents:
            with use_analysis_run_id(analysis_run_id):
                result_msg = await agent(current_context)
            attempts.append(
                ScenarioAttemptResult(
                    agent_name=agent_name,
                    attempt_number=attempt_number,
                    raw_output=_extract_output_payload(result_msg),
                    analysis_run_id=analysis_run_id,
                )
            )
            current_context = result_msg
    return ScenarioExecutionResult(status=BenchmarkRunStatus.COMPLETED, attempts=attempts)

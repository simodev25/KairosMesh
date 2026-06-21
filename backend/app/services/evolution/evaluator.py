from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.benchmark_case import BenchmarkCase
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.db.models.evolution_candidate_evaluation import EvolutionCandidateEvaluation
from app.services.benchmark.constants import BenchmarkRunStatus
from app.services.benchmark.engine import BenchmarkEngine
from app.services.benchmark.fixtures_service import compute_fixture_hash


class BenchmarkEvaluator:
    def evaluate_candidate(
        self,
        db: Session,
        *,
        campaign: EvolutionCampaign,
        candidate: EvolutionCandidate,
    ) -> EvolutionCandidateEvaluation:
        fixture_inputs = dict((campaign.evaluation_config or {}).get('inputs') or {})
        fixture_config = dict((campaign.evaluation_config or {}).get('config') or {})
        fixture_config['system_prompt'] = candidate.system_prompt
        fixture_config['user_prompt_template'] = candidate.user_prompt_template
        fixture_hash = compute_fixture_hash(agent_name=campaign.agent_name, inputs=fixture_inputs, config=fixture_config)
        created_by_id = int(campaign.created_by_id or 1)

        fixture = BenchmarkFixture(
            name=f'evolution-campaign-{campaign.id}-candidate-{candidate.id}',
            agent_name=campaign.agent_name,
            version=1,
            hash=fixture_hash,
            inputs=fixture_inputs,
            config=fixture_config,
            default_scoring_weights=(campaign.evaluation_config or {}).get('scoring_weights'),
            is_active=True,
            is_deleted=False,
            created_by_id=created_by_id,
        )
        db.add(fixture)
        db.flush()

        run = BenchmarkRun(
            fixture_id=fixture.id,
            fixture_hash=fixture.hash,
            model_spec={
                'provider': campaign.provider,
                'model_name': campaign.model_name,
                'parameters': campaign.model_parameters or {},
            },
            scenario_type=str((campaign.evaluation_config or {}).get('scenario_type') or 'single-agent'),
            status=BenchmarkRunStatus.PENDING,
            repetitions=int((campaign.evaluation_config or {}).get('repetitions') or 2),
            max_llm_calls=campaign.max_llm_calls,
            effective_scoring_weights=(campaign.evaluation_config or {}).get('scoring_weights'),
            created_by_id=created_by_id,
        )
        db.add(run)
        db.flush()

        result_run = asyncio.run(BenchmarkEngine().execute_run(db, run))
        if result_run.status not in {BenchmarkRunStatus.COMPLETED, BenchmarkRunStatus.SKIPPED_DEBATE}:
            raise RuntimeError(f'benchmark evaluation failed with status={result_run.status}')

        case_rows = db.query(BenchmarkCase).filter(BenchmarkCase.run_id == run.id).all()
        aggregate_scores: list[float] = []
        metrics: dict[str, Any] = {
            'schema_validity_score': [],
            'completeness_score': [],
            'tool_policy_compliance_score': [],
            'reference_consistency_score': [],
            'stability_score': [],
        }
        total_llm_calls = 0

        for case in case_rows:
            if case.aggregate_score is not None:
                aggregate_scores.append(float(case.aggregate_score))
            for attempt in case.attempts:
                total_llm_calls += int(attempt.llm_calls_count or 0)
                metrics['schema_validity_score'].append(float(attempt.schema_validity_score or 0.0))
                metrics['completeness_score'].append(float(attempt.completeness_score or 0.0))
                metrics['tool_policy_compliance_score'].append(float(attempt.tool_policy_compliance_score or 0.0))
                metrics['reference_consistency_score'].append(float(attempt.reference_consistency_score or 0.0))
                metrics['stability_score'].append(float(attempt.stability_score or 0.0))

        aggregate_score = (sum(aggregate_scores) / len(aggregate_scores)) if aggregate_scores else 0.0
        metrics_summary = {
            key: (sum(values) / len(values) if values else 0.0)
            for key, values in metrics.items()
        }

        evaluation = EvolutionCandidateEvaluation(
            candidate_id=candidate.id,
            evaluation_type='benchmark',
            benchmark_run_id=run.id,
            metrics=metrics_summary,
            aggregate_score=aggregate_score,
        )
        db.add(evaluation)

        # Estimate evaluation cost from total LLM calls (rough: $0.001 per call)
        evaluation_cost = total_llm_calls * 0.001

        candidate.metrics_summary = metrics_summary
        candidate.fitness_score = aggregate_score
        candidate.status = 'evaluated'
        candidate.llm_calls_count = (candidate.llm_calls_count or 0) + total_llm_calls
        # Add evaluation cost to existing mutation cost (additive)
        candidate.llm_cost_usd = float(candidate.llm_cost_usd or 0.0) + evaluation_cost
        db.commit()
        db.refresh(evaluation)
        return evaluation

import type { BenchmarkAttempt, BenchmarkRunDetail, BenchmarkScoresV1 } from '../types/benchmark';

export const BENCHMARK_METRIC_KEYS: Array<keyof BenchmarkScoresV1> = [
  'schema_validity',
  'completeness',
  'tool_policy',
  'reference_consistency',
  'stability',
  'overall',
];

export const BENCHMARK_METRIC_LABELS: Record<keyof BenchmarkScoresV1, string> = {
  schema_validity: 'Schema',
  completeness: 'Complétude',
  tool_policy: 'Policy',
  reference_consistency: 'Référence',
  stability: 'Stabilité',
  overall: 'Global',
};

export function getBenchmarkScoreTone(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 0.7) return 'success';
  if (score >= 0.4) return 'warning';
  return 'danger';
}

export function getBenchmarkScoreClass(score: number): string {
  const tone = getBenchmarkScoreTone(score);
  if (tone === 'success') return 'text-success';
  if (tone === 'warning') return 'text-warning';
  return 'text-danger';
}

export function formatBenchmarkScore(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return '--';
  return score.toFixed(2);
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function toBenchmarkScores(attempts: BenchmarkAttempt[]): BenchmarkScoresV1 {
  const schemaValidity = average(attempts.map((attempt) => attempt.schema_validity_score));
  const completeness = average(attempts.map((attempt) => attempt.completeness_score));
  const toolPolicy = average(attempts.map((attempt) => attempt.tool_policy_compliance_score));
  const referenceConsistency = average(attempts.map((attempt) => attempt.reference_consistency_score));
  const stability = average(
    attempts
      .map((attempt) => attempt.stability_score)
      .filter((value): value is number => typeof value === 'number'),
  );
  const overall = average(attempts.map((attempt) => attempt.aggregate_score));

  return {
    schema_validity: schemaValidity,
    completeness,
    tool_policy: toolPolicy,
    reference_consistency: referenceConsistency,
    stability,
    overall,
  };
}

export function computeBenchmarkRunScores(runDetail: BenchmarkRunDetail): BenchmarkScoresV1 {
  const attempts = runDetail.cases.flatMap((benchmarkCase) => benchmarkCase.attempts ?? []);
  return toBenchmarkScores(attempts);
}

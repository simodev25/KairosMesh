class BenchmarkRunStatus:
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SKIPPED_DEBATE = 'SKIPPED_DEBATE'
    CANCELLED = 'CANCELLED'


class BenchmarkScenarioType:
    SINGLE_AGENT = 'single-agent'
    DEBATE_BUNDLE = 'debate-bundle'
    FULL_PIPELINE = 'full-pipeline'

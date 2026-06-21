from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db.models.benchmark_attempt import BenchmarkAttempt  # noqa: F401
from app.db.models.benchmark_case import BenchmarkCase  # noqa: F401
from app.db.models.benchmark_fixture import BenchmarkFixture  # noqa: F401
from app.db.models.benchmark_run import BenchmarkRun  # noqa: F401
from app.db.models.llm_call_log import LlmCallLog  # noqa: F401
from app.db.models.run import AnalysisRun  # noqa: F401
from app.db.models.user import User  # noqa: F401


def test_benchmark_tables_are_registered_and_created() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert 'benchmark_fixtures' in table_names
    assert 'benchmark_runs' in table_names
    assert 'benchmark_cases' in table_names
    assert 'benchmark_attempts' in table_names


def test_llm_call_logs_has_analysis_run_link_column() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    llm_columns = {column['name'] for column in inspector.get_columns('llm_call_logs')}
    assert 'analysis_run_id' in llm_columns

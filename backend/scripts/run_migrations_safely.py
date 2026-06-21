from __future__ import annotations

import subprocess
import os

from sqlalchemy import create_engine, inspect


LEGACY_BASELINE_REVISION = '0013_gh24_benchmark_tables'


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    database_url = os.environ.get('DATABASE_URL', 'postgresql+psycopg2://trading:trading@postgres:5432/trading_platform')
    engine = create_engine(database_url)
    with engine.connect() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())

    has_alembic_history = 'alembic_version' in table_names
    has_user_tables = any(name != 'alembic_version' for name in table_names)

    if has_alembic_history:
        _run(['alembic', 'upgrade', 'head'])
        return 0

    if not has_user_tables:
        _run(['alembic', 'upgrade', 'head'])
        return 0

    # Legacy DB created without Alembic history:
    # stamp at last known revision for current schema lineage, then apply forward fixes.
    _run(['alembic', 'stamp', LEGACY_BASELINE_REVISION])
    _run(['alembic', 'upgrade', 'head'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

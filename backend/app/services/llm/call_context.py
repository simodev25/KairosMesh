from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_analysis_run_id_ctx: ContextVar[int | None] = ContextVar('analysis_run_id', default=None)


def get_current_analysis_run_id() -> int | None:
    return _analysis_run_id_ctx.get()


@contextmanager
def use_analysis_run_id(analysis_run_id: int | None) -> Iterator[None]:
    token = _analysis_run_id_ctx.set(analysis_run_id)
    try:
        yield
    finally:
        _analysis_run_id_ctx.reset(token)

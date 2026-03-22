"""Lightweight correlation/causation ID propagation for request tracing.

Provides a thread-local context that carries ``correlation_id`` (ties all
events in a single user-facing request) and ``causation_id`` (ties an
event to its direct parent).  These IDs are injected into log records and
trace payloads so that any run, agent step, tool call, or memory
operation can be correlated back to its root trigger.

Usage::

    from app.observability.trace_context import trace_ctx

    # At request boundary (middleware / API route)
    trace_ctx.set(correlation_id="run-42", causation_id="api-request")

    # Downstream code reads the current context
    cid = trace_ctx.correlation_id

    # When spawning a child operation
    trace_ctx.push_causation("agent-step-technical")
    ...
    trace_ctx.pop_causation()
"""

from __future__ import annotations

import threading
import uuid
from typing import Any


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class _TraceContext(threading.local):
    correlation_id: str = ""
    _causation_stack: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.correlation_id = ""
        self._causation_stack = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, *, correlation_id: str | None = None, causation_id: str | None = None) -> None:
        self.correlation_id = correlation_id or _new_id()
        self._causation_stack = [causation_id or self.correlation_id]

    @property
    def causation_id(self) -> str:
        return self._causation_stack[-1] if self._causation_stack else self.correlation_id

    def push_causation(self, causation_id: str | None = None) -> str:
        cid = causation_id or _new_id()
        self._causation_stack.append(cid)
        return cid

    def pop_causation(self) -> str | None:
        if len(self._causation_stack) > 1:
            return self._causation_stack.pop()
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    def clear(self) -> None:
        self.correlation_id = ""
        self._causation_stack = []


trace_ctx = _TraceContext()

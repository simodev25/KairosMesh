from __future__ import annotations

import logging
import os
import threading

from prometheus_client import CollectorRegistry, REGISTRY, generate_latest, multiprocess, start_http_server

logger = logging.getLogger(__name__)

_worker_metrics_lock = threading.Lock()
_worker_metrics_started = False


def build_metrics_payload() -> bytes:
    multiproc_dir = str(os.getenv('PROMETHEUS_MULTIPROC_DIR') or '').strip()
    if not multiproc_dir:
        return generate_latest(REGISTRY)

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return generate_latest(registry)


def start_worker_metrics_server(port: int) -> None:
    global _worker_metrics_started

    with _worker_metrics_lock:
        if _worker_metrics_started:
            return

        multiproc_dir = str(os.getenv('PROMETHEUS_MULTIPROC_DIR') or '').strip()
        registry = REGISTRY
        if multiproc_dir:
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)

        start_http_server(port, addr='0.0.0.0', registry=registry)
        _worker_metrics_started = True
        logger.info('Prometheus worker metrics server started on port=%s multiprocess=%s', port, bool(multiproc_dir))


def mark_worker_process_dead(pid: int | None) -> None:
    multiproc_dir = str(os.getenv('PROMETHEUS_MULTIPROC_DIR') or '').strip()
    if not multiproc_dir or pid is None:
        return
    multiprocess.mark_process_dead(pid)

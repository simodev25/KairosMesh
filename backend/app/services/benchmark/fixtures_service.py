from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.benchmark_fixture import BenchmarkFixture


def compute_fixture_hash(*, agent_name: str, inputs: dict[str, Any], config: dict[str, Any]) -> str:
    payload = {
        'agent_name': agent_name,
        'inputs': inputs,
        'config': config,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def create_fixture(
    db: Session,
    *,
    name: str,
    agent_name: str,
    inputs: dict[str, Any],
    config: dict[str, Any],
    created_by_id: int,
    default_scoring_weights: dict[str, float] | None = None,
) -> BenchmarkFixture:
    fixture_hash = compute_fixture_hash(agent_name=agent_name, inputs=inputs, config=config)
    fixture = BenchmarkFixture(
        name=name,
        agent_name=agent_name,
        version=1,
        hash=fixture_hash,
        inputs=inputs,
        config=config,
        default_scoring_weights=default_scoring_weights,
        is_active=True,
        is_deleted=False,
        created_by_id=created_by_id,
    )
    db.add(fixture)
    db.commit()
    db.refresh(fixture)
    return fixture


def list_fixtures(
    db: Session,
    *,
    agent_name: str | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[BenchmarkFixture]:
    query = db.query(BenchmarkFixture).filter(BenchmarkFixture.is_deleted.is_(False))
    if agent_name:
        query = query.filter(BenchmarkFixture.agent_name == agent_name)
    if is_active is not None:
        query = query.filter(BenchmarkFixture.is_active == is_active)
    return query.order_by(BenchmarkFixture.created_at.desc()).offset(offset).limit(limit).all()


def get_fixture_or_404(db: Session, fixture_id: int) -> BenchmarkFixture:
    fixture = db.get(BenchmarkFixture, fixture_id)
    if fixture is None or fixture.is_deleted:
        raise HTTPException(status_code=404, detail='Benchmark fixture not found')
    return fixture


def patch_fixture_activation(db: Session, fixture_id: int, *, is_active: bool) -> BenchmarkFixture:
    fixture = get_fixture_or_404(db, fixture_id)
    fixture.is_active = is_active
    db.commit()
    db.refresh(fixture)
    return fixture


def soft_delete_fixture(db: Session, fixture_id: int) -> None:
    fixture = get_fixture_or_404(db, fixture_id)
    fixture.is_active = False
    fixture.is_deleted = True
    db.commit()

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.memory_entry import MemoryEntry
from app.db.models.run import AnalysisRun

logger = logging.getLogger(__name__)


class VectorMemoryService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.vector_size = self.settings.memory_vector_size
        if self.vector_size != 64:
            logger.warning('memory_vector_size=%s is not supported with current pgvector schema; forcing 64', self.vector_size)
            self.vector_size = 64
        self.collection = self.settings.qdrant_collection
        self._qdrant: QdrantClient | None = None
        self._collection_ready = False

        try:
            self._qdrant = QdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key or None, timeout=3.0)
        except Exception as exc:  # pragma: no cover
            logger.warning('qdrant unavailable: %s', exc)
            self._qdrant = None

    def _ensure_collection(self) -> None:
        if not self._qdrant or self._collection_ready:
            return
        try:
            existing = {item.name for item in self._qdrant.get_collections().collections}
            if self.collection not in existing:
                self._qdrant.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
            self._collection_ready = True
        except Exception as exc:  # pragma: no cover
            logger.warning('qdrant collection init failed: %s', exc)

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        values: list[float] = []
        for i in range(self.vector_size):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)

        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        an = math.sqrt(sum(x * x for x in a)) or 1.0
        bn = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (an * bn)

    @staticmethod
    def _dedupe_search_results(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in items:
            summary = str(item.get('summary', '') or '').strip()
            source_type = str(item.get('source_type', '') or '').strip()
            pair = str(item.get('pair', '') or '').strip()
            key = (pair, source_type, summary)
            if not summary or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def store_memory(
        self,
        db: Session,
        pair: str,
        timeframe: str,
        source_type: str,
        summary: str,
        payload: dict[str, Any],
        run_id: int | None = None,
    ) -> MemoryEntry:
        embedding = self._embed(f'{pair}|{timeframe}|{summary}')
        entry = MemoryEntry(
            pair=pair,
            timeframe=timeframe,
            source_type=source_type,
            summary=summary,
            embedding=embedding,
            payload=payload,
            run_id=run_id,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        if self._qdrant:
            try:
                self._ensure_collection()
                self._qdrant.upsert(
                    collection_name=self.collection,
                    wait=False,
                    points=[
                        PointStruct(
                            id=entry.id,
                            vector=embedding,
                            payload={
                                'pair': pair,
                                'timeframe': timeframe,
                                'summary': summary,
                            },
                        )
                    ],
                )
            except Exception as exc:  # pragma: no cover
                logger.warning('qdrant upsert failed for memory id=%s: %s', entry.id, exc)

        return entry

    def add_run_memory(self, db: Session, run: AnalysisRun) -> MemoryEntry:
        decision = run.decision or {}
        summary = (
            f"{run.pair} {run.timeframe} -> {decision.get('decision', 'HOLD')} "
            f"confidence={decision.get('confidence', 0)} "
            f"net_score={decision.get('net_score', 0)}"
        )
        payload = {
            'risk': decision.get('risk', {}),
            'execution': decision.get('execution', {}),
            'status': run.status,
            'created_at': run.created_at.isoformat(),
        }
        return self.store_memory(
            db=db,
            pair=run.pair,
            timeframe=run.timeframe,
            source_type='run_outcome',
            summary=summary,
            payload=payload,
            run_id=run.id,
        )

    def search(
        self,
        db: Session,
        pair: str,
        timeframe: str,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        query_embedding = self._embed(query)

        if self._qdrant:
            try:
                self._ensure_collection()
                results = self._qdrant.search(
                    collection_name=self.collection,
                    query_vector=query_embedding,
                    query_filter=Filter(
                        must=[
                            FieldCondition(key='pair', match=MatchValue(value=pair)),
                            FieldCondition(key='timeframe', match=MatchValue(value=timeframe)),
                        ]
                    ),
                    limit=limit,
                    with_payload=True,
                )
                memory_ids = [int(item.id) for item in results]
                if memory_ids:
                    entries = (
                        db.query(MemoryEntry)
                        .filter(
                            MemoryEntry.id.in_(memory_ids),
                            MemoryEntry.pair == pair,
                            MemoryEntry.timeframe == timeframe,
                        )
                        .all()
                    )
                    by_id = {entry.id: entry for entry in entries}
                    ordered = [by_id[mid] for mid in memory_ids if mid in by_id]
                    score_by_id = {int(item.id): float(item.score) for item in results}
                    results = [
                        {
                            'id': entry.id,
                            'pair': entry.pair,
                            'timeframe': entry.timeframe,
                            'summary': entry.summary,
                            'source_type': entry.source_type,
                            'score': score_by_id.get(entry.id, 0.0),
                        }
                        for entry in ordered
                    ]
                    return self._dedupe_search_results(results, limit)
            except Exception as exc:  # pragma: no cover
                logger.warning('qdrant search failed: %s', exc)

        candidates = (
            db.query(MemoryEntry)
            .filter(MemoryEntry.pair == pair, MemoryEntry.timeframe == timeframe)
            .order_by(MemoryEntry.created_at.desc())
            .limit(100)
            .all()
        )

        scored = []
        for entry in candidates:
            similarity = self._cosine(entry.embedding, query_embedding)
            scored.append((similarity, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:limit]

        results = [
            {
                'id': entry.id,
                'pair': entry.pair,
                'timeframe': entry.timeframe,
                'summary': entry.summary,
                'source_type': entry.source_type,
                'score': round(score, 6),
            }
            for score, entry in top
        ]
        return self._dedupe_search_results(results, limit)

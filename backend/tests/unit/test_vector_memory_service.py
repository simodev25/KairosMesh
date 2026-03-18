from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.memory_entry import MemoryEntry
from app.services.memory.vector_memory import VectorMemoryService


class _FakePoint:
    def __init__(self, item_id: int, score: float) -> None:
        self.id = item_id
        self.score = score


class _FakeQdrant:
    def __init__(self) -> None:
        self.search_kwargs: dict = {}

    def search(self, **kwargs):
        self.search_kwargs = kwargs
        # Return mixed ids to ensure SQL side still enforces pair/timeframe boundaries.
        return [_FakePoint(1, 0.9), _FakePoint(2, 0.8)]


def test_qdrant_search_is_scoped_by_pair_and_timeframe(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        eur_h1 = MemoryEntry(
            pair='EURUSD',
            timeframe='H1',
            source_type='run_outcome',
            summary='eur h1 memory',
            embedding=[0.1] * 64,
            payload={},
        )
        gbp_h1 = MemoryEntry(
            pair='GBPUSD',
            timeframe='H1',
            source_type='run_outcome',
            summary='gbp h1 memory',
            embedding=[0.2] * 64,
            payload={},
        )
        db.add_all([eur_h1, gbp_h1])
        db.commit()

        service = VectorMemoryService()
        fake_qdrant = _FakeQdrant()
        service._qdrant = fake_qdrant
        service._collection_ready = True

        monkeypatch.setattr(service, '_ensure_collection', lambda: None)
        monkeypatch.setattr(service, '_embed', lambda _text: [0.01] * 64)

        results = service.search(
            db=db,
            pair='EURUSD',
            timeframe='H1',
            query='eur trend',
            limit=5,
        )

        assert len(results) == 1
        assert results[0]['id'] == eur_h1.id
        assert results[0]['pair'] == 'EURUSD'
        assert results[0]['timeframe'] == 'H1'

        query_filter = fake_qdrant.search_kwargs.get('query_filter')
        assert query_filter is not None
        must_filters = list(getattr(query_filter, 'must', []))
        assert any(getattr(item, 'key', None) == 'pair' and getattr(item.match, 'value', None) == 'EURUSD' for item in must_filters)
        assert any(getattr(item, 'key', None) == 'timeframe' and getattr(item.match, 'value', None) == 'H1' for item in must_filters)


def test_search_deduplicates_identical_memory_summaries() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        db.add_all(
            [
                MemoryEntry(
                    pair='EURUSD',
                    timeframe='M15',
                    source_type='run_outcome',
                    summary='EURUSD M15 -> SELL confidence=0.8 net_score=-0.5',
                    embedding=[0.1] * 64,
                    payload={},
                ),
                MemoryEntry(
                    pair='EURUSD',
                    timeframe='M15',
                    source_type='run_outcome',
                    summary='EURUSD M15 -> SELL confidence=0.8 net_score=-0.5',
                    embedding=[0.1] * 64,
                    payload={},
                ),
            ]
        )
        db.commit()

        service = VectorMemoryService()
        service._qdrant = None

        results = service.search(
            db=db,
            pair='EURUSD',
            timeframe='M15',
            query='eurusd m15 bearish trend',
            limit=5,
        )

        assert len(results) == 1
        assert results[0]['summary'] == 'EURUSD M15 -> SELL confidence=0.8 net_score=-0.5'

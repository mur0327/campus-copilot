import pytest

from tasks.storage import invalidate_conflicts_for_document


@pytest.mark.asyncio
async def test_invalidate_conflicts_for_document_deletes_related_pairs():
    calls = []

    class FakeConnection:
        async def execute(self, query, document_id):
            calls.append((query, document_id))

    await invalidate_conflicts_for_document(FakeConnection(), "doc-1")

    assert calls
    assert "conflict_pairs" in calls[0][0]
    assert calls[0][1] == "doc-1"

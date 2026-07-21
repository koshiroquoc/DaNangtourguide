from localguide_assistant.indexer import index_is_current


class FakeIndices:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    def exists(self, *, index: str) -> bool:
        return self._exists


class FakeClient:
    def __init__(self, *, exists: bool, count: int) -> None:
        self.indices = FakeIndices(exists)
        self._count = count

    def count(self, *, index: str):
        return {"count": self._count}


def test_current_index_requires_matching_document_count() -> None:
    assert index_is_current(
        FakeClient(exists=True, count=299),
        index_name="places",
        expected_count=299,
    )
    assert not index_is_current(
        FakeClient(exists=True, count=298),
        index_name="places",
        expected_count=299,
    )
    assert not index_is_current(
        FakeClient(exists=False, count=299),
        index_name="places",
        expected_count=299,
    )

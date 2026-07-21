from localguide_assistant.indexer import build_index_mapping, index_is_current


class FakeIndices:
    def __init__(self, exists: bool, dataset_sha256: str = "abc") -> None:
        self._exists = exists
        self._dataset_sha256 = dataset_sha256

    def exists(self, *, index: str) -> bool:
        return self._exists

    def get_mapping(self, *, index: str):
        return {
            index: {"mappings": {"_meta": {"dataset_sha256": self._dataset_sha256}}}
        }


class FakeClient:
    def __init__(
        self, *, exists: bool, count: int, dataset_sha256: str = "abc"
    ) -> None:
        self.indices = FakeIndices(exists, dataset_sha256)
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


def test_current_index_requires_matching_dataset_fingerprint() -> None:
    assert index_is_current(
        FakeClient(exists=True, count=100),
        index_name="places",
        expected_count=100,
        dataset_sha256="abc",
    )
    assert not index_is_current(
        FakeClient(exists=True, count=100, dataset_sha256="old"),
        index_name="places",
        expected_count=100,
        dataset_sha256="abc",
    )


def test_mapping_uses_runtime_embedding_dimensions_and_fingerprint() -> None:
    mapping = build_index_mapping(vector_dims=768, dataset_sha256="digest")

    assert mapping["mappings"]["properties"]["vector_search"]["dims"] == 768
    assert mapping["mappings"]["_meta"]["dataset_sha256"] == "digest"

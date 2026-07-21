from typing import Any

from localguide_assistant.service import RAGService


class FakeRetriever:
    def hybrid_search(
        self, query: str, *, top_k: int, type_filter: str | None
    ) -> list[dict[str, Any]]:
        assert query == "cheap breakfast"
        assert top_k == 3
        assert type_filter == "eat"
        return [
            {
                "id": "eat_001",
                "name": "Breakfast Place",
                "type": "eat",
                "description": "noodles",
                "time": "morning",
                "price": "30k VND",
                "location": "Central Da Nang",
                "area": "center",
                "note": "Local breakfast",
            }
        ]


class FakeGenerator:
    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.prompt = prompt
        return "Try Breakfast Place [S1]."


def test_service_returns_sources_and_latency_without_repeating_work() -> None:
    generator = FakeGenerator()
    service = RAGService(FakeRetriever(), generator)

    response = service.ask("cheap breakfast", type_filter="eat", top_k=3)

    assert response.answer == "Try Breakfast Place [S1]."
    assert response.sources[0]["id"] == "eat_001"
    assert response.latency_ms["total"] >= 0
    assert response.request_id
    assert "[S1]" in generator.prompt
    assert "cheap breakfast" in generator.prompt

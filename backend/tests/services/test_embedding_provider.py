from types import SimpleNamespace

import pytest

from app.services.embedding_provider import VoyageEmbedder


class RetryableError(Exception):
    status_code = 500


class FatalError(Exception):
    status_code = 400


class FakeClient:
    def __init__(self, failures: list[Exception] | None = None) -> None:
        self.failures = failures or []
        self.calls = []

    def embed(self, texts, *, model, input_type):
        self.calls.append({"texts": texts, "model": model, "input_type": input_type})
        if self.failures:
            raise self.failures.pop(0)
        return SimpleNamespace(embeddings=[[0.25, 2] for _ in texts])


def test_voyage_embedder_embeds_queries_with_input_type():
    client = FakeClient()
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="query",
        api_key="key",
        client_factory=lambda: client,
    )

    embeddings = embedder.encode(["휴학 신청"])

    assert embeddings == [[0.25, 2.0]]
    assert client.calls == [
        {
            "texts": ["휴학 신청"],
            "model": "voyage-4-large",
            "input_type": "query",
        }
    ]


def test_voyage_embedder_delays_api_key_failure_until_encode_by_default():
    embedder = VoyageEmbedder(model_name="voyage-4-large", input_type="query", api_key="")

    with pytest.raises(ValueError, match="VOYAGE_API_KEY is required"):
        embedder.encode(["휴학 신청"])


def test_voyage_embedder_retries_retryable_failures():
    client = FakeClient(failures=[RetryableError("server error")])
    sleeps = []
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="query",
        api_key="key",
        client_factory=lambda: client,
        sleep=sleeps.append,
    )

    assert embedder.encode(["a"]) == [[0.25, 2.0]]
    assert len(client.calls) == 2
    assert sleeps == [0.5]


def test_voyage_embedder_does_not_retry_fatal_failures():
    client = FakeClient(failures=[FatalError("bad request")])
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="query",
        api_key="key",
        client_factory=lambda: client,
        sleep=lambda delay: None,
    )

    with pytest.raises(FatalError):
        embedder.encode(["a"])
    assert len(client.calls) == 1

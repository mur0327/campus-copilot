from types import SimpleNamespace

import pytest

from tasks.embedding_provider import VoyageEmbedder


class RetryableError(Exception):
    status_code = 429


class FatalError(Exception):
    status_code = 401


class FakeClient:
    def __init__(self, failures: list[Exception] | None = None) -> None:
        self.failures = failures or []
        self.calls = []

    def embed(self, texts, *, model, input_type):
        self.calls.append({"texts": texts, "model": model, "input_type": input_type})
        if self.failures:
            raise self.failures.pop(0)
        return SimpleNamespace(embeddings=[[0.1, 1] for _ in texts])


def test_voyage_embedder_embeds_documents_with_input_type():
    client = FakeClient()
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="document",
        api_key="key",
        client_factory=lambda: client,
    )

    embeddings = embedder.encode(["휴학 신청 안내"])

    assert embeddings == [[0.1, 1.0]]
    assert client.calls == [
        {
            "texts": ["휴학 신청 안내"],
            "model": "voyage-4-large",
            "input_type": "document",
        }
    ]


def test_voyage_embedder_requires_api_key_when_configured():
    with pytest.raises(ValueError, match="VOYAGE_API_KEY is required"):
        VoyageEmbedder(
            model_name="voyage-4-large",
            input_type="document",
            api_key="",
            require_api_key=True,
        )


def test_voyage_embedder_retries_retryable_failures():
    client = FakeClient(failures=[RetryableError("rate limited")])
    sleeps = []
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="document",
        api_key="key",
        client_factory=lambda: client,
        sleep=sleeps.append,
    )

    assert embedder.encode(["a"]) == [[0.1, 1.0]]
    assert len(client.calls) == 2
    assert sleeps == [0.5]


def test_voyage_embedder_does_not_retry_fatal_failures():
    client = FakeClient(failures=[FatalError("unauthorized")])
    embedder = VoyageEmbedder(
        model_name="voyage-4-large",
        input_type="document",
        api_key="key",
        client_factory=lambda: client,
        sleep=lambda delay: None,
    )

    with pytest.raises(FatalError):
        embedder.encode(["a"])
    assert len(client.calls) == 1

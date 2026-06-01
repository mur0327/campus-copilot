"""Embedding provider adapters."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

VOYAGE_RETRY_DELAYS_SECONDS = (0.5, 1.0)


class VoyageClient(Protocol):
    def embed(self, texts: list[str], *, model: str, input_type: str):
        ...


class VoyageEmbedder:
    def __init__(
        self,
        *,
        model_name: str,
        input_type: str,
        api_key: str = "",
        require_api_key: bool = False,
        client_factory: Callable[[], VoyageClient] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if input_type not in {"document", "query"}:
            raise ValueError("Voyage input_type must be 'document' or 'query'")
        if require_api_key and not api_key.strip():
            raise ValueError("VOYAGE_API_KEY is required")

        self.model_name = model_name
        self.input_type = input_type
        self.api_key = api_key
        self.client_factory = client_factory
        self.sleep = sleep
        self._client: VoyageClient | None = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key.strip() and self.client_factory is None:
            raise ValueError("VOYAGE_API_KEY is required")

        return self._embed_with_retry(texts)

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        attempts = len(VOYAGE_RETRY_DELAYS_SECONDS) + 1
        for attempt in range(attempts):
            try:
                response = self._client_or_create().embed(
                    texts,
                    model=self.model_name,
                    input_type=self.input_type,
                )
                return [[float(value) for value in vector] for vector in response.embeddings]
            except Exception as exc:
                if attempt == attempts - 1 or not _is_retryable_error(exc):
                    raise
                self.sleep(VOYAGE_RETRY_DELAYS_SECONDS[attempt])
        raise RuntimeError("Voyage embedding failed")

    def _client_or_create(self) -> VoyageClient:
        if self._client is None:
            if self.client_factory is not None:
                self._client = self.client_factory()
            else:
                import voyageai

                self._client = voyageai.Client(api_key=self.api_key)
        return self._client


def _is_retryable_error(exc: Exception) -> bool:
    status_code = _status_code(exc)
    if status_code is not None:
        return status_code == 429 or status_code >= 500

    name = type(exc).__name__.lower()
    return any(marker in name for marker in ("timeout", "connection", "network"))


def _status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status_code = getattr(response, "status_code", None)
    if isinstance(response_status_code, int):
        return response_status_code
    return None

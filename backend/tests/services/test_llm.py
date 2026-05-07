import pytest

from app.services.llm import LlamaCppProvider, LLMMessage, StaticLLMProvider, validate_provider_settings


def test_static_provider_streams_answer_tokens():
    provider = StaticLLMProvider("안녕하세요")

    assert provider.generate_sync([LLMMessage(role="user", content="질문")]) == "안녕하세요"


def test_gemini_requires_model_and_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        validate_provider_settings("gemini", gemini_api_key="", gemini_model="")


def test_llama_cpp_requires_base_url_and_model():
    with pytest.raises(ValueError, match="LLAMA_CPP_BASE_URL"):
        validate_provider_settings("llama_cpp", llama_cpp_base_url="", llama_cpp_model="")


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeLlamaClient:
    def __init__(self, lines=None):
        self.lines = lines or []
        self.closed = False

    def stream(self, method, path, json):
        return FakeStreamResponse(self.lines)

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_llama_cpp_stream_skips_malformed_and_missing_tokens():
    provider = LlamaCppProvider(base_url="http://example.test", model="local")
    provider.client = FakeLlamaClient(
        [
            "data: {not-json",
            'data: {"choices":[{"delta":{"content":"휴학"}}]}',
            'data: {"choices":[]}',
            'data: {"choices":[{"delta":{}}]}',
            "data: [DONE]",
        ]
    )

    tokens = [token async for token in provider.stream([LLMMessage(role="user", content="질문")])]

    assert tokens == ["휴학"]


@pytest.mark.asyncio
async def test_llama_cpp_stream_raises_runtime_error_for_error_payload():
    provider = LlamaCppProvider(base_url="http://example.test", model="local")
    provider.client = FakeLlamaClient(['data: {"error":{"message":"model failed"}}'])

    with pytest.raises(RuntimeError, match="model failed"):
        [token async for token in provider.stream([LLMMessage(role="user", content="질문")])]


@pytest.mark.asyncio
async def test_llama_cpp_provider_closes_client():
    provider = LlamaCppProvider(base_url="http://example.test", model="local")
    fake_client = FakeLlamaClient()
    provider.client = fake_client

    await provider.aclose()

    assert fake_client.closed is True

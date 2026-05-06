from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    async def generate(self, messages: list[LLMMessage]) -> str:
        ...

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        ...


class StaticLLMProvider:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def generate_sync(self, messages: list[LLMMessage]) -> str:
        return self.answer

    async def generate(self, messages: list[LLMMessage]) -> str:
        return self.answer

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        for token in self.answer.split(" "):
            yield token + " "


def validate_provider_settings(
    provider: str,
    *,
    llama_cpp_base_url: str = "",
    llama_cpp_model: str = "",
    gemini_api_key: str = "",
    gemini_model: str = "",
) -> None:
    if provider == "llama_cpp" and (not llama_cpp_base_url.strip() or not llama_cpp_model.strip()):
        raise ValueError("LLAMA_CPP_BASE_URL and LLAMA_CPP_MODEL are required")
    if provider == "gemini" and (not gemini_api_key.strip() or not gemini_model.strip()):
        raise ValueError("GEMINI_API_KEY and GEMINI_MODEL are required")


def _message_payload(messages: list[LLMMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


class LlamaCppProvider:
    def __init__(self, *, base_url: str, model: str) -> None:
        import httpx

        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=60)
        self.model = model

    async def generate(self, messages: list[LLMMessage]) -> str:
        response = await self.client.post(
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": _message_payload(messages),
                "stream": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        import json
        from json import JSONDecodeError

        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": _message_payload(messages),
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if "error" in payload:
                    raise RuntimeError(_provider_error_message(payload["error"]))
                token = _stream_token(payload)
                if token:
                    yield token

    async def aclose(self) -> None:
        await self.client.aclose()


class GeminiProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(self, messages: list[LLMMessage]) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=_gemini_prompt(messages),
        )
        return response.text or ""

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        async for chunk in await self.client.aio.models.generate_content_stream(
            model=self.model,
            contents=_gemini_prompt(messages),
        ):
            if chunk.text:
                yield chunk.text

    async def aclose(self) -> None:
        return None


def _gemini_prompt(messages: list[LLMMessage]) -> str:
    return "\n\n".join(f"{message.role}: {message.content}" for message in messages)


def _stream_token(payload: dict) -> str:
    choices = payload.get("choices")
    if not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    delta = first_choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def _provider_error_message(error: object) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    return f"LLM provider error: {error}"

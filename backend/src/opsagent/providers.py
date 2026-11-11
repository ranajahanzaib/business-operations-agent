"""Provider boundary for local inference and deterministic orchestration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ModelReply:
    message: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ns: int | None = None


class ModelProvider(Protocol):
    name: str
    model: str

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply: ...


@dataclass
class OllamaProvider:
    model: str
    base_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.1
    num_ctx: int = 8192
    max_tokens: int = 2048
    timeout_seconds: float = 60
    client: httpx.AsyncClient | None = field(default=None, repr=False)
    name: str = "ollama"

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds))

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "messages": messages,
                "tools": tools,
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": self.num_ctx,
                    "num_predict": self.max_tokens,
                },
            },
        )
        response.raise_for_status()
        body = response.json()
        return ModelReply(
            body.get("message", {}),
            int(body.get("prompt_eval_count", 0) or 0),
            int(body.get("eval_count", 0) or 0),
            body.get("total_duration"),
        )


@dataclass
class OpenAICompatibleProvider:
    model: str
    base_url: str
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout_seconds: float = 60
    client: httpx.AsyncClient | None = field(default=None, repr=False)
    name: str = "openai_compatible"

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds))

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = await self.client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
        )
        response.raise_for_status()
        body = response.json()
        choice = body["choices"][0]["message"]
        calls = []
        for call in choice.get("tool_calls", []):
            fn = call.get("function", {})
            args = fn.get("arguments", {})
            calls.append(
                {
                    "id": call.get("id"),
                    "type": "function",
                    "function": {"name": fn.get("name"), "arguments": args},
                }
            )
        usage = body.get("usage", {})
        return ModelReply(
            {"role": "assistant", "content": choice.get("content") or "", "tool_calls": calls},
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )


class ScriptedProvider:
    """Predictable response queue for unit/integration tests; never selected in live mode."""

    name = "scripted"

    def __init__(self, replies: list[ModelReply], model: str = "scripted-fixture") -> None:
        self.replies = replies
        self.model = model
        self.calls = 0
        self.requests: list[dict[str, Any]] = []

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        self.calls += 1
        self.requests.append({"messages": list(messages), "tools": list(tools)})
        if not self.replies:
            raise RuntimeError("Scripted provider exhausted its response queue")
        return self.replies.pop(0)


def provider_from_config(
    name: str,
    model: str,
    ollama_url: str,
    openai_url: str,
    api_key: str | None = None,
    *,
    temperature: float = 0.1,
    num_ctx: int = 8192,
    max_tokens: int = 2048,
    timeout_seconds: float = 60,
) -> ModelProvider:
    if name == "ollama":
        return OllamaProvider(model, ollama_url, temperature, num_ctx, max_tokens, timeout_seconds)
    if name in {"openai", "openai_compatible"}:
        return OpenAICompatibleProvider(
            model, openai_url, api_key, temperature, max_tokens, timeout_seconds
        )
    raise ValueError(f"Unsupported provider: {name}")

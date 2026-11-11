"""Opt-in real Ollama tool-calling smoke test; never substitutes a scripted model."""

import os

import httpx
import pytest

from opsagent.api import tool_defs
from opsagent.providers import OllamaProvider


@pytest.mark.live
@pytest.mark.asyncio
async def test_ollama_selects_a_registered_read_tool():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OPSAGENT_MODEL", "qwen3:4b-instruct")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Ollama is unavailable: {exc}")
    available = {item.get("name") for item in response.json().get("models", [])}
    if model not in available:
        pytest.skip(f"Configured Ollama model {model!r} is not downloaded")

    provider = OllamaProvider(model=model, base_url=base_url)
    try:
        reply = await provider.complete(
            [
                {
                    "role": "system",
                    "content": "Select only the registered read tool that answers the request. Never propose writes.",
                },
                {
                    "role": "user",
                    "content": "List orders more than five days overdue as of 2026-11-10T12:00:00+00:00.",
                },
            ],
            [tool for tool in tool_defs() if tool["function"]["name"] == "list_delayed_orders"],
        )
    finally:
        await provider.client.aclose()

    calls = reply.message.get("tool_calls", [])
    assert calls, "Ollama returned no tool call for the delayed-order query"
    assert calls[0]["function"]["name"] == "list_delayed_orders"
    assert reply.prompt_tokens >= 0 and reply.completion_tokens >= 0

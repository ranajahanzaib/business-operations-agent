import asyncio

from opsagent.providers import ModelReply, ScriptedProvider


def test_scripted_provider_returns_structured_tool_decision():
    expected = ModelReply(
        {
            "role": "assistant",
            "content": "Inspect delayed orders.",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "list_delayed_orders",
                        "arguments": {
                            "overdue_days": 5,
                            "as_of": "2026-11-10T12:00:00+00:00",
                            "limit": 100,
                        },
                    },
                }
            ],
        },
        12,
        8,
    )
    provider = ScriptedProvider([expected])
    actual = asyncio.run(provider.complete([], []))
    assert actual == expected
    assert provider.calls == 1

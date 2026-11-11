"""Test-only server for the Playwright full-stack workflow scenario."""

import os
import tempfile
from pathlib import Path


def main() -> None:
    runtime_dir = Path(tempfile.mkdtemp(prefix="opsagent-playwright-"))
    os.environ["OPSAGENT_DB"] = str(runtime_dir / "business.sqlite3")
    os.environ["OPSAGENT_PROVIDER"] = "scripted"
    os.environ["OPSAGENT_MODEL"] = "playwright-fixture"

    import uvicorn

    from opsagent import api, providers
    from opsagent.db import seed
    from opsagent.providers import ModelReply, ScriptedProvider

    fixture_provider = ScriptedProvider(
        [
            ModelReply(
                {
                    "role": "assistant",
                    "content": "Find delayed orders.",
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
                }
            ),
            ModelReply(
                {
                    "role": "assistant",
                    "content": "Prepare uncovered tickets.",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "propose_delayed_order_tickets",
                                "arguments": {
                                    "overdue_days": 5,
                                    "as_of": "2026-11-10T12:00:00+00:00",
                                },
                            },
                        }
                    ],
                }
            ),
            ModelReply({"role": "assistant", "content": "Prepared the proposal for review."}),
        ]
    )
    providers.provider_from_config = lambda *_args, **_kwargs: fixture_provider
    seed()
    uvicorn.run(api.app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()

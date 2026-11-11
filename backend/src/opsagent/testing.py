"""Test-only deterministic adapter for replaying selected tool responses.

This module is never imported by the live API or provider path. Tests may inject
``ToolResponseReplay`` as ``api.call_tool`` to reproduce malformed, stale, or
otherwise controlled responses without exposing fault injection over HTTP.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReplayStep:
    tool: str
    arguments: dict[str, Any]
    response: Any


class ToolResponseReplay:
    """Replay a strict ordered sequence of tool responses in tests."""

    def __init__(self, steps: list[ReplayStep]) -> None:
        self._steps = list(steps)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, tool: str, arguments: dict[str, Any]) -> Any:
        actual_arguments = deepcopy(arguments)
        self.calls.append((tool, actual_arguments))
        if not self._steps:
            raise AssertionError(f"Unexpected extra tool call: {tool}")
        expected = self._steps.pop(0)
        if tool != expected.tool or actual_arguments != expected.arguments:
            raise AssertionError(
                f"Expected {expected.tool}({expected.arguments!r}); got {tool}({actual_arguments!r})"
            )
        if isinstance(expected.response, BaseException):
            raise expected.response
        return deepcopy(expected.response)

    def assert_exhausted(self) -> None:
        if self._steps:
            raise AssertionError(f"{len(self._steps)} replay step(s) were not consumed")

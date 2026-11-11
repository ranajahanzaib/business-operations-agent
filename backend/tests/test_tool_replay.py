import pytest

from opsagent.testing import ReplayStep, ToolResponseReplay


def test_tool_response_replay_enforces_call_order_and_arguments():
    replay = ToolResponseReplay(
        [ReplayStep("check_inventory", {"sku": "NS-0001"}, {"available_quantity": 8})]
    )
    assert replay("check_inventory", {"sku": "NS-0001"}) == {"available_quantity": 8}
    replay.assert_exhausted()
    with pytest.raises(AssertionError, match="Unexpected extra tool call"):
        replay("check_inventory", {"sku": "NS-0001"})


def test_tool_response_replay_can_inject_a_controlled_failure():
    replay = ToolResponseReplay(
        [ReplayStep("get_order", {"order_id": "o0001"}, RuntimeError("controlled timeout"))]
    )
    with pytest.raises(RuntimeError, match="controlled timeout"):
        replay("get_order", {"order_id": "o0001"})
    replay.assert_exhausted()

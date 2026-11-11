import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import WorkflowGraph from "./WorkflowGraph";

it("shows stored payload details when an execution node is selected", () => {
  const event = {
    id: 42,
    kind: "tool_call",
    created_at: "2026-11-10T12:00:00Z",
    payload: { name: "get_order", arguments: { order_id: "o0001" } },
  };
  render(<WorkflowGraph events={[event]} status="completed" />);
  expect(
    screen.getByRole("region", {
      name: "Workflow graph showing 1 recorded events",
    }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByText("tool call"));
  expect(
    screen.getByRole("region", { name: "Selected workflow event details" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/o0001/)).toBeInTheDocument();
});

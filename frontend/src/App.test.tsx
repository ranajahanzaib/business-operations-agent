import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
const closedStream = () =>
  new Response(
    new ReadableStream({
      start(controller) {
        controller.close();
      },
    }),
  );
function setupWorkspace(fetcher: (url: string) => Response) {
  localStorage.setItem("token", "local-operator-token");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => fetcher(String(input))),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

it("shows the local sign-in screen before accessing workspace data", () => {
  localStorage.clear();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  );
  expect(
    screen.getByRole("heading", { name: "Sign in to OpsAgent" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/local-operator-token/)).toBeInTheDocument();
});

it("opens a business record and follows its linked customer", async () => {
  localStorage.setItem("token", "local-operator-token");
  const payloads: Record<string, unknown> = {
    "/api/dashboard": { counts: {}, pending_approvals: 0 },
    "/api/runs": { items: [] },
    "/api/data/orders?limit=20&offset=0&search=&sort_by=": {
      items: [{ id: "o0001", order_number: "NS-000001", customer_id: "c001" }],
      total: 1,
      offset: 0,
    },
    "/api/orders/o0001": {
      id: "o0001",
      order_number: "NS-000001",
      customer: { id: "c001", full_name: "Customer One" },
      items: [],
      tickets: [],
    },
    "/api/data/customers?limit=20&offset=0&search=&sort_by=": {
      items: [{ id: "c001", full_name: "Customer One" }],
      total: 1,
      offset: 0,
    },
    "/api/customers/c001": {
      id: "c001",
      full_name: "Customer One",
      orders: [],
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(JSON.stringify(payloads[String(input)] ?? {}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("button", { name: /Orders/ }));
  fireEvent.click(await screen.findByRole("button", { name: "o0001" }));
  const customerLink = await screen.findByRole("button", {
    name: "Customer One",
  });
  fireEvent.click(customerLink);
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Customers", level: 1 }),
    ).toBeInTheDocument(),
  );
  expect(
    await screen.findByRole("heading", { name: "Record details" }),
  ).toBeInTheDocument();
});

it("shows a failed workflow and keeps its error visible", async () => {
  setupWorkspace((url) => {
    if (url === "/api/dashboard")
      return json({ counts: {}, pending_approvals: 0 });
    if (url === "/api/runs")
      return json({
        items: [
          {
            id: "run-failed",
            request: "Inspect this run",
            status: "failed",
            created_at: "2026-11-10T12:00:00Z",
            model: "fixture",
          },
        ],
      });
    if (url === "/api/runs/run-failed")
      return json({
        id: "run-failed",
        status: "failed",
        error: "Provider unavailable",
        events: [],
        proposal: null,
      });
    if (url.endsWith("/stream")) return closedStream();
    return json({});
  });
  fireEvent.click(
    await screen.findByRole("button", { name: /Inspect this run/ }),
  );
  expect(await screen.findByText("Provider unavailable")).toBeInTheDocument();
});

it("renders a pending proposal with its approval action", async () => {
  setupWorkspace((url) => {
    if (url === "/api/dashboard")
      return json({ counts: {}, pending_approvals: 1 });
    if (url === "/api/runs")
      return json({
        items: [
          {
            id: "run-pending",
            request: "Prepare an update",
            status: "awaiting_approval",
            created_at: "2026-11-10T12:00:00Z",
            model: "fixture",
          },
        ],
      });
    if (url === "/api/runs/run-pending")
      return json({
        id: "run-pending",
        status: "awaiting_approval",
        events: [],
        proposal: {
          id: "proposal-1",
          status: "pending",
          payload: [
            {
              action_id: "a1",
              action_type: "update_ticket_priority",
              ticket_number: "T-1",
              old_priority: "high",
              new_priority: "urgent",
              reason: "Escalate the delayed complaint.",
            },
          ],
        },
      });
    if (url.endsWith("/stream")) return closedStream();
    return json({});
  });
  fireEvent.click(
    await screen.findByRole("button", { name: /Prepare an update/ }),
  );
  expect(
    await screen.findByRole("button", { name: /Approve all 1 actions/ }),
  ).toBeInTheDocument();
  expect(screen.getByText(/high → urgent/)).toBeInTheDocument();
});

it("expands an independent evaluation result", async () => {
  setupWorkspace((url) => {
    if (url === "/api/dashboard")
      return json({ counts: {}, pending_approvals: 0 });
    if (url === "/api/runs") return json({ items: [] });
    if (url === "/api/evaluations")
      return json({
        items: [
          {
            id: "eval-1",
            scenario_id: "delayed_order_support",
            mode: "live",
            run_id: "run-1",
            status: "passed",
            created_at: "2026-11-10T12:00:00Z",
          },
        ],
      });
    if (url === "/api/evaluations/eval-1")
      return json({
        result: { overall_status: "passed", verified_actions: 2 },
      });
    return json({});
  });
  fireEvent.click(await screen.findByRole("button", { name: "Evaluations" }));
  fireEvent.click(
    await screen.findByRole("button", { name: /delayed order support/ }),
  );
  expect(await screen.findByText(/verified_actions/)).toBeInTheDocument();
});

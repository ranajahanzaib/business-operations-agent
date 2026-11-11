# Current limitations

- Three model-driven proposal workflows are implemented: delayed-order tickets, inventory reservations, and ticket-priority escalation. A scripted provider is used only in deterministic integration tests.
- Ollama `/api/chat` and an OpenAI-compatible provider adapter are implemented. Live model quality has not been benchmarked.
- The client uses persisted, resumable SSE events and an interactive XYFlow graph with event details. One Playwright flagship flow covers delayed orders through approval, verification, ticket drilldown, and persisted history. Broader browser coverage and a formal accessibility audit have not been run.
- The local auth tokens are a lightweight single-user reference mechanism, not production authentication.
- Tailwind is wired into the Vite build and used for utility styling alongside the compact custom design system. The explorer supports search, sort, pagination, record detail, and linked customer/order/ticket navigation.
- Tool calls, planning iterations, proposals, repeated calls, malformed model responses, and run duration are bounded. Tool arguments are validated against the registered schemas and invalid responses receive bounded correction retries. A test-only ordered tool-response replay adapter and sanitized trace export support controlled fault experiments; there is no public fault-injection endpoint or built-in ToolTwin variant runner.
- CI is configured for backend, frontend, and browser end-to-end checks. Hosted CI has not been observed for this checkout, and a formal accessibility audit has not been run.
- This service does not integrate with external commerce, support, payment, or email providers.

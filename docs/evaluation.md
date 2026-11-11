# Evaluation

The delayed-ticket verifier independently re-queries qualifying orders and committed support-ticket rows, then checks coverage, unexpected actions, duplicates, customer/order relationships, and approval provenance. Inventory and priority-change evaluators verify committed state and applicable invariants. A natural-language completion statement is not evidence of success. Verification results are persisted and available through `/api/evaluations` and the UI, with JSON export.

The fixture reference clock defaults to 2026-11-10T12:00:00Z and can be changed with `OPSAGENT_AS_OF`. Strict overdue comparison excludes orders exactly at the configured threshold. Delivered and cancelled orders are excluded from current overdue status. Historical late delivery is separate from current delay.

Scripted-provider integration tests exercise the real graph interrupt/resume path and business state, but are reported as deterministic tests, not measured LLM performance. Live model quality benchmarks are not included. Do not interpret local fixture coverage as a benchmark of model reliability.

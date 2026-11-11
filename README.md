# Business Operations Agent (OpsAgent)

OpsAgent is a local-first AI business operations reference system. It gives a configured model provider typed read tools for a synthetic retail business, pauses proposed changes for human approval, applies approved changes in SQLite, and checks the committed database state independently.

The project demonstrates a bounded workflow with durable checkpoints, explicit permissions, immutable proposal payloads, idempotency records, and inspectable events. It is a reference implementation, not a production-ready multitenant agent service.

## Features

- Deterministic Northstar Commerce demo data and a fixed evaluation clock.
- Ollama native function calling through `/api/chat`; no scripted live-mode fallback.
- LangGraph workflow with SQLite checkpointing and an approval interrupt.
- Human approval bound to a canonical proposal hash, operator role, and current business state.
- Atomic ticket writes, execution ledger, duplicate prevention, and persisted event history.
- Independent verification against committed support-ticket rows.
- React/TypeScript dashboard with workflow history, approval review, and business data views.
- Local operator and read-only auditor roles.

## Requirements

Python 3.12+, `uv`, Node.js 20+, pnpm, and [Ollama](https://ollama.com/) with a tool-calling capable model. No paid API or Docker is required. Dependencies and model weights must be downloaded once; the application then runs locally.

## Quick start

From the repository root:

```bash
ollama pull qwen3:4b-instruct
cd backend
uv sync --group dev
uv run opsagent init
uv run opsagent seed
uv run opsagent serve
```

In a second terminal:

```bash
cd frontend
pnpm install
pnpm run dev
```

Open http://127.0.0.1:5173. The local demo operator credential is `local-operator-token`; the read-only auditor credential is `local-auditor-token`. These credentials are public demo values. The API binds to localhost by default and is not hardened for network exposure; changing the tokens alone does not make it suitable for a network or production deployment.

Submit: “Find orders delayed more than five days, identify affected customers, and prepare a support ticket for each.” The server asks the model to select registered read tools, evaluates their actual database results, skips orders with an existing active duplicate ticket, and displays proposed changes. No support-ticket row is created until an operator approves the batch.

## Configuration

Copy `.env.example` to `.env` and export desired values in the shell (or use your preferred dotenv loader). Configuration includes provider/model parameters (`OPSAGENT_TEMPERATURE`, `OPSAGENT_NUM_CTX`, `OPSAGENT_MAX_TOKENS`, `OPSAGENT_MODEL_TIMEOUT_SECONDS`) and bounded execution controls (`OPSAGENT_EXECUTION_TIMEOUT_SECONDS`, `OPSAGENT_MAX_ITERATIONS`, `OPSAGENT_MAX_TOOL_CALLS`, `OPSAGENT_MAX_PROPOSED_ACTIONS`, `OPSAGENT_MAX_IDENTICAL_TOOL_CALLS`, `OPSAGENT_MAX_RESPONSE_RETRIES`). The public Settings screen shows effective values, and invalid/out-of-range values are rejected with a configuration error. The default business database is `backend/data/business-operations-agent.sqlite3`; checkpoint state is held separately in `business-operations-agent-checkpoints.sqlite3`. The fixed reference clock avoids silently drifting fixture results.

The service does not load `.env` automatically. To use the example file from the repository root, run:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Then start the backend and frontend in shells that inherit these exported values. Do not commit `.env`; it is ignored by Git.

## Commands

```bash
cd backend
uv run opsagent doctor
uv run opsagent trace RUN_ID
uv run pytest
uv run ruff check src tests
```

To run the full-stack browser workflow test, install Chromium with `pnpm exec playwright install chromium` from `frontend`, then run `pnpm run test:e2e`.

The HTTP API is documented by FastAPI at http://127.0.0.1:8000/docs. Root `make dev` starts the API and Vite development servers; `make test` runs backend and frontend tests.

## Architecture

- **LangGraph** holds workflow state, explicit transitions, an approval interrupt, and resumable SQLite checkpoints. Application run/event records remain independently queryable.
- **SQLite** keeps the demo reproducible, local, and transactionally understandable. Business state and graph checkpoints use separate files.
- **Human approval** separates untrusted model proposals from authorized state changes. Role is derived from a server-validated local credential, not browser role headers.
- **Execution ledger** records action IDs and unique idempotency keys in the same SQLite transaction as business writes; a checkpoint alone cannot prevent duplicate side effects.
- **Independent evaluation** checks actual ticket rows and their order/category coverage, not model prose.
- **Tool registry** exposes bounded JSON tool schemas and read classifications. The model cannot execute SQL or arbitrary code.

See [docs/architecture.md](docs/architecture.md), [docs/approval-model.md](docs/approval-model.md), [docs/tool-contracts.md](docs/tool-contracts.md), [docs/evaluation.md](docs/evaluation.md), and [docs/limitations.md](docs/limitations.md).

## Providers and scenarios

Ollama and an optional OpenAI-compatible local provider are implemented; provider and model identifiers and token usage are persisted per run. The model can use bounded read tools and prepare approval-backed ticket creation, inventory reservation, and ticket-priority escalation. These workflows share the same proposal, approval, idempotency, and verification controls. A scripted provider is used only in deterministic tests. The live provider path requires a running compatible endpoint and tool-calling model.

## ToolFault / ToolTwin

`GET /api/tools` exports registered descriptions and JSON schemas with read/proposal classifications. `GET /api/runs/{id}/trace` (also `opsagent trace RUN_ID`) exports the used definitions and sanitized, ordered tool inputs/outputs for ToolFault-style analysis. A strict ordered response-replay adapter exists only in the test package; no public fault injection is available. ToolTwin can consume the exported schemas, but alternative tool-name scenario execution is not built into Business Operations Agent.

## Security and limitations

All names, emails, orders, and tickets are synthetic. This demo has no enterprise authentication, no tenant isolation, no real commerce or email integrations, and no remote deployment hardening. Keep it on localhost; replacing the demo bearer tokens does not make it safe to expose. See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). MIT licensed.

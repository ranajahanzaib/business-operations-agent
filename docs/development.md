# Development

Use Python 3.12+, `uv`, Node.js 20+, npm, and local Ollama. From `backend`, run `uv sync --locked --group dev`, then `uv run opsagent init` and `uv run opsagent seed`. Start the API with `uv run opsagent serve`. In another terminal, run `npm ci && npm run dev` from `frontend`; root `make dev` starts both services in parallel. The installable Python distribution is `business-operations-agent`; its import package and CLI remain `opsagent`.

Backend tests live in `backend/tests`. Run `uv run pytest` and `uv run ruff check src tests` from `backend`. Frontend uses Vitest, Testing Library, TypeScript, Tailwind CSS, and XYFlow; run `npm test` and `npm run build` from `frontend`.

The full-stack browser test uses a test-only scripted provider with the real API, SQLite state, approval route, evaluation, and UI. Install Chromium with `npx playwright install chromium`, then run `npm run test:e2e` from `frontend`. The scripted provider is never selected by the live service configuration.

Set `OPSAGENT_DB` to change the business SQLite file. LangGraph checkpoint data is stored alongside it in a separate `business-operations-agent-checkpoints.sqlite3` database. The service does not load `.env` automatically; export its values in the shell before starting the backend. The demo reset endpoint is `POST /api/demo/reset?confirmed=true` and requires an operator token.

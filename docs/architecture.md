# Architecture

Business Operations Agent (OpsAgent) is a local single-process FastAPI service, React client, Ollama provider, business SQLite database, and separate LangGraph SQLite checkpoint database. The application data is synthetic.

LangGraph makes lifecycle transitions explicit and stores resumable state. SQLite provides reproducible local data and atomic business writes. A tool registry limits model capabilities to validated read functions. The model proposes a workflow and reads business facts; application policy controls write authorization, duplicate checks, and state mutation.

The proposal table holds a revision, canonical payload, and SHA-256 digest. The approval endpoint accepts only a proposal ID, authenticates the operator, validates the digest, rechecks current rows, applies the batch and ledger atomically, and verifies resulting state for the selected scenario. Supported proposal types cover delayed-order tickets, inventory reservations, and ticket-priority escalation. Checkpoints and business records have independent stores because workflow state cannot prove a committed business mutation.

## Tradeoffs

The demo uses local bearer credentials rather than a production identity provider, and its API is designed for one local operator. LangGraph SQLite is for local development and lightweight use, not a horizontally scaled deployment. The three demo workflows operate on synthetic records and do not integrate external commerce or support systems.

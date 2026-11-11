.PHONY: dev backend frontend test e2e
dev:
	$(MAKE) -j2 backend frontend
backend:
	cd backend && uv run opsagent serve
frontend:
	cd frontend && pnpm run dev
test:
	cd backend && uv run pytest
	cd frontend && pnpm test
e2e:
	cd frontend && pnpm run test:e2e

SHELL := /bin/bash
.PHONY: setup dev test build seed eval smoke lint typecheck clean

setup: ## Install backend + frontend dependencies and create .env
	bash scripts/setup.sh

dev: ## Run API (:8000) and web (:5173) together
	bash scripts/dev.sh

test: ## Run backend tests
	bash scripts/test.sh

build: ## Build the SPA into frontend/dist
	bash scripts/build.sh

seed: ## Load the demo dataset (implemented in P04)
	bash scripts/seed.sh

eval: ## Run evaluation and generate docs/EVAL_REPORT.md
	bash scripts/eval.sh

smoke: ## Run smoke tests against running API
	bash scripts/smoke.sh

lint: ## Lint backend (ruff, black) and frontend (eslint)
	npm run lint

typecheck: ## TypeScript type check
	npm run typecheck

clean: ## Remove build output and caches (keeps the venv and node_modules)
	rm -rf frontend/dist backend/.pytest_cache backend/.ruff_cache backend/data/*.db backend/data/*.db-wal backend/data/*.db-shm

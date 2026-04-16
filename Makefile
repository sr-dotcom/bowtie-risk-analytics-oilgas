.PHONY: help api frontend test test-py test-js docker clean

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

api:  ## Start FastAPI dev server on port 8000
	uvicorn src.api.main:app --port 8000 --reload

frontend:  ## Start Next.js dev server
	cd frontend && npm run dev

test: test-py test-js  ## Run all tests (Python + frontend)

test-py:  ## Run Python tests
	python3 -m pytest tests/ -q

test-js:  ## Run frontend tests
	cd frontend && npx vitest run

docker:  ## Build and start the Docker stack
	docker compose up --build

clean:  ## Clear build/test caches
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

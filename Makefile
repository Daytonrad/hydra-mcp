.PHONY: install dev proxy admin build test lint fmt

install:          ## install Python and Node dependencies
	cd proxy && uv sync
	cd admin && npm install

build:            ## build the admin page (served by the proxy at /admin/)
	cd admin && npm run build

proxy:            ## run the proxy (serves admin/dist if built)
	cd proxy && uv run hydra-mcp serve

dev:              ## proxy with auto-reload + admin page with hot reload on :5173
	(cd proxy && uv run hydra-mcp serve --reload) & (cd admin && npm run dev); wait

test:             ## Python tests + TypeScript type check
	cd proxy && uv run pytest -q
	cd admin && npm run typecheck

lint:
	cd proxy && uv run ruff check . && uv run ruff format --check .

fmt:
	cd proxy && uv run ruff format . && uv run ruff check --fix .

# Load environment variables from .env file
include .env
export $(shell sed 's/=.*//' .env)

COMPOSE_COMMAND= docker compose --env-file .env -f docker/compose.yml
PYTHON_COMMAND= docker run --rm --network host --env-file .env -e PYTHONPATH=/app/src -e DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}" -e OLLAMA_API_BASE="http://localhost:11434" docker-web:latest .venv/bin/python

up:
	$(COMPOSE_COMMAND) up -d
down:
	$(COMPOSE_COMMAND) down
logs:
	$(COMPOSE_COMMAND) logs -f
ps:
	$(COMPOSE_COMMAND) ps
build:
	$(COMPOSE_COMMAND) build --no-cache
bash:
	$(COMPOSE_COMMAND) exec web bash
migrate:
	$(PYTHON_COMMAND) -m meridiano.migrate migrate
run:
	$(PYTHON_COMMAND) -m meridiano.run_briefing $(ARGS)
check-ollama:
	$(PYTHON_COMMAND) -m meridiano.ollama check_ollama

lint:
	uv run ruff check . 

format:
	uv run ruff check . --fix

test: format
	uv run pytest --cov=src/ tests/

bare-run:
	uv run python -m meridiano.run_briefing ${ARGS}

.PHONY: up down logs ps build bash migrate run app
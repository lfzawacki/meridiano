# Load environment variables from .env file
include .env
export $(shell sed 's/=.*//' .env)

COMPOSE_COMMAND= docker compose -f docker/compose.yml
PYTHON_COMMAND= docker compose -f docker/compose.yml run --rm web .venv/bin/python

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
	$(PYTHON_COMMAND) migrate.py migrate
run:
	# Get user arguments after 'run' target
	$(eval ARGS=$(filter-out $@,$(MAKECMDGOALS)))
	$(PYTHON_COMMAND) /app/src/meridiano/run_briefing.py $(ARGS)

.PHONY: up down logs ps build bash migrate run app
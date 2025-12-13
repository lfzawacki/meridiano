FROM python:3.12-slim-bookworm

# Add uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN mkdir /app
WORKDIR /app
COPY . .
RUN uv sync
EXPOSE 5000

CMD [".venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "meridiano.app:app"]

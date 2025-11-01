FROM python:3.12-slim-bookworm

# Add uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN mkdir /app
COPY ./requirements.txt /app/requirements.txt

WORKDIR /app
COPY . .
RUN uv venv .venv; source .venv/bin/activate; uv pip install -r requirements.txt
EXPOSE 5000

CMD [".venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

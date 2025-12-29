# Contributing

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bug fix (git checkout -b feature/your-feature-name).
3. Make your changes, adhering to the existing code style where possible. (Use `make lint` to check style)
4. Run tests to ensure nothing is broken. (Use `make test`)
5. (Optional but Recommended) Add tests for your changes if applicable.
6. Ensure your changes don't break existing functionality.
7. Commit your changes (git commit -am 'Add some feature').
8. Push to your branch (git push origin feature/your-feature-name).
9. Create a Pull Request on GitHub, describing your changes clearly.

## Test Suite

Simple pytest-based test suite for Meridiano.

## Setup

Install test dependencies:

```bash
uv sync --group dev
```

## Running Tests

Run all tests:

```bash
make test
```

Run with verbose output:

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=. --cov-report=html
```

Run specific test file:

```bash
pytest tests/test_database.py
```

Run specific test:

```bash
pytest tests/test_database.py::TestAddArticle::test_add_article_success
```

## Test Structure

- Tests are located in the `tests/` directory
- Use pytest framework
- `tests/integration/` - Integration tests
- `tests/test_database.py` - Tests for database operations (add, get, list articles)
- `tests/test_models.py` - Tests for SQLModel models (Article, Brief)
- `tests/test_utils.py` - Tests for utility functions (datetime formatting)
- `tests/test_app.py` - Tests for Flask routes (basic smoke tests)
- `tests/conftest.py` - Shared pytest fixtures and configuration

## Notes

- Tests use an in-memory SQLite database for isolation
- Each test runs with a fresh database state
- No external API calls are made (integration tests would require mocking)

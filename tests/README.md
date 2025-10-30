# Test Suite

Simple pytest-based test suite for Meridiano.

## Setup

Install test dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

Run all tests:
```bash
pytest
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

- `test_database.py` - Tests for database operations (add, get, list articles)
- `test_models.py` - Tests for SQLModel models (Article, Brief)
- `test_utils.py` - Tests for utility functions (datetime formatting)
- `test_app.py` - Tests for Flask routes (basic smoke tests)
- `conftest.py` - Shared pytest fixtures and configuration

## Notes

- Tests use an in-memory SQLite database for isolation
- Each test runs with a fresh database state
- No external API calls are made (integration tests would require mocking)


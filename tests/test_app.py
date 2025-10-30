"""
Tests for Flask application routes.
"""
import os
import pytest
from flask import Flask
from datetime import datetime
from models import Article, Brief

# Import app after setting up test database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.test_client() as client:
        with app.app_context():
            from models import init_db
            init_db()
        yield client


class TestIndexRoute:
    """Tests for the index (briefings list) route."""

    def test_index_route_success(self, client):
        """Test accessing the index route."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Generated Briefings" in response.data or b"Briefings" in response.data

    def test_index_route_with_profile_filter(self, client):
        """Test index route with feed profile filter."""
        response = client.get("/?feed_profile=tech")
        assert response.status_code == 200


class TestArticlesRoute:
    """Tests for the articles listing route."""

    def test_articles_route_success(self, client):
        """Test accessing the articles route."""
        response = client.get("/articles")
        assert response.status_code == 200
        assert b"Articles" in response.data

    def test_articles_route_with_pagination(self, client):
        """Test articles route with pagination."""
        response = client.get("/articles?page=1")
        assert response.status_code == 200

    def test_articles_route_with_search(self, client):
        """Test articles route with search term."""
        response = client.get("/articles?search=test")
        assert response.status_code == 200

    def test_articles_route_with_date_filter(self, client):
        """Test articles route with date filters."""
        response = client.get("/articles?start_date=2024-01-01&end_date=2024-01-31")
        assert response.status_code == 200


class TestAddArticleRoute:
    """Tests for the add article route."""

    def test_add_article_get(self, client):
        """Test GET request to add article page."""
        response = client.get("/add_article")
        assert response.status_code == 200
        assert b"Add New Article" in response.data or b"Add Article" in response.data

    def test_add_article_post_invalid_url(self, client):
        """Test POST with invalid URL."""
        response = client.post(
            "/add_article",
            data={"article_url": "not-a-url", "feed_profile_assign": "test"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should show error message (check for flash message)
        assert b"Invalid URL" in response.data or b"error" in response.data.lower()

    def test_add_article_post_empty_url(self, client):
        """Test POST with empty URL."""
        response = client.post(
            "/add_article",
            data={"article_url": "", "feed_profile_assign": "test"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should show error message
        assert b"required" in response.data.lower() or b"error" in response.data.lower()


class TestViewArticleRoute:
    """Tests for viewing individual articles."""

    def test_view_article_not_found(self, client):
        """Test viewing non-existent article."""
        response = client.get("/article/99999")
        assert response.status_code == 404


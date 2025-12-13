"""
Tests for database models.
"""

import os
import sys
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from sqlmodel import SQLModel

from meridiano.models import Article, Brief, get_session, init_db

# Set test database URL
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize test database before each test and clean up after."""
    init_db()
    yield
    # Clean up: drop all tables to ensure fresh state for next test
    with get_session() as session:
        SQLModel.metadata.drop_all(session.bind)


class TestArticleModel:
    """Tests for Article model."""

    def test_create_article_minimal(self):
        """Test creating article with minimal required fields."""
        with get_session() as session:
            article = Article(
                url="https://example.com/test",
                feed_profile="test",
            )
            session.add(article)
            session.commit()
            session.refresh(article)

            assert article.id is not None
            assert article.url == "https://example.com/test"
            assert article.feed_profile == "test"
            assert article.fetched_at is not None

    def test_create_article_full(self, sample_article_data):
        """Test creating article with all fields."""
        with get_session() as session:
            article = Article(**sample_article_data, fetched_at=datetime.now())
            session.add(article)
            session.commit()
            session.refresh(article)

            assert article.id is not None
            assert article.url == sample_article_data["url"]
            assert article.title == sample_article_data["title"]
            assert article.feed_profile == sample_article_data["feed_profile"]
            assert article.image_url == sample_article_data["image_url"]

    def test_article_unique_url(self):
        """Test that article URLs must be unique."""
        with get_session() as session:
            article1 = Article(
                url="https://example.com/duplicate",
                feed_profile="test",
            )
            session.add(article1)
            session.commit()

            article2 = Article(
                url="https://example.com/duplicate",  # Same URL
                feed_profile="test",
            )
            session.add(article2)

            with pytest.raises(IntegrityError):  # Should raise IntegrityError
                session.commit()


class TestBriefModel:
    """Tests for Brief model."""

    def test_create_brief_minimal(self):
        """Test creating brief with minimal required fields."""
        with get_session() as session:
            brief = Brief(
                brief_markdown="# Test Brief",
                feed_profile="test",
            )
            session.add(brief)
            session.commit()
            session.refresh(brief)

            assert brief.id is not None
            assert brief.brief_markdown == "# Test Brief"
            assert brief.feed_profile == "test"
            assert brief.generated_at is not None

    def test_create_brief_full(self, sample_brief_data):
        """Test creating brief with all fields."""
        with get_session() as session:
            brief = Brief(**sample_brief_data)
            session.add(brief)
            session.commit()
            session.refresh(brief)

            assert brief.id is not None
            assert brief.brief_markdown == sample_brief_data["brief_markdown"]
            assert brief.feed_profile == sample_brief_data["feed_profile"]
            assert brief.contributing_article_ids == sample_brief_data["contributing_article_ids"]

"""
Tests for database operations.
"""

import json
import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from sqlmodel import SQLModel

from meridiano.models import get_session, init_db

# Set test database before importing database module
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from meridiano.database import (
    add_article,
    get_all_articles,
    get_article_by_id,
    get_brief_by_id,
    get_distinct_feed_profiles,
    save_brief,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize test database before each test and clean up after."""
    init_db()
    yield
    # Clean up: drop all tables to ensure fresh state for next test
    with get_session() as session:
        SQLModel.metadata.drop_all(session.bind)


class TestAddArticle:
    """Tests for adding articles."""

    def test_add_article_success(self, sample_article_data):
        """Test successfully adding an article."""
        article_id = add_article(**sample_article_data)

        assert article_id is not None
        assert article_id > 0

        # Verify article was added
        retrieved = get_article_by_id(article_id)
        assert retrieved is not None
        assert retrieved["url"] == sample_article_data["url"]
        assert retrieved["title"] == sample_article_data["title"]
        assert retrieved["feed_profile"] == sample_article_data["feed_profile"]

    def test_add_duplicate_article(self, sample_article_data):
        """Test that duplicate URLs are rejected."""
        # Add first article
        article_id1 = add_article(**sample_article_data)
        assert article_id1 is not None

        # Try to add duplicate
        article_id2 = add_article(**sample_article_data)
        assert article_id2 is None  # Should return None for duplicates


class TestGetArticle:
    """Tests for retrieving articles."""

    def test_get_article_by_id(self, sample_article_data):
        """Test retrieving an article by ID."""
        # Add article first
        article_id = add_article(**sample_article_data)
        assert article_id is not None

        # Retrieve article
        retrieved = get_article_by_id(article_id)

        assert retrieved is not None
        assert retrieved["id"] == article_id
        assert retrieved["url"] == sample_article_data["url"]
        assert retrieved["title"] == sample_article_data["title"]

    def test_get_article_not_found(self):
        """Test retrieving non-existent article."""
        result = get_article_by_id(99999)
        assert result is None


class TestGetAllArticles:
    """Tests for listing articles."""

    def test_get_all_articles_empty(self):
        """Test getting articles when none exist."""
        articles = get_all_articles()
        assert articles == []

    def test_get_all_articles_with_data(self, sample_article_data):
        """Test getting articles with data."""
        # Create multiple articles
        for i in range(3):
            article_data = sample_article_data.copy()
            article_data["url"] = f"https://example.com/article{i}"
            article_data["title"] = f"Article {i}"
            add_article(**article_data)

        articles = get_all_articles()
        assert len(articles) == 3


class TestFeedProfiles:
    """Tests for feed profile operations."""

    def test_get_distinct_feed_profiles(self, sample_article_data):
        """Test getting distinct feed profiles."""
        # Create articles with different profiles
        profiles = ["tech", "brasil", "tech", "default"]
        for idx, profile in enumerate(profiles):
            article_data = sample_article_data.copy()
            article_data["url"] = f"https://example.com/{profile}_{idx}"
            article_data["feed_profile"] = profile
            add_article(**article_data)

        distinct_profiles = get_distinct_feed_profiles(table="articles")
        assert len(distinct_profiles) == 3  # tech, brasil, default
        assert "tech" in distinct_profiles
        assert "brasil" in distinct_profiles
        assert "default" in distinct_profiles


class TestSaveBrief:
    """Tests for saving briefs."""

    def test_save_brief_success(self):
        """Test successfully saving a brief."""
        brief_markdown = "# Test Brief\n\nThis is a test briefing."
        contributing_article_ids = [1, 2, 3]
        feed_profile = "test"

        brief_id = save_brief(brief_markdown, contributing_article_ids, feed_profile)

        assert brief_id is not None
        assert brief_id > 0

        # Verify brief was saved
        retrieved = get_brief_by_id(brief_id)
        assert retrieved is not None
        assert retrieved["id"] == brief_id
        assert retrieved["brief_markdown"] == brief_markdown
        assert retrieved["feed_profile"] == feed_profile
        assert retrieved["contributing_article_ids"] == json.dumps(contributing_article_ids)

    def test_save_brief_sequential_ids(self):
        """Test that brief IDs are sequential."""
        brief_markdown = "# Test Brief\n\nThis is a test briefing."
        contributing_article_ids = [1, 2, 3]
        feed_profile = "test"

        # Save multiple briefs
        brief_ids = []
        for i in range(3):
            brief_id = save_brief(
                f"{brief_markdown} {i}",
                contributing_article_ids,
                feed_profile,
            )
            brief_ids.append(brief_id)

        # Verify IDs are sequential
        assert len(brief_ids) == 3
        assert brief_ids[0] < brief_ids[1] < brief_ids[2]
        # Verify they are consecutive (or at least sequential)
        assert brief_ids[1] == brief_ids[0] + 1
        assert brief_ids[2] == brief_ids[1] + 1

    def test_save_brief_different_profiles(self):
        """Test saving briefs with different feed profiles."""
        brief_markdown = "# Test Brief\n\nThis is a test briefing."
        contributing_article_ids = [1, 2, 3]

        profiles = ["tech", "brasil", "default"]
        brief_ids = []

        for profile in profiles:
            brief_id = save_brief(brief_markdown, contributing_article_ids, profile)
            brief_ids.append(brief_id)

            # Verify each brief has correct profile
            retrieved = get_brief_by_id(brief_id)
            assert retrieved is not None
            assert retrieved["feed_profile"] == profile

        # Verify all briefs were saved
        assert len(brief_ids) == 3
        assert all(bid > 0 for bid in brief_ids)

    def test_save_brief_empty_contributing_ids(self):
        """Test saving a brief with empty contributing article IDs."""
        brief_markdown = "# Test Brief\n\nThis is a test briefing."
        contributing_article_ids = []
        feed_profile = "test"

        brief_id = save_brief(brief_markdown, contributing_article_ids, feed_profile)

        assert brief_id is not None
        assert brief_id > 0

        # Verify brief was saved with empty IDs
        retrieved = get_brief_by_id(brief_id)
        assert retrieved is not None
        assert retrieved["contributing_article_ids"] == json.dumps([])

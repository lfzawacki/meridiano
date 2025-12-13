"""
Pytest configuration and shared fixtures.
"""

import os
import sys
from datetime import datetime

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# Set test database URL before importing models
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def sample_article_data():
    """Sample article data for testing."""
    return {
        "url": "https://example.com/article1",
        "title": "Test Article",
        "published_date": datetime(2024, 1, 15, 10, 30),
        "feed_source": "Test Feed",
        "raw_content": "This is test content for an article.",
        "feed_profile": "test",
        "image_url": "https://example.com/image.jpg",
    }


@pytest.fixture
def sample_brief_data():
    """Sample brief data for testing."""
    return {
        "brief_markdown": "# Test Brief\n\nThis is a test briefing.",
        "contributing_article_ids": "[1, 2, 3]",
        "feed_profile": "test",
    }

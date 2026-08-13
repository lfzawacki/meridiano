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
    add_article_to_collection,
    create_collection,
    delete_collection,
    get_all_articles,
    get_article_by_id,
    get_article_count_for_collection,
    get_articles_by_ids,
    get_articles_for_collection,
    get_brief_article_links,
    get_brief_by_id,
    get_collection_by_id,
    get_collections,
    get_distinct_feed_profiles,
    remove_article_from_collection,
    save_brief,
    toggle_collection_archive_status,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize test database before each test and clean up after."""
    # This setup ensures that each test function runs with a fresh database.
    # It drops all tables, then re-creates them before the test runs.
    with get_session() as session:
        SQLModel.metadata.drop_all(session.bind)
    init_db()
    return


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


class TestGetArticlesByIds:
    """Tests for the bulk article lookup used by the brief source list."""

    def _add(self, sample_article_data, suffix, title):
        data = {**sample_article_data, "url": f"https://example.com/a{suffix}", "title": title}
        return add_article(
            data["url"],
            data["title"],
            data["published_date"],
            data["feed_source"],
            data["raw_content"],
            data["feed_profile"],
            data["image_url"],
        )

    def test_returns_articles_in_requested_order(self, sample_article_data):
        """Test that results follow the id order given, not insertion order."""
        first = self._add(sample_article_data, 1, "First")
        second = self._add(sample_article_data, 2, "Second")

        results = get_articles_by_ids([second, first])

        assert [a["title"] for a in results] == ["Second", "First"]

    def test_skips_missing_ids(self, sample_article_data):
        """Test that ids with no row are dropped instead of raising."""
        existing = self._add(sample_article_data, 1, "First")

        results = get_articles_by_ids([existing, 999999])

        assert [a["id"] for a in results] == [existing]

    def test_deduplicates_ids(self, sample_article_data):
        """Test that a repeated id yields a single row."""
        existing = self._add(sample_article_data, 1, "First")

        results = get_articles_by_ids([existing, existing])

        assert len(results) == 1

    def test_empty_input(self):
        """Test that no ids means no query and no rows."""
        assert get_articles_by_ids([]) == []


class TestBriefArticleLinks:
    """Tests for the source links recorded alongside a brief."""

    @pytest.fixture
    def scored_sources(self):
        """Creates source articles with known impact scores, keyed by score."""
        from datetime import datetime

        from meridiano.models import Article

        ids = {}
        with get_session() as session:
            for score in (3, 7, 9, None):
                article = Article(
                    url=f"https://example.com/src-{score}",
                    title=f"Score {score}",
                    published_date=datetime(2024, 1, 1),
                    feed_source="Test Feed",
                    raw_content="content",
                    feed_profile="test",
                    impact_score=score,
                )
                session.add(article)
                session.commit()
                session.refresh(article)
                ids[score] = article.id
        return ids

    def test_save_brief_persists_article_links(self, scored_sources):
        """Test that article links are written and read back in cluster order."""
        first, second = scored_sources[9], scored_sources[7]
        links = [
            {"article_id": second, "cluster_index": 1, "cluster_topic": "Second Topic"},
            {"article_id": first, "cluster_index": 0, "cluster_topic": "First Topic"},
        ]

        brief_id = save_brief("# Brief", [first, second], "test", article_links=links)

        stored = get_brief_article_links(brief_id)
        assert [link["article_id"] for link in stored] == [first, second]
        assert [link["cluster_topic"] for link in stored] == ["First Topic", "Second Topic"]

    def test_links_are_ranked_by_impact_within_a_cluster(self, scored_sources):
        """Test that the strongest story in a cluster is listed first."""
        links = [
            {"article_id": scored_sources[3], "cluster_index": 0, "cluster_topic": "Topic"},
            {"article_id": scored_sources[9], "cluster_index": 0, "cluster_topic": "Topic"},
            {"article_id": scored_sources[7], "cluster_index": 0, "cluster_topic": "Topic"},
        ]

        brief_id = save_brief("# Brief", [], "test", article_links=links)

        stored = get_brief_article_links(brief_id)
        assert [link["article_id"] for link in stored] == [
            scored_sources[9],
            scored_sources[7],
            scored_sources[3],
        ]

    def test_unscored_articles_sort_last(self, scored_sources):
        """Test that a NULL impact score does not outrank a real one."""
        links = [
            {"article_id": scored_sources[None], "cluster_index": 0},
            {"article_id": scored_sources[3], "cluster_index": 0},
        ]

        brief_id = save_brief("# Brief", [], "test", article_links=links)

        stored = get_brief_article_links(brief_id)
        assert [link["article_id"] for link in stored] == [scored_sources[3], scored_sources[None]]

    def test_cluster_order_beats_impact_score(self, scored_sources):
        """Test that ranking happens inside a cluster, never across clusters."""
        links = [
            {"article_id": scored_sources[3], "cluster_index": 0, "cluster_topic": "First"},
            {"article_id": scored_sources[9], "cluster_index": 1, "cluster_topic": "Second"},
        ]

        brief_id = save_brief("# Brief", [], "test", article_links=links)

        stored = get_brief_article_links(brief_id)
        assert [link["article_id"] for link in stored] == [scored_sources[3], scored_sources[9]]

    def test_save_brief_without_links(self):
        """Test that omitting links leaves the brief with no source rows."""
        brief_id = save_brief("# Brief", [1, 2], "test")

        assert get_brief_article_links(brief_id) == []

    def test_links_are_scoped_to_their_brief(self, scored_sources):
        """Test that one brief's links never leak into another's source list."""
        first_article, second_article = scored_sources[9], scored_sources[7]
        first = save_brief("# One", [], "test", article_links=[{"article_id": first_article, "cluster_index": 0}])
        second = save_brief("# Two", [], "test", article_links=[{"article_id": second_article, "cluster_index": 0}])

        assert [link["article_id"] for link in get_brief_article_links(first)] == [first_article]
        assert [link["article_id"] for link in get_brief_article_links(second)] == [second_article]

    def test_missing_topic_is_stored_as_none(self, scored_sources):
        """Test that a model that ignored the TOPIC line yields an untitled group."""
        article_id = scored_sources[9]
        brief_id = save_brief("# Brief", [], "test", article_links=[{"article_id": article_id, "cluster_index": 0}])

        assert get_brief_article_links(brief_id)[0]["cluster_topic"] is None

    def test_link_to_a_deleted_article_is_dropped(self, scored_sources):
        """Test that a source which no longer exists is not reported."""
        links = [
            {"article_id": scored_sources[9], "cluster_index": 0},
            {"article_id": 999999, "cluster_index": 0},
        ]

        brief_id = save_brief("# Brief", [], "test", article_links=links)

        assert [link["article_id"] for link in get_brief_article_links(brief_id)] == [scored_sources[9]]


class TestCollections:
    """Tests for collection database operations."""

    def test_create_collection(self):
        """Test creating a new collection."""
        coll_id = create_collection("Test Collection")
        assert coll_id is not None
        assert coll_id > 0

        retrieved = get_collection_by_id(coll_id)
        assert retrieved["name"] == "Test Collection"
        assert retrieved["archived"] is False

    def test_get_collections(self):
        """Test retrieving active collections."""
        # Initially empty
        assert get_collections() == []

        # After adding collections
        create_collection("Collection B")
        create_collection("Collection A")
        collections = get_collections()
        assert len(collections) == 2
        # Test sorting by name
        assert collections[0]["name"] == "Collection A"
        assert collections[1]["name"] == "Collection B"

    def test_toggle_archive_collection(self):
        """Test archiving and un-archiving a collection."""
        coll_id = create_collection("To Archive")

        # Initial state: Not archived
        coll = get_collection_by_id(coll_id)
        assert coll["archived"] is False

        # Toggle: Should become archived
        new_status = toggle_collection_archive_status(coll_id)
        assert new_status is True
        coll = get_collection_by_id(coll_id)
        assert coll["archived"] is True

        # Toggle again: Should become un-archived
        new_status = toggle_collection_archive_status(coll_id)
        assert new_status is False
        coll = get_collection_by_id(coll_id)
        assert coll["archived"] is False

    def test_get_collections_filtered_by_archive(self):
        """Test retrieving collections filtered by archived status."""
        id1 = create_collection("Active 1")
        id2 = create_collection("Active 2")
        id3 = create_collection("Archived 1")

        # Archive the third one
        toggle_collection_archive_status(id3)

        # Fetch active (default)
        active_cols = get_collections(archived=False)
        assert len(active_cols) == 2
        active_ids = {c["id"] for c in active_cols}
        assert id1 in active_ids
        assert id2 in active_ids
        assert id3 not in active_ids

        # Fetch archived
        archived_cols = get_collections(archived=True)
        assert len(archived_cols) == 1
        assert archived_cols[0]["id"] == id3

    def test_add_and_remove_article_from_collection(self, sample_article_data):
        """Test adding and removing an article from a collection."""
        article_id = add_article(**sample_article_data)
        coll_id = create_collection("My Collection")

        # Initially, collection is empty
        assert get_articles_for_collection(coll_id) == []
        assert get_article_count_for_collection(coll_id) == 0

        # Add article
        add_article_to_collection(coll_id, article_id)
        articles_in_coll = get_articles_for_collection(coll_id)
        assert len(articles_in_coll) == 1
        assert articles_in_coll[0]["id"] == article_id
        assert get_article_count_for_collection(coll_id) == 1

        # Add again (should be idempotent)
        add_article_to_collection(coll_id, article_id)
        assert get_article_count_for_collection(coll_id) == 1

        # Remove article
        remove_article_from_collection(coll_id, article_id)
        assert get_articles_for_collection(coll_id) == []
        assert get_article_count_for_collection(coll_id) == 0

    def test_get_multiple_articles_for_collection(self, sample_article_data):
        """Test retrieving multiple articles from a collection."""
        coll_id = create_collection("Tech News")
        article_ids = []
        for i in range(3):
            data = sample_article_data.copy()
            data["url"] = f"http://example.com/{i}"
            article_id = add_article(**data)
            article_ids.append(article_id)
            add_article_to_collection(coll_id, article_id)

        articles = get_articles_for_collection(coll_id)
        assert len(articles) == 3
        retrieved_ids = {a["id"] for a in articles}
        assert retrieved_ids == set(article_ids)

    def test_delete_collection(self, sample_article_data):
        """Test deleting a collection and its associations, but not the articles."""
        # 1. Setup: Create an article and a collection
        article_id = add_article(**sample_article_data)
        coll_id = create_collection("To Delete")

        # 2. Associate them
        add_article_to_collection(coll_id, article_id)
        assert get_article_count_for_collection(coll_id) == 1

        # 3. Delete the collection
        delete_collection(coll_id)

        # 4. Verify collection is gone
        assert get_collection_by_id(coll_id) is None
        assert get_collections() == []  # No collections should be left

        # 5. Verify the article still exists
        article = get_article_by_id(article_id)
        assert article is not None
        assert article["id"] == article_id

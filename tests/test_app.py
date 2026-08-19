"""
Tests for Flask application routes.
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


# Import app after setting up test database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from meridiano.app import app
from meridiano.database import (
    add_article,
    create_collection,
    get_collection_by_id,
    save_brief,
)


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.test_client() as client:
        with app.app_context():
            from meridiano.models import SQLModel, get_session, init_db

            # Drop all tables to ensure a clean state before each test
            SQLModel.metadata.drop_all(get_session().bind)
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


class TestCollectionsRoutes:
    """Tests for collections-related Flask routes."""

    def test_collections_page_get(self, client):
        """Test GET /collections displays the page correctly."""
        response = client.get("/collections")
        assert response.status_code == 200
        assert b"Collections" in response.data
        assert b"No active collections." in response.data or b"No collections" in response.data

    def test_ajax_endpoints(self, client, sample_article_data):
        """Test the AJAX endpoints for adding/removing articles and checking status."""
        # Setup: Create an article and two collections
        with app.app_context():
            article_id = add_article(**sample_article_data)
            coll1_id = create_collection("Collection 1")
            coll2_id = create_collection("Collection 2")

        # 1. Test Status Endpoint (initially in no collections)
        response = client.get(f"/article/{article_id}/collections_status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        print(data)
        assert len(data["collections"]) == 2
        assert not any(c["contains"] for c in data["collections"])

        # 2. Test Add to Collection
        response = client.post(f"/collection/{coll1_id}/add_article", json={"article_id": article_id})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

        # 3. Test Status Endpoint again (should be in Collection 1)
        response = client.get(f"/article/{article_id}/collections_status")
        assert response.status_code == 200
        data = response.get_json()
        # Order of collections isn't guaranteed, so find the one we care about
        coll1_status = next(c for c in data["collections"] if c["id"] == coll1_id)
        coll2_status = next(c for c in data["collections"] if c["id"] == coll2_id)
        assert coll1_status["contains"]
        assert not coll2_status["contains"]

        # 4. Test Remove from Collection
        response = client.post(f"/collection/{coll1_id}/remove_article", json={"article_id": article_id})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

        # 5. Test Status Endpoint final time (should be in no collections)
        response = client.get(f"/article/{article_id}/collections_status")
        assert response.status_code == 200
        data = response.get_json()
        assert not any(c["contains"] for c in data["collections"])

    def test_collections_page_post_create(self, client):
        """Test POST /collections to create a new collection."""
        response = client.post(
            "/collections",
            data={"collection_name": "My New Collection"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Collection &#34;My New Collection&#34; created" in response.data
        # It should now be viewing the collection detail page
        assert b"Collection: My New Collection" in response.data

    def test_collections_page_post_create_empty_name(self, client):
        """Test POST /collections with an empty name."""
        response = client.post("/collections", data={"collection_name": ""}, follow_redirects=True)
        assert response.status_code == 200
        assert b"Collection name is required." in response.data
        assert b"Collections" in response.data  # Should be back on the collections list page

    def test_view_collection_not_found(self, client):
        """Test viewing a non-existent collection."""
        response = client.get("/collection/999")
        assert response.status_code == 404

    def test_delete_collection_post(self, client):
        """Test POST to delete a collection."""
        # 1. Create a collection to delete
        with app.app_context():
            coll_id = create_collection("Ephemeral Collection")

        # Check it exists on the collections page
        response = client.get("/collections")
        assert b"Ephemeral Collection" in response.data

        # 2. Send POST request to delete it
        response = client.post(
            f"/collection/{coll_id}/delete",
            follow_redirects=True,
        )

        # 3. Verify response and effects
        assert response.status_code == 200
        # Check we are back on the collections list page
        assert b"Collections" in response.data
        # Check for success flash message
        assert b'Collection &#34;Ephemeral Collection&#34; has been deleted.' in response.data
        # Check the link to the collection is no longer on the page.
        # We don't check for the name alone, as it appears in the flash message.
        assert f'<a href="/collection/{coll_id}"'.encode() not in response.data
        assert b"No active collections." in response.data or b"No collections" in response.data

    def test_delete_nonexistent_collection_post(self, client):
        """Test POST to delete a collection that does not exist."""
        # 1. Send POST request to delete a non-existent collection
        response = client.post(
            "/collection/9999/delete",
            follow_redirects=True,
        )

        # 2. Verify response
        assert response.status_code == 200
        # Check we are back on the collections list page
        assert b"Collections" in response.data
        # Check for error flash message
        assert b"Collection with ID 9999 not found, could not delete." in response.data

    def test_archive_collection_flow(self, client):
        """Test the flow of archiving and un-archiving a collection."""
        # 1. Create a collection
        with app.app_context():
            coll_id = create_collection("To Be Archived")

        # 2. Archive it
        response = client.post(f"/collection/{coll_id}/toggle_archive", follow_redirects=True)
        assert response.status_code == 200
        assert b"Collection has been archived" in response.data

        # Verify in DB
        with app.app_context():
            coll = get_collection_by_id(coll_id)
            assert coll['archived'] is True

        # 3. Verify it shows up in "Archived Collections" section
        response = client.get("/collections")
        assert b"Archived Collections" in response.data
        assert b"To Be Archived" in response.data

        # 4. Un-archive it
        response = client.post(f"/collection/{coll_id}/toggle_archive", follow_redirects=True)
        assert response.status_code == 200
        assert b"Collection has been un-archived" in response.data

        # Verify in DB
        with app.app_context():
            coll = get_collection_by_id(coll_id)
            assert coll['archived'] is False

    def test_archive_nonexistent_collection(self, client):
        """Test attempting to archive a collection that doesn't exist."""
        response = client.post("/collection/9999/toggle_archive", follow_redirects=True)
        assert response.status_code == 200
        assert b"Collection with ID 9999 not found" in response.data


class TestViewBriefRoute:
    """Tests for the brief page and the source list underneath it."""

    def _seed_articles(self, sample_article_data, count):
        """Adds ``count`` articles and returns their ids."""
        article_ids = []
        with app.app_context():
            for i in range(1, count + 1):
                article_ids.append(
                    add_article(
                        f"https://example.com/src{i}",
                        f"Source Article {i}",
                        sample_article_data["published_date"],
                        sample_article_data["feed_source"],
                        sample_article_data["raw_content"],
                        sample_article_data["feed_profile"],
                        sample_article_data["image_url"],
                    )
                )
        return article_ids

    def test_brief_not_found(self, client):
        """Test that an unknown brief id is a 404."""
        assert client.get("/brief/9999").status_code == 404

    def test_cluster_topics_are_not_rendered(self, client, sample_article_data):
        """Test that clustered sources collapse into one list with no topic headings."""
        first, second = self._seed_articles(sample_article_data, 2)
        with app.app_context():
            brief_id = save_brief(
                "# Brief",
                [first, second],
                "test",
                article_links=[
                    {"article_id": first, "cluster_index": 0, "cluster_topic": "Chips And Fabs"},
                    {"article_id": second, "cluster_index": 1, "cluster_topic": "Cloud Outages"},
                ],
            )

        response = client.get(f"/brief/{brief_id}")

        assert response.status_code == 200
        assert b"Chips And Fabs" not in response.data
        assert b"Cloud Outages" not in response.data
        assert response.data.count(b'<ul class="article-list">') == 1
        assert b"Source Article 1" in response.data
        assert b"Source Article 2" in response.data

    def test_clustered_sources_are_ranked_by_impact_across_clusters(self, client, sample_article_data):
        """Test that impact rank wins over cluster order in the flattened list."""
        article_ids = self._seed_articles(sample_article_data, 3)
        with app.app_context():
            from meridiano.models import Article, get_session

            with get_session() as session:
                for article_id, score in zip(article_ids, [2, 9, None]):
                    session.get(Article, article_id).impact_score = score
                session.commit()
            brief_id = save_brief(
                "# Brief",
                article_ids,
                "test",
                article_links=[
                    {"article_id": article_ids[0], "cluster_index": 0, "cluster_topic": "First"},
                    {"article_id": article_ids[2], "cluster_index": 0, "cluster_topic": "First"},
                    {"article_id": article_ids[1], "cluster_index": 1, "cluster_topic": "Second"},
                ],
            )

        html = client.get(f"/brief/{brief_id}").get_data(as_text=True)

        positions = [html.index(f"Source Article {i}") for i in (2, 1, 3)]
        assert positions == sorted(positions), "expected impact 9, then 2, then unscored"

    def test_legacy_brief_falls_back_to_contributing_ids(self, client, sample_article_data):
        """Test that a brief predating source tracking still lists its articles."""
        article_ids = self._seed_articles(sample_article_data, 2)
        with app.app_context():
            brief_id = save_brief("# Brief", article_ids, "test")

        response = client.get(f"/brief/{brief_id}")

        assert response.status_code == 200
        assert b"Source Article 1" in response.data
        assert b"Source Article 2" in response.data

    def test_legacy_sources_are_ranked_by_impact(self, client, sample_article_data):
        """Test that a brief with no clusters still leads with its strongest story."""
        article_ids = self._seed_articles(sample_article_data, 3)
        with app.app_context():
            from meridiano.models import Article, get_session

            with get_session() as session:
                for article_id, score in zip(article_ids, [2, 9, None]):
                    session.get(Article, article_id).impact_score = score
                session.commit()
            brief_id = save_brief("# Brief", article_ids, "test")

        html = client.get(f"/brief/{brief_id}").get_data(as_text=True)

        positions = [html.index(f"Source Article {i}") for i in (2, 1, 3)]
        assert positions == sorted(positions), "expected impact 9, then 2, then unscored"

    def test_source_list_is_capped(self, client, sample_article_data):
        """Test that a huge legacy id list is trimmed and the total is disclosed."""
        article_ids = self._seed_articles(sample_article_data, 5)
        with app.app_context():
            brief_id = save_brief("# Brief", article_ids, "test")

        with patch("meridiano.app.config.BRIEF_MAX_SOURCES", 2):
            response = client.get(f"/brief/{brief_id}")

        assert response.status_code == 200
        assert b"(2 of 5)" in response.data
        assert b"Source Article 3" not in response.data

    def test_sources_open_by_default(self, client, sample_article_data):
        """Test that the source list is expanded for tracked and legacy briefs alike."""
        (article_id,) = self._seed_articles(sample_article_data, 1)
        with app.app_context():
            tracked = save_brief(
                "# Brief",
                [article_id],
                "test",
                article_links=[{"article_id": article_id, "cluster_index": 0, "cluster_topic": "Topic"}],
            )
            legacy = save_brief("# Brief", [article_id], "test")

        for brief_id in (tracked, legacy):
            assert b"<details class=\"brief-sources\" open>" in client.get(f"/brief/{brief_id}").data

    def test_brief_without_sources_omits_the_section(self, client):
        """Test that a brief with no surviving articles renders no Sources block."""
        with app.app_context():
            brief_id = save_brief("# Brief", [], "test")

        response = client.get(f"/brief/{brief_id}")

        assert response.status_code == 200
        assert b"brief-sources" not in response.data

    def test_deleted_source_article_is_skipped(self, client, sample_article_data):
        """Test that a link pointing at a removed article does not break the page."""
        (article_id,) = self._seed_articles(sample_article_data, 1)
        with app.app_context():
            brief_id = save_brief(
                "# Brief",
                [article_id],
                "test",
                article_links=[
                    {"article_id": article_id, "cluster_index": 0, "cluster_topic": "Topic"},
                    {"article_id": 999999, "cluster_index": 1, "cluster_topic": "Gone"},
                ],
            )

        response = client.get(f"/brief/{brief_id}")

        assert response.status_code == 200
        assert b"Source Article 1" in response.data
        assert b"(1)" in response.data


class TestHeaderActiveLinks:
    """Tests for active navigation link styling in the header."""

    def test_briefs_link_active_on_index(self, client):
        """Test that the 'Briefs' link is active on the index page."""
        response = client.get("/")
        assert response.status_code == 200
        # Check for active link
        assert b'class="active">Briefs</a>' in response.data
        # Check that other links are not active
        assert b'class="active">Articles</a>' not in response.data
        assert b'class="active">Collections</a>' not in response.data

    def test_articles_link_active_on_articles_list(self, client):
        """Test that the 'Articles' link is active on the articles list page."""
        response = client.get("/articles")
        assert response.status_code == 200
        assert b'class="active">Articles</a>' in response.data
        assert b'class="active">Briefs</a>' not in response.data
        assert b'class="active">Collections</a>' not in response.data

    def test_articles_link_active_on_add_article(self, client):
        """Test that the 'Articles' link is active on the add article page."""
        response = client.get("/add_article")
        assert response.status_code == 200
        assert b'class="active">Articles</a>' in response.data
        assert b'class="active">Briefs</a>' not in response.data
        assert b'class="active">Collections</a>' not in response.data

    def test_articles_link_active_on_view_article(self, client, sample_article_data):
        """Test that the 'Articles' link is active on the view article page."""
        with app.app_context():
            article_id = add_article(**sample_article_data)

        response = client.get(f"/article/{article_id}")
        assert response.status_code == 200
        assert b'class="active">Articles</a>' in response.data
        assert b'class="active">Briefs</a>' not in response.data
        assert b'class="active">Collections</a>' not in response.data

    def test_collections_link_active_on_collections_list(self, client):
        """Test that the 'Collections' link is active on the collections list page."""
        response = client.get("/collections")
        assert response.status_code == 200
        assert b'class="active">Collections</a>' in response.data
        assert b'class="active">Briefs</a>' not in response.data
        assert b'class="active">Articles</a>' not in response.data

    def test_collections_link_active_on_view_collection(self, client):
        """Test that the 'Collections' link is active on a collection detail page."""
        with app.app_context():
            collection_id = create_collection("Test Collection")

        response = client.get(f"/collection/{collection_id}")
        assert response.status_code == 200
        assert b'class="active">Collections</a>' in response.data
        assert b'class="active">Briefs</a>' not in response.data
        assert b'class="active">Articles</a>' not in response.data

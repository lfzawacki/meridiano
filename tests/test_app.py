"""
Tests for Flask application routes.
"""

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


# Import app after setting up test database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from meridiano.app import app
from meridiano.database import add_article, add_article_to_collection, create_collection, get_collection_by_id


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


class TestFullArticleContent:
    """Full article section on the article page and the collection reader."""

    def _add(self, url="https://example.com/full", title="Full Story", full_html=None, paywalled=None):
        return add_article(
            url=url,
            title=title,
            published_date=datetime(2024, 1, 1),
            feed_source="Test Feed",
            raw_content="plain text body",
            feed_profile="tech",
            full_content_html=full_html,
            full_content_paywalled=paywalled,
        )

    def test_paywall_notices(self, client):
        cut = self._add(url="https://example.com/cut", full_html="<p>The deal was signed by the</p>", paywalled=True)
        marked = self._add(url="https://example.com/marked", full_html="<p>Whole story.</p>", paywalled=True)
        free = self._add(url="https://example.com/free", full_html="<p>Free story</p>", paywalled=False)
        assert b"Cut off by a paywall" in client.get(f"/article/{cut}").data
        marked_page = client.get(f"/article/{marked}").data
        assert b"Subscriber-only site" in marked_page
        assert b"Cut off by a paywall" not in marked_page
        assert b"paywall-notice" not in client.get(f"/article/{free}").data

    def test_article_page_shows_stored_full_content(self, client):
        article_id = self._add(full_html='<p>Rich body</p><img src="https://example.com/i.jpg">')
        response = client.get(f"/article/{article_id}")
        assert response.status_code == 200
        assert b"Full Article" in response.data
        assert b'id="full-content-container"' in response.data
        assert b"<p>Rich body</p>" in response.data

    def test_article_page_offers_fetch_when_missing(self, client):
        article_id = self._add()
        response = client.get(f"/article/{article_id}")
        assert b"has not been fetched yet" in response.data
        assert f"/article/{article_id}/fetch_full_content".encode() in response.data

    def test_fetch_route_stores_html(self, client):
        article_id = self._add()
        fake = {"content": "x", "og_image": None, "full_html": "<p>Fetched body</p>"}
        with patch("meridiano.app.fetch_article_content_and_og_image", return_value=fake):
            response = client.post(f"/article/{article_id}/fetch_full_content", data={"next": "//evil.example"})
        # Absolute/protocol-relative "next" values are ignored.
        assert response.status_code == 302
        assert response.headers["Location"].endswith(f"/article/{article_id}")

        from meridiano.database import get_article_by_id

        stored = get_article_by_id(article_id)
        assert stored["full_content_html"] == "<p>Fetched body</p>"
        assert stored["full_content_fetched_at"] is not None

    def test_failed_fetch_keeps_existing_html(self, client):
        article_id = self._add(full_html="<p>Old body</p>")
        fake = {"content": None, "og_image": None, "full_html": None}
        with patch("meridiano.app.fetch_article_content_and_og_image", return_value=fake):
            client.post(f"/article/{article_id}/fetch_full_content")

        from meridiano.database import get_article_by_id

        assert get_article_by_id(article_id)["full_content_html"] == "<p>Old body</p>"

    def test_collection_reader_navigation(self, client):
        first = self._add(url="https://example.com/1", title="First", full_html="<p>First body</p>")
        second = self._add(url="https://example.com/2", title="Second")
        coll_id = create_collection("Reading list")
        add_article_to_collection(coll_id, first)
        add_article_to_collection(coll_id, second)

        detail = client.get(f"/collection/{coll_id}")
        assert f"/collection/{coll_id}/read".encode() in detail.data

        response = client.get(f"/collection/{coll_id}/read/{first}")
        assert response.status_code == 200
        assert b"<p>First body</p>" in response.data

        response = client.get(f"/collection/{coll_id}/read/{second}")
        assert b"plain text body" in response.data
        assert b"has not been fetched yet" in response.data

        assert client.get(f"/collection/{coll_id}/read").status_code == 200

    def test_collection_reader_rejects_foreign_article(self, client):
        outsider = self._add(url="https://example.com/out")
        inside = self._add(url="https://example.com/in")
        coll_id = create_collection("C")
        add_article_to_collection(coll_id, inside)
        assert client.get(f"/collection/{coll_id}/read/{outsider}").status_code == 404

    def test_empty_collection_reader_redirects(self, client):
        coll_id = create_collection("Empty")
        assert client.get(f"/collection/{coll_id}/read").status_code == 302

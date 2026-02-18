"""
Tests for Flask application routes.
"""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


# Import app after setting up test database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from meridiano.app import app
from meridiano.database import add_article, create_collection


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
        assert b"No collections yet." in response.data

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

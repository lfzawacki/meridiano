"""
Tests for Flask application routes.
"""

import os
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


# Import app after setting up test database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from meridiano import config_base
from meridiano.app import app
from meridiano.database import (
    add_article,
    create_collection,
    get_collection_by_id,
    update_article_processing,
    update_article_rating,
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


def add_test_article(**overrides):
    """Adds an article for RSS tests with a unique URL and sensible defaults."""
    defaults = {
        "url": f"https://example.com/{uuid.uuid4().hex}",
        "title": "Test Article",
        "published_date": datetime(2024, 1, 15, 10, 30),
        "feed_source": "Test Feed",
        "raw_content": "This is test content for an article.",
        "feed_profile": "test",
        "image_url": None,
    }
    defaults.update(overrides)
    return add_article(**defaults)


class TestProfileRssRoute:
    """Tests for the per-profile RSS output feeds."""

    def test_rss_route_content_type_and_channel(self, client, sample_article_data):
        """Test the feed returns an RSS 2.0 document with the channel metadata."""
        with app.app_context():
            add_article(**sample_article_data)

        response = client.get("/test.rss")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/rss+xml")

        root = ET.fromstring(response.data)
        assert root.tag == "rss"
        assert root.attrib["version"] == "2.0"

        channel = root.find("channel")
        assert channel.find("title").text == "Meridiano — test"
        assert channel.find("link").text.endswith("/articles?feed_profile=test")
        assert channel.find("description").text is not None
        assert channel.find("lastBuildDate").text is not None

        atom_link = channel.find("{http://www.w3.org/2005/Atom}link")
        assert atom_link is not None
        assert atom_link.attrib["rel"] == "self"
        assert atom_link.attrib["href"].endswith("/test.rss")

    def test_rss_unknown_profile_returns_404(self, client):
        """Test that requesting a profile not present in the DB returns a 404."""
        response = client.get("/nosuchfeed.rss")
        assert response.status_code == 404

    def test_rss_item_contains_article_main_information(self, client, sample_article_data):
        """Test an item exposes the original link, AI summary, date and impact score."""
        with app.app_context():
            article_id = add_article(**sample_article_data)
            update_article_processing(article_id, "This is the AI summary.", None)
            update_article_rating(article_id, 7)

        response = client.get("/test.rss")
        root = ET.fromstring(response.data)
        items = root.findall("channel/item")
        assert len(items) == 1

        item = items[0]
        assert item.find("title").text == "Test Article"
        assert item.find("link").text == "https://example.com/article1"
        guid = item.find("guid")
        assert guid.attrib["isPermaLink"] == "true"
        assert item.find("description").text.strip() == "<p>This is the AI summary.</p>"
        assert item.find("category").text == "impact:7"

        parsed = parsedate_to_datetime(item.find("pubDate").text)
        assert (parsed.year, parsed.month, parsed.day) == (2024, 1, 15)

    def test_rss_item_optional_fields(self, client, sample_article_data):
        """Test unrated items have no category, images become media:thumbnail, description uses the raw content."""
        with app.app_context():
            data = {**sample_article_data, "image_url": "https://example.com/image.jpg"}
            add_article(**data)

        response = client.get("/test.rss")
        root = ET.fromstring(response.data)
        item = root.findall("channel/item")[0]

        assert item.find("category") is None

        thumbnail = item.find("{http://search.yahoo.com/mrss/}thumbnail")
        assert thumbnail is not None
        assert thumbnail.attrib["url"] == "https://example.com/image.jpg"

        description = item.find("description")
        assert description is not None
        assert "This is test content for an article." in description.text

    def test_rss_items_ordered_newest_first(self, client):
        """Test the items are ordered by published date, newest first."""
        with app.app_context():
            add_test_article(title="Older Article", published_date=datetime(2024, 1, 1, 0, 0))
            add_test_article(title="Newer Article", published_date=datetime(2025, 6, 1, 0, 0))

        response = client.get("/test.rss")
        root = ET.fromstring(response.data)
        titles = [item.find("title").text for item in root.findall("channel/item")]
        assert titles == ["Newer Article", "Older Article"]

    def test_rss_respects_max_items_setting(self, client, monkeypatch):
        """Test that only RSS_MAX_ITEMS newest articles are exposed."""
        monkeypatch.setattr(config_base, "RSS_MAX_ITEMS", 1)
        with app.app_context():
            add_test_article(title="One", published_date=datetime(2024, 1, 1, 0, 0))
            add_test_article(title="Two", published_date=datetime(2024, 2, 1, 0, 0))

        response = client.get("/test.rss")
        root = ET.fromstring(response.data)
        titles = [item.find("title").text for item in root.findall("channel/item")]
        assert titles == ["Two"]

    def test_articles_page_has_rss_autodiscovery(self, client, sample_article_data):
        """Test the articles page advertises the RSS feed when filtered by profile."""
        with app.app_context():
            add_article(**sample_article_data)

        response = client.get("/articles?feed_profile=test")
        assert response.status_code == 200
        assert b' type="application/rss+xml"' in response.data
        assert b' href="/test.rss"' in response.data

        # No discovery links when no profile filter is applied
        response = client.get("/articles")
        assert b' type="application/rss+xml"' not in response.data

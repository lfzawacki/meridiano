import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import feedparser
import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from meridiano import database, models, run_briefing


@pytest.fixture
def setup_integration():
    # Create a temporary directory
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, "test_meridian.db")
    db_url = f"sqlite:///{db_path}"

    # Patch the database URL in config
    config_patcher = patch("meridiano.config_base.DATABASE_URL", db_url)
    config_patcher.start()

    # Re-create the engine with the new URL
    # We need to keep a reference to the old engine to restore it if needed,
    # but for tests usually we just overwrite.
    original_engine = models.engine
    models.engine = models.create_engine(db_url, echo=False)

    # Initialize the database
    models.create_db_and_tables()

    # Mock clients in run_briefing
    # We don't need to mock client/embedding_client objects anymore as they are just dicts now
    # Instead we need to mock litellm functions
    mock_completion = MagicMock()
    mock_embedding = MagicMock()

    completion_patcher = patch("meridiano.run_briefing.litellm.completion", mock_completion)
    embedding_patcher = patch("meridiano.run_briefing.litellm.embedding", mock_embedding)

    completion_patcher.start()
    embedding_patcher.start()

    yield {"mock_completion": mock_completion, "mock_embedding": mock_embedding, "test_dir": test_dir}

    # Teardown
    config_patcher.stop()
    completion_patcher.stop()
    embedding_patcher.stop()
    models.engine.dispose()
    models.engine = original_engine  # Restore original engine
    shutil.rmtree(test_dir)


@patch("meridiano.run_briefing.feedparser.parse")
@patch("meridiano.run_briefing.fetch_article_content_and_og_image")
def test_full_workflow(mock_fetch, mock_parse, setup_integration):
    # Access mocks from fixture
    mock_completion = setup_integration["mock_completion"]
    mock_embedding = setup_integration["mock_embedding"]

    # --- Setup Mocks ---

    # Mock RSS Feed with multiple entries
    entries = []
    for i in range(1, 6):  # Create 5 articles
        mock_entry = MagicMock()
        # We need to bind i to the lambda scope
        mock_entry.get.side_effect = (
            lambda i=i: lambda k, default=None: {
                "link": f"http://example.com/article{i}",
                "title": f"Test Article {i}",
                "published_parsed": time.struct_time((2023, 1, 1, 12, 0, 0, 6, 1, 0)),
            }.get(k, default)
        )()
        entries.append(mock_entry)

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = entries
    mock_feed.feed.get.return_value = "Test Feed Source"

    mock_parse.return_value = mock_feed

    # Mock Article Content Fetch
    mock_fetch.return_value = {
        "content": "This is the content of the test article. It is very interesting.",
        "og_image": "http://example.com/image.jpg",
    }

    # Mock DeepSeek Chat (Summarization, Rating, Analysis, Synthesis)
    def chat_side_effect(*args, **kwargs):
        messages = kwargs.get("messages", [])
        user_content = messages[-1]["content"] if messages else ""

        if "Summarize" in user_content:
            return {"choices": [{"message": {"content": "This is a summary."}}]}
        elif "Rate the impact" in user_content:
            return {"choices": [{"message": {"content": "8"}}]}
        elif "core event or topic" in user_content:  # Cluster analysis
            return {"choices": [{"message": {"content": "Cluster Analysis Result"}}]}
        elif "Presidential-style" in user_content:  # Brief synthesis
            return {"choices": [{"message": {"content": "# Final Brief\n\n- Point 1"}}]}
        return {"choices": [{"message": {"content": "Generic Response"}}]}

    mock_completion.side_effect = chat_side_effect

    # Mock Embeddings
    # Return slightly different embeddings to allow clustering
    def embedding_side_effect(*args, **kwargs):
        # Random-ish embedding
        import random

        return {"data": [{"embedding": [random.random(), random.random(), random.random()]}]}

    mock_embedding.side_effect = embedding_side_effect

    # --- Test Execution ---

    feed_profile = "test_profile"
    rss_feeds = ["http://example.com/rss"]

    # 1. Scrape
    run_briefing.scrape_articles(feed_profile, rss_feeds)

    # Verify Article in DB
    with database.get_session() as session:
        article = session.exec(
            database.select(models.Article).where(models.Article.url == "http://example.com/article1")
        ).first()
        assert article is not None
        assert article.title == "Test Article 1"

    # 2. Process
    class DummyConfig:
        LLM_CHAT_MODEL = "test-model"
        PROMPT_ARTICLE_SUMMARY = "Summarize: {article_content}"
        EMBEDDING_MODEL = "test-embedding"

    run_briefing.process_articles(feed_profile, DummyConfig())

    # Verify Processing
    with database.get_session() as session:
        session.expire_all()
        article = session.exec(
            database.select(models.Article).where(models.Article.url == "http://example.com/article1")
        ).first()
        assert article.processed_content == "This is a summary."
        assert article.embedding is not None

    # 3. Rate
    class DummyConfigRate(DummyConfig):
        PROMPT_IMPACT_RATING = "Rate the impact: {summary}"

    run_briefing.rate_articles(feed_profile, DummyConfigRate())

    # Verify Rating
    with database.get_session() as session:
        session.expire_all()
        article = session.exec(
            database.select(models.Article).where(models.Article.url == "http://example.com/article1")
        ).first()
        assert article.impact_score == 8

    # 4. Generate Brief
    # We have 5 articles. 5 // 2 = 2 clusters. This should satisfy n_clusters >= 2.
    # We need to ensure MIN_ARTICLES_FOR_BRIEFING is <= 5. Default is 5.

    with patch("meridiano.config_base.MIN_ARTICLES_FOR_BRIEFING", 2), patch("meridiano.config_base.N_CLUSTERS", 2):

        class DummyConfigBrief(DummyConfigRate):
            PROMPT_CLUSTER_ANALYSIS = "Analyze core event or topic: {cluster_summaries_text}"
            PROMPT_BRIEF_SYNTHESIS = "Write Presidential-style brief: {cluster_analyses_text}"
            RSS_FEEDS = rss_feeds

        run_briefing.generate_brief(feed_profile, DummyConfigBrief())

    # Verify Brief
    with database.get_session() as session:
        brief = session.exec(database.select(models.Brief)).first()
        assert brief is not None
        assert "# Final Brief" in brief.brief_markdown
        assert brief.feed_profile == feed_profile


@patch("meridiano.run_briefing.importlib.import_module")
def test_cli_main(mock_import, setup_integration):
    # Mock feed config import
    mock_feed_config = MagicMock()
    mock_feed_config.RSS_FEEDS = ["http://example.com/rss"]
    mock_feed_config.__name__ = "meridiano.feeds.test"
    mock_import.return_value = mock_feed_config

    # Test --all
    with (
        patch.object(run_briefing, "scrape_articles") as mock_scrape,
        patch.object(run_briefing, "process_articles") as mock_process,
        patch.object(run_briefing, "rate_articles") as mock_rate,
        patch.object(run_briefing, "generate_brief") as mock_generate,
    ):
        with patch.object(sys, "argv", ["run_briefing.py", "--feed", "test", "--all"]):
            run_briefing.main()

            mock_scrape.assert_called_once()
            mock_process.assert_called_once()
            mock_rate.assert_called_once()
            mock_generate.assert_called_once()

        # Reset mocks
        mock_scrape.reset_mock()
        mock_process.reset_mock()
        mock_rate.reset_mock()
        mock_generate.reset_mock()

        # Test individual stage
        with patch.object(sys, "argv", ["run_briefing.py", "--feed", "test", "--scrape-articles"]):
            run_briefing.main()

            mock_scrape.assert_called_once()
            mock_process.assert_not_called()
            mock_rate.assert_not_called()
            mock_generate.assert_not_called()


def test_edge_cases(setup_integration):
    feed_profile = "test_edge"
    rss_feeds = ["http://example.com/rss"]

    # 1. Test Scrape with Existing Article
    # Create an existing article in DB
    with database.get_session() as session:
        existing_article = models.Article(
            title="Existing Article",
            url="http://example.com/existing",
            published_date=datetime.now(),
            feed_source="Test Source",
            feed_profile=feed_profile,
        )
        session.add(existing_article)
        session.commit()

    # Mock feed with SAME article
    mock_feed = feedparser.FeedParserDict()
    mock_feed.bozo = 0  # No errors
    mock_feed.feed = feedparser.FeedParserDict({"title": "Test Feed"})
    mock_feed.entries = [
        feedparser.FeedParserDict(
            {
                "title": "Existing Article",
                "link": "http://example.com/existing",
                "published_parsed": time.struct_time((2023, 1, 1, 12, 0, 0, 6, 1, 0)),
                "summary": "Summary",
                "source": {"title": "Test Source"},
            }
        )
    ]

    with patch("meridiano.run_briefing.feedparser.parse", return_value=mock_feed):
        run_briefing.scrape_articles(feed_profile, rss_feeds)

    # Verify NO new article added (count should be 1)
    with database.get_session() as session:
        articles = session.exec(
            database.select(models.Article).where(models.Article.feed_profile == feed_profile)
        ).all()
        assert len(articles) == 1

    # 2. Test Generate Brief with Not Enough Articles
    # We have 1 article. Min is 5.
    class DummyConfig:
        MIN_ARTICLES_FOR_BRIEFING = 5
        RSS_FEEDS = rss_feeds

    # Capture stdout to check for print message
    from io import StringIO

    captured_output = StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_output

    try:
        run_briefing.generate_brief(feed_profile, DummyConfig())
    finally:
        sys.stdout = original_stdout

    output = captured_output.getvalue()
    assert "Not enough recent articles" in output


def test_empty_feed_profile(setup_integration):
    # Mock import to return config with NO feeds
    mock_feed_config = MagicMock()
    mock_feed_config.RSS_FEEDS = []
    mock_feed_config.__name__ = "meridiano.feeds.empty"

    with patch("meridiano.run_briefing.importlib.import_module", return_value=mock_feed_config):
        with patch.object(sys, "argv", ["run_briefing.py", "--feed", "empty", "--all"]):
            # Capture stdout
            from io import StringIO

            captured_output = StringIO()
            original_stdout = sys.stdout
            sys.stdout = captured_output

            try:
                run_briefing.main()
            finally:
                sys.stdout = original_stdout

            output = captured_output.getvalue()
            assert "Skipping scrape stage: No RSS_FEEDS found" in output
            assert "Skipping generate stage: No RSS_FEEDS found" in output


def _completion(content, finish_reason="stop"):
    """Builds a litellm-shaped reply."""
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


class TestChatCompletionBudget:
    """Reasoning models burn the completion budget before answering; see LLM_MAX_TOKENS."""

    def test_uses_the_configured_budget(self, setup_integration):
        """Test that the default budget comes from config rather than a hardcoded value."""
        mock_completion = setup_integration["mock_completion"]
        mock_completion.side_effect = None
        mock_completion.return_value = _completion("An answer.")

        with patch("meridiano.config_base.LLM_MAX_TOKENS", 4321):
            assert run_briefing.call_deepseek_chat("Prompt") == "An answer."

        assert mock_completion.call_args.kwargs["max_tokens"] == 4321

    def test_retries_with_a_bigger_budget_when_reasoning_ate_it_all(self, setup_integration):
        """Test that an empty finish_reason='length' reply is retried, not given up on."""
        mock_completion = setup_integration["mock_completion"]
        mock_completion.side_effect = [
            _completion("", finish_reason="length"),
            _completion("The real brief."),
        ]

        with patch("meridiano.config_base.LLM_MAX_TOKENS", 1000):
            assert run_briefing.call_deepseek_chat("Prompt") == "The real brief."

        budgets = [call.kwargs["max_tokens"] for call in mock_completion.call_args_list]
        assert budgets == [1000, 1000 * run_briefing.EMPTY_RESPONSE_RETRY_FACTOR]

    def test_gives_up_after_one_retry(self, setup_integration):
        """Test that a persistently empty response ends the loop instead of spinning."""
        mock_completion = setup_integration["mock_completion"]
        mock_completion.side_effect = [
            _completion("", finish_reason="length"),
            _completion("", finish_reason="length"),
        ]

        assert run_briefing.call_deepseek_chat("Prompt") is None
        assert mock_completion.call_count == 2

    def test_empty_answer_that_is_not_truncated_is_not_retried(self, setup_integration):
        """Test that a model which simply answered nothing is not billed for a retry."""
        mock_completion = setup_integration["mock_completion"]
        mock_completion.side_effect = None
        mock_completion.return_value = _completion("", finish_reason="stop")

        assert run_briefing.call_deepseek_chat("Prompt") is None
        assert mock_completion.call_count == 1

    def test_missing_content_key_is_treated_as_empty(self, setup_integration):
        """Test that a reply carrying only reasoning_content does not raise."""
        mock_completion = setup_integration["mock_completion"]
        mock_completion.side_effect = None
        mock_completion.return_value = {
            "choices": [{"message": {"reasoning_content": "thinking..."}, "finish_reason": "stop"}]
        }

        assert run_briefing.call_deepseek_chat("Prompt") is None


class TestSplitTopicLine:
    """The TOPIC line is a source-list heading, not part of the brief text."""

    def test_extracts_the_topic_and_drops_the_line(self):
        """Test that the heading is lifted off and the analysis keeps the rest."""
        topic, analysis = run_briefing.split_topic_line("TOPIC: Chips And Fabs\n\nThe real analysis.")

        assert topic == "Chips And Fabs"
        assert analysis == "The real analysis."

    def test_tolerates_markdown_emphasis_and_quotes(self):
        """Test that a model wrapping the line in ** or quotes still parses."""
        topic, analysis = run_briefing.split_topic_line('**TOPIC:** "Cloud Outages"\n\nBody.')

        assert topic == "Cloud Outages"
        assert analysis == "Body."

    def test_missing_topic_line_leaves_the_analysis_untouched(self):
        """Test that a model ignoring the instruction costs nothing."""
        topic, analysis = run_briefing.split_topic_line("Straight into the analysis.")

        assert topic is None
        assert analysis == "Straight into the analysis."


class TestBuildArticleLinks:
    """Only articles the model actually saw may be credited as sources."""

    def test_numbers_clusters_and_carries_their_topic(self):
        """Test that link rows record the cluster order and heading."""
        clusters = [
            {"topic": "First", "referenced_articles": [{"id": 1}, {"id": 2}]},
            {"topic": "Second", "referenced_articles": [{"id": 3}]},
        ]

        links = run_briefing.build_article_links(clusters)

        assert links == [
            {"article_id": 1, "cluster_index": 0, "cluster_topic": "First"},
            {"article_id": 2, "cluster_index": 0, "cluster_topic": "First"},
            {"article_id": 3, "cluster_index": 1, "cluster_topic": "Second"},
        ]

    def test_an_article_in_two_clusters_is_listed_once(self):
        """Test that the first cluster wins, so the source list has no duplicates."""
        clusters = [
            {"topic": "First", "referenced_articles": [{"id": 1}]},
            {"topic": "Second", "referenced_articles": [{"id": 1}, {"id": 2}]},
        ]

        links = run_briefing.build_article_links(clusters)

        assert [(link["article_id"], link["cluster_index"]) for link in links] == [(1, 0), (2, 1)]


def _seed_processed_articles(count, feed_profile="test"):
    """Adds articles that are already summarized and embedded, ready for briefing."""
    article_ids = []
    for i in range(1, count + 1):
        article_id = database.add_article(
            f"http://example.com/src{i}",
            f"Source Article {i}",
            datetime.now(),
            f"Source {i}",
            "Raw content.",
            feed_profile,
            None,
        )
        database.update_article_processing(article_id, f"Summary {i}.", [i * 0.1, i * 0.2, i * 0.3])
        article_ids.append(article_id)
    return article_ids


def test_generate_brief_records_its_sources(setup_integration):
    """A generated brief links the articles its clusters were built from."""
    mock_completion = setup_integration["mock_completion"]
    feed_profile = "test"
    _seed_processed_articles(6, feed_profile)

    def chat_side_effect(*args, **kwargs):
        user_content = kwargs.get("messages", [])[-1]["content"]
        if "core event or topic" in user_content:
            content = "TOPIC: Seeded Topic\n\nCluster analysis body."
        else:
            content = "# Final Brief\n\n- Point one\n- Point two"
        return {"choices": [{"message": {"content": content}}]}

    mock_completion.side_effect = chat_side_effect

    effective_config = MagicMock()
    effective_config.PROMPT_CLUSTER_ANALYSIS = run_briefing.config.PROMPT_CLUSTER_ANALYSIS
    effective_config.PROMPT_BRIEF_SYNTHESIS = run_briefing.config.PROMPT_BRIEF_SYNTHESIS
    effective_config.PROMPT_CLUSTER_TOPIC_RULE = run_briefing.config.PROMPT_CLUSTER_TOPIC_RULE
    effective_config.LLM_CHAT_MODEL = "test-model"

    with patch("meridiano.config_base.MIN_ARTICLES_FOR_BRIEFING", 2):
        run_briefing.generate_brief(feed_profile, effective_config)

    brief = database.get_all_briefs_metadata(feed_profile=feed_profile)[0]
    links = database.get_brief_article_links(brief["id"])

    assert links, "the brief should record the articles it was built from"
    # The TOPIC line is a heading only; it must not survive into the brief text.
    assert "TOPIC:" not in database.get_brief_by_id(brief["id"])["brief_markdown"]
    assert all(link["cluster_topic"] == "Seeded Topic" for link in links)
    assert len(links) == len({link["article_id"] for link in links})

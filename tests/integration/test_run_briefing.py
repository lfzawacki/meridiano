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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from meridiano import database, models, run_briefing


@pytest.fixture
def setup_integration():
    # Create a temporary directory
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, "test_meridian.db")
    db_url = f"sqlite:///{db_path}"

    # Patch the database URL in config
    config_patcher = patch('meridiano.config_base.DATABASE_URL', db_url)
    config_patcher.start()

    # Re-create the engine with the new URL
    # We need to keep a reference to the old engine to restore it if needed, 
    # but for tests usually we just overwrite.
    original_engine = models.engine
    models.engine = models.create_engine(db_url, echo=False)
    
    # Initialize the database
    models.create_db_and_tables()

    # Mock clients in run_briefing
    mock_client = MagicMock()
    mock_embedding_client = MagicMock()
    
    # Patch the clients in run_briefing module
    client_patcher = patch('meridiano.run_briefing.client', mock_client)
    embedding_client_patcher = patch('meridiano.run_briefing.embedding_client', mock_embedding_client)
    
    client_patcher.start()
    embedding_client_patcher.start()

    yield {
        'mock_client': mock_client,
        'mock_embedding_client': mock_embedding_client,
        'test_dir': test_dir
    }

    # Teardown
    config_patcher.stop()
    client_patcher.stop()
    embedding_client_patcher.stop()
    models.engine.dispose()
    models.engine = original_engine # Restore original engine
    shutil.rmtree(test_dir)

@patch('meridiano.run_briefing.feedparser.parse')
@patch('meridiano.run_briefing.fetch_article_content_and_og_image')
def test_full_workflow(mock_fetch, mock_parse, setup_integration):
    # Access mocks from fixture
    mock_client = setup_integration['mock_client']
    mock_embedding_client = setup_integration['mock_embedding_client']

    # --- Setup Mocks ---
    
    # Mock RSS Feed with multiple entries
    entries = []
    for i in range(1, 6): # Create 5 articles
        mock_entry = MagicMock()
        # We need to bind i to the lambda scope
        mock_entry.get.side_effect = (lambda i=i: lambda k, default=None: {
            'link': f'http://example.com/article{i}',
            'title': f'Test Article {i}',
            'published_parsed': time.struct_time((2023, 1, 1, 12, 0, 0, 6, 1, 0))
        }.get(k, default))()
        entries.append(mock_entry)
    
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = entries
    mock_feed.feed.get.return_value = 'Test Feed Source'
    
    mock_parse.return_value = mock_feed

    # Mock Article Content Fetch
    mock_fetch.return_value = {
        'content': 'This is the content of the test article. It is very interesting.',
        'og_image': 'http://example.com/image.jpg'
    }

    # Mock DeepSeek Chat (Summarization, Rating, Analysis, Synthesis)
    def chat_side_effect(*args, **kwargs):
        messages = kwargs.get('messages', [])
        user_content = messages[-1]['content'] if messages else ""
        
        if "Summarize" in user_content:
            return MagicMock(choices=[MagicMock(message=MagicMock(content="This is a summary."))])
        elif "Rate the impact" in user_content:
            return MagicMock(choices=[MagicMock(message=MagicMock(content="8"))])
        elif "core event or topic" in user_content: # Cluster analysis
            return MagicMock(choices=[MagicMock(message=MagicMock(content="Cluster Analysis Result"))])
        elif "Presidential-style" in user_content: # Brief synthesis
            return MagicMock(choices=[MagicMock(message=MagicMock(content="# Final Brief\n\n- Point 1"))])
        return MagicMock(choices=[MagicMock(message=MagicMock(content="Generic Response"))])

    mock_client.chat.completions.create.side_effect = chat_side_effect

    # Mock Embeddings
    # Return slightly different embeddings to allow clustering
    def embedding_side_effect(*args, **kwargs):
        # Random-ish embedding
        import random
        return MagicMock(data=[MagicMock(embedding=[random.random(), random.random(), random.random()])])
        
    mock_embedding_client.embeddings.create.side_effect = embedding_side_effect

    # --- Test Execution ---
    
    feed_profile = 'test_profile'
    rss_feeds = ['http://example.com/rss']
    
    # 1. Scrape
    run_briefing.scrape_articles(feed_profile, rss_feeds)
    
    # Verify Article in DB
    with database.get_session() as session:
        article = session.exec(database.select(models.Article).where(models.Article.url == 'http://example.com/article1')).first()
        assert article is not None
        assert article.title == 'Test Article 1'

    # 2. Process
    class DummyConfig:
        DEEPSEEK_CHAT_MODEL = 'test-model'
        PROMPT_ARTICLE_SUMMARY = "Summarize: {article_content}"
        EMBEDDING_MODEL = 'test-embedding'
        
    run_briefing.process_articles(feed_profile, DummyConfig())
    
    # Verify Processing
    with database.get_session() as session:
        session.expire_all()
        article = session.exec(database.select(models.Article).where(models.Article.url == 'http://example.com/article1')).first()
        assert article.processed_content == "This is a summary."
        assert article.embedding is not None

    # 3. Rate
    class DummyConfigRate(DummyConfig):
        PROMPT_IMPACT_RATING = "Rate the impact: {summary}"
        
    run_briefing.rate_articles(feed_profile, DummyConfigRate())
    
    # Verify Rating
    with database.get_session() as session:
        session.expire_all()
        article = session.exec(database.select(models.Article).where(models.Article.url == 'http://example.com/article1')).first()
        assert article.impact_score == 8

    # 4. Generate Brief
    # We have 5 articles. 5 // 2 = 2 clusters. This should satisfy n_clusters >= 2.
    # We need to ensure MIN_ARTICLES_FOR_BRIEFING is <= 5. Default is 5.
    
    with patch('meridiano.config_base.MIN_ARTICLES_FOR_BRIEFING', 2), \
            patch('meridiano.config_base.N_CLUSTERS', 2):
        
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

@patch('meridiano.run_briefing.importlib.import_module')
def test_cli_main(mock_import, setup_integration):
    # Mock feed config import
    mock_feed_config = MagicMock()
    mock_feed_config.RSS_FEEDS = ['http://example.com/rss']
    mock_feed_config.__name__ = 'meridiano.feeds.test'
    mock_import.return_value = mock_feed_config

    # Test --all
    with patch.object(run_briefing, 'scrape_articles') as mock_scrape, \
            patch.object(run_briefing, 'process_articles') as mock_process, \
            patch.object(run_briefing, 'rate_articles') as mock_rate, \
            patch.object(run_briefing, 'generate_brief') as mock_generate:
        
        with patch.object(sys, 'argv', ['run_briefing.py', '--feed', 'test', '--all']):
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
        with patch.object(sys, 'argv', ['run_briefing.py', '--feed', 'test', '--scrape-articles']):
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
            feed_profile=feed_profile
        )
        session.add(existing_article)
        session.commit()

    # Mock feed with SAME article
    mock_feed = feedparser.FeedParserDict()
    mock_feed.bozo = 0 # No errors
    mock_feed.feed = feedparser.FeedParserDict({'title': 'Test Feed'})
    mock_feed.entries = [
        feedparser.FeedParserDict({
            'title': 'Existing Article',
            'link': 'http://example.com/existing',
            'published_parsed': time.struct_time((2023, 1, 1, 12, 0, 0, 6, 1, 0)),
            'summary': 'Summary',
            'source': {'title': 'Test Source'}
        })
    ]
    
    with patch('meridiano.run_briefing.feedparser.parse', return_value=mock_feed):
        run_briefing.scrape_articles(feed_profile, rss_feeds)
        
    # Verify NO new article added (count should be 1)
    with database.get_session() as session:
        articles = session.exec(database.select(models.Article).where(models.Article.feed_profile == feed_profile)).all()
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
    mock_feed_config.__name__ = 'meridiano.feeds.empty'
    
    with patch('meridiano.run_briefing.importlib.import_module', return_value=mock_feed_config):
        with patch.object(sys, 'argv', ['run_briefing.py', '--feed', 'empty', '--all']):
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

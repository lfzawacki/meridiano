# simple-meridian/database.py

import sqlite3
import json
from datetime import datetime, timedelta
import config

DB_FILE = config.DATABASE_FILE

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Articles Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        title TEXT,
        published_date DATETIME,
        feed_source TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        raw_content TEXT,
        processed_content TEXT, -- Summary or key points
        embedding TEXT,         -- Store embedding as JSON string
        processed_at DATETIME,
        cluster_id INTEGER       -- Optional: store cluster assignment
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_processed_at ON articles (processed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles (published_date)')


    # Briefs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        brief_markdown TEXT NOT NULL,
        contributing_article_ids TEXT -- Store list of article IDs as JSON string
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_briefs_generated_at ON briefs (generated_at)')

    conn.commit()
    conn.close()
    print("Database initialized.")

def get_all_articles(page=1, per_page=config.ARTICLES_PER_PAGE):
    """
    Fetches a specific page of articles for the list view, newest first.

    Args:
        page (int): The page number to retrieve (1-indexed).
        per_page (int): The number of articles per page.

    Returns:
        list: A list of article rows (dictionaries) for the requested page.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    cursor.execute('''
    SELECT id, title, url, feed_source, published_date
    FROM articles
    ORDER BY published_date DESC, fetched_at DESC
    LIMIT ? OFFSET ?
    ''', (per_page, offset))
    articles = cursor.fetchall()
    conn.close()
    return articles

def get_total_article_count():
    """Returns the total number of articles in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM articles')
    count = cursor.fetchone()[0] # fetchone() returns a tuple e.g., (52,)
    conn.close()
    return count

def add_article(url, title, published_date, feed_source, raw_content):
    """Adds a new article to the database if the URL is unique."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO articles (url, title, published_date, feed_source, raw_content, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (url, title, published_date, feed_source, raw_content, datetime.now()))
        conn.commit()
        print(f"Added article: {title}")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # print(f"Article already exists: {url}")
        return None # Indicate article already exists
    finally:
        conn.close()

def get_unprocessed_articles(limit=50):
    """Gets articles that haven't been processed yet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, url, raw_content FROM articles
    WHERE processed_at IS NULL AND raw_content IS NOT NULL AND raw_content != ''
    ORDER BY fetched_at ASC
    LIMIT ?
    ''', (limit,))
    articles = cursor.fetchall()
    conn.close()
    return articles

def update_article_processing(article_id, processed_content, embedding):
    """Updates an article with its summary, embedding, and processed timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    embedding_json = json.dumps(embedding) if embedding else None
    cursor.execute('''
    UPDATE articles
    SET processed_content = ?, embedding = ?, processed_at = ?
    WHERE id = ?
    ''', (processed_content, embedding_json, datetime.now(), article_id))
    conn.commit()
    conn.close()

def get_articles_for_briefing(lookback_hours):
    """Gets recently processed articles with embeddings for briefing generation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
    cursor.execute('''
    SELECT id, processed_content, embedding FROM articles
    WHERE processed_at >= ? AND embedding IS NOT NULL
    ORDER BY processed_at DESC
    ''', (cutoff_time,))
    articles = cursor.fetchall()
    conn.close()
    return articles

def save_brief(brief_markdown, contributing_article_ids):
    """Saves the generated brief markdown and contributing article IDs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    ids_json = json.dumps(contributing_article_ids)
    cursor.execute('''
    INSERT INTO briefs (brief_markdown, contributing_article_ids, generated_at)
    VALUES (?, ?, ?)
    ''', (brief_markdown, ids_json, datetime.now()))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    print(f"Saved brief with ID: {last_id}")
    return last_id

def get_latest_brief():
    """Retrieves the most recently generated brief."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT brief_markdown, generated_at FROM briefs
    ORDER BY generated_at DESC
    LIMIT 1
    ''')
    brief = cursor.fetchone()
    conn.close()
    return brief

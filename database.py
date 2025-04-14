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
        impact_score INTEGER
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

    try:
        cursor.execute('ALTER TABLE articles ADD COLUMN impact_score INTEGER')
        conn.commit()
        print("Added 'impact_score' column to articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            pass # Column already exists, ignore
        else:
            raise e # Raise other operational errors

    conn.commit()
    conn.close()
    print("Database initialized.")

def get_unrated_articles(limit=50):
    """Gets processed articles that haven't been rated yet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Select articles that have processed_content but lack an impact_score
    cursor.execute('''
    SELECT id, title, processed_content FROM articles
    WHERE processed_content IS NOT NULL AND processed_content != ''
      AND processed_at IS NOT NULL
      AND impact_score IS NULL
    ORDER BY processed_at DESC
    LIMIT ?
    ''', (limit,))
    articles = cursor.fetchall()
    conn.close()
    return articles

def update_article_rating(article_id, impact_score):
    """Updates an article with its impact score."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE articles
    SET impact_score = ?
    WHERE id = ?
    ''', (impact_score, article_id))
    conn.commit()
    conn.close()

def get_article_by_id(article_id):
    """Retrieves all data for a specific article by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Select all relevant columns you might want to display
    cursor.execute('''
    SELECT id, url, title, published_date, feed_source, fetched_at,
           raw_content, processed_content, embedding, processed_at, cluster_id,
           impact_score
    FROM articles
    WHERE id = ?
    ''', (article_id,))
    article_data = cursor.fetchone() # Use fetchone as ID is unique
    conn.close()
    return article_data

def _build_article_filter_clause(start_date=None, end_date=None):
    """Helper to build WHERE clauses and params for date filtering."""
    where_clauses = []
    params = []

    if start_date:
        # Assuming start_date is a date object or ISO string 'YYYY-MM-DD'
        where_clauses.append("date(published_date) >= ?")
        params.append(str(start_date)) # Use date() function in SQL for comparison

    if end_date:
        # Assuming end_date is a date object or ISO string 'YYYY-MM-DD'
        # Filter includes the entire end_date day
        where_clauses.append("date(published_date) <= ?")
        params.append(str(end_date))

    where_string = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_string, params

def get_all_articles(page=1, per_page=config.ARTICLES_PER_PAGE,
                     sort_by='published_date', direction='desc',
                     start_date=None, end_date=None): # Added date filters
    """ Fetches a page of articles, allowing sorting and date filtering. """
    conn = get_db_connection()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    # Sorting logic (remains the same)
    allowed_sort_columns = {'published_date': 'published_date', 'impact_score': 'impact_score', 'fetched_at': 'fetched_at'}
    db_sort_column = allowed_sort_columns.get(sort_by, 'published_date')
    db_direction = 'ASC' if direction.lower() == 'asc' else 'DESC'
    order_by_clause = f"ORDER BY {db_sort_column} {db_direction}, id DESC"

    # --- Date Filtering ---
    where_string, date_params = _build_article_filter_clause(start_date, end_date)
    # --- End Date Filtering ---

    sql = f'''
    SELECT id, title, url, feed_source, published_date, impact_score, processed_content
    FROM articles
    WHERE {where_string} -- Added WHERE clause
    {order_by_clause}
    LIMIT ? OFFSET ?
    '''

    # Combine date params with pagination params
    final_params = date_params + [per_page, offset]

    # print(f"DEBUG SQL: {sql}")
    # print(f"DEBUG PARAMS: {final_params}")
    cursor.execute(sql, final_params)
    articles = cursor.fetchall()
    conn.close()
    return articles

def get_total_article_count(start_date=None, end_date=None): # Added date filters
    """ Returns the total count of articles, optionally filtered by date. """
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Date Filtering ---
    where_string, date_params = _build_article_filter_clause(start_date, end_date)
    # --- End Date Filtering ---

    sql = f'SELECT COUNT(*) FROM articles WHERE {where_string}'

    # print(f"DEBUG COUNT SQL: {sql}")
    # print(f"DEBUG COUNT PARAMS: {date_params}")
    cursor.execute(sql, date_params)
    count = cursor.fetchone()[0]
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
    SELECT id, title, url, raw_content FROM articles
    WHERE processed_at IS NULL AND raw_content IS NOT NULL AND raw_content != ''
    ORDER BY fetched_at DESC
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

def get_all_briefs_metadata():
    """Retrieves ID and generation timestamp for all briefs, newest first."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, generated_at FROM briefs
    ORDER BY generated_at DESC
    ''')
    briefs_metadata = cursor.fetchall()
    conn.close()
    return briefs_metadata

def get_brief_by_id(brief_id):
    """Retrieves a specific brief's content and timestamp by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, brief_markdown, generated_at FROM briefs
    WHERE id = ?
    ''', (brief_id,))
    brief_data = cursor.fetchone()
    conn.close()
    return brief_data

# simple-meridian/database.py

import sqlite3
import json
from datetime import datetime, timedelta
import config_base as config

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
        image_url TEXT
        feed_profile TEXT NOT NULL DEFAULT 'default'
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_processed_at ON articles (processed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles (published_date)')

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN feed_profile TEXT NOT NULL DEFAULT 'default'")
        conn.commit()
        print("Added 'feed_profile' column to articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e): pass
        else: raise e
    # Add index
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_feed_profile ON articles (feed_profile)')

    # Briefs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        brief_markdown TEXT NOT NULL,
        contributing_article_ids TEXT -- Store list of article IDs as JSON string
        feed_profile TEXT NOT NULL DEFAULT 'default'
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_briefs_generated_at ON briefs (generated_at)')

    try:
        cursor.execute("ALTER TABLE briefs ADD COLUMN feed_profile TEXT NOT NULL DEFAULT 'default'")
        conn.commit()
        print("Added 'feed_profile' column to briefs table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e): pass
        else: raise e

    try:
        cursor.execute('ALTER TABLE articles ADD COLUMN impact_score INTEGER')
        conn.commit()
        print("Added 'impact_score' column to articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            pass # Column already exists, ignore
        else:
            raise e # Raise other operational errors

    try:
        cursor.execute('ALTER TABLE articles ADD COLUMN image_url TEXT')
        conn.commit()
        print("Added 'image_url' column to articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e): pass # Column already exists
        else: raise e

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
    cursor.execute('''
    SELECT id, url, title, published_date, feed_source, fetched_at,
           raw_content, processed_content, embedding, processed_at, cluster_id,
           impact_score, image_url -- Added image_url
    FROM articles
    WHERE id = ?
    ''', (article_id,))
    article_data = cursor.fetchone()
    conn.close()
    return article_data

def _build_article_filter_clause(start_date=None, end_date=None, feed_profile=None, search_term=None): # Added search_term
    """Helper to build WHERE clauses including date, profile, and search filters."""
    where_clauses = []
    params = []

    # Date filters
    if start_date:
        where_clauses.append("date(published_date) >= ?")
        params.append(str(start_date))
    if end_date:
        where_clauses.append("date(published_date) <= ?")
        params.append(str(end_date))

    # Profile filter
    if feed_profile: # Filter by profile if provided
        where_clauses.append("feed_profile = ?")
        params.append(feed_profile)

    # Search Filter
    if search_term:
        # Add clauses for title OR raw_content LIKE search_term
        # Use parentheses for correct OR precedence
        where_clauses.append("(title LIKE ? OR raw_content LIKE ?)")
        # Add the search term twice to the params list, with wildcards
        like_pattern = f"%{search_term}%"
        params.append(like_pattern)
        params.append(like_pattern)

    where_string = " AND ".join(where_clauses) if where_clauses else "1=1" # 1=1 ensures valid SQL if no filters
    return where_string, params

def get_all_articles(page=1, per_page=25,
                     sort_by='published_date', direction='desc',
                     start_date=None, end_date=None, feed_profile=None, search_term=None): # Added search_term
    """ Fetches articles, allowing sorting, date, profile, and search filtering. """
    conn = get_db_connection()
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    allowed_sort_columns = {'published_date': 'published_date', 'impact_score': 'impact_score', 'fetched_at': 'fetched_at'}
    db_sort_column = allowed_sort_columns.get(sort_by, 'published_date')
    db_direction = 'ASC' if direction.lower() == 'asc' else 'DESC'
    order_by_clause = f"ORDER BY {db_sort_column} {db_direction}, id DESC"

    where_string, filter_params = _build_article_filter_clause(start_date, end_date, feed_profile, search_term)

    sql = f'''
    SELECT id, title, url, feed_source, published_date, impact_score,
    processed_content, image_url, feed_profile
    FROM articles
    WHERE {where_string}
    {order_by_clause}
    LIMIT ? OFFSET ?
    '''
    final_params = filter_params + [per_page, offset]
    cursor.execute(sql, final_params)
    articles = cursor.fetchall()
    conn.close()
    return articles

def get_total_article_count(start_date=None, end_date=None, feed_profile=None, search_term=None): # Added search_term
    """ Returns total count of articles, optionally filtered by date, profile, and search. """
    conn = get_db_connection()
    cursor = conn.cursor()
    where_string, filter_params = _build_article_filter_clause(start_date, end_date, feed_profile, search_term)
    sql = f'SELECT COUNT(*) FROM articles WHERE {where_string}'
    cursor.execute(sql, filter_params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_article(url, title, published_date, feed_source, raw_content, feed_profile, image_url=None): # Added image_url param
    """Adds a new article with optional image URL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO articles (url, title, published_date, feed_source, raw_content, fetched_at, image_url, feed_profile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (url, title, published_date, feed_source, raw_content, datetime.now(), image_url, feed_profile))
        conn.commit()
        print(f"Added article [{feed_profile}]: {title}")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
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

def get_articles_for_briefing(lookback_hours, feed_profile):
    """Gets recently processed articles *for a specific feed profile*."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
    cursor.execute('''
    SELECT id, processed_content, embedding FROM articles
    WHERE processed_at >= ? AND embedding IS NOT NULL
      AND feed_profile = ?  -- *** Filter by profile ***
    ORDER BY processed_at DESC
    ''', (cutoff_time, feed_profile))
    articles = cursor.fetchall()
    conn.close()
    return articles

def save_brief(brief_markdown, contributing_article_ids, feed_profile): # Added feed_profile
    """Saves the generated brief including its feed profile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    ids_json = json.dumps(contributing_article_ids)
    cursor.execute('''
    INSERT INTO briefs (brief_markdown, contributing_article_ids, generated_at, feed_profile)
    VALUES (?, ?, ?, ?)
    ''', (brief_markdown, ids_json, datetime.now(), feed_profile)) # Added feed_profile
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    print(f"Saved brief [{feed_profile}] with ID: {last_id}")
    return last_id

def get_all_briefs_metadata(feed_profile=None): # Added feed_profile filter
    """Retrieves ID, timestamp, and profile for briefs, newest first, optionally filtered."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = '''
    SELECT id, generated_at, feed_profile FROM briefs
    '''
    params = []
    if feed_profile:
        sql += " WHERE feed_profile = ?"
        params.append(feed_profile)
    sql += " ORDER BY generated_at DESC"

    cursor.execute(sql, params)
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

def get_distinct_feed_profiles(table='articles'):
    """Gets a list of distinct feed_profile values from a table."""
    if table not in ['articles', 'briefs']:
        raise ValueError("Invalid table name for distinct profiles.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT DISTINCT feed_profile FROM {table} ORDER BY feed_profile')
    profiles = [row['feed_profile'] for row in cursor.fetchall()]
    conn.close()
    return profiles

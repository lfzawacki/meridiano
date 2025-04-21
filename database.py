# simple-meridian/database.py

import sqlite3
import json
from datetime import datetime, timedelta
import config_base as config

DB_FILE = config.DATABASE_FILE
ARTICLES_PER_PAGE_DEFAULT = 25

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    conn.execute('PRAGMA foreign_keys = ON')

    # Articles Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, /* id is alias for rowid */
        url TEXT UNIQUE NOT NULL,
        title TEXT,
        published_date DATETIME,
        feed_source TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        raw_content TEXT,
        processed_content TEXT,
        embedding TEXT,
        processed_at DATETIME,
        cluster_id INTEGER,
        impact_score INTEGER,
        image_url TEXT,
        feed_profile TEXT NOT NULL DEFAULT 'default'
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_processed_at ON articles (processed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles (published_date)')

   # --- FTS5 Virtual Table ---
    # Create the virtual table to index title and raw_content from articles
    # content='' means it doesn't store the content itself, only index
    # content_rowid='id' links the FTS rowid to the articles table id column
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        title,
        raw_content,
        content='articles',
        content_rowid='id'
    )
    ''')

    # --- Triggers to keep FTS table synchronized ---
    # After inserting into articles, insert into articles_fts
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts (rowid, title, raw_content)
        VALUES (new.id, new.title, new.raw_content);
    END;
    ''')

    # Before deleting from articles, delete from articles_fts
    # Need old.id to identify the row in articles_fts
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS articles_ad BEFORE DELETE ON articles BEGIN
        DELETE FROM articles_fts WHERE rowid=old.id;
    END;
    ''')

    # After updating articles, update articles_fts
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
        UPDATE articles_fts SET title=new.title, raw_content=new.raw_content
        WHERE rowid=old.id;
    END;
    ''')
    # --- End FTS Setup ---

    # Briefs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        brief_markdown TEXT NOT NULL,
        contributing_article_ids TEXT,
        feed_profile TEXT NOT NULL DEFAULT 'default'
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_briefs_generated_at ON briefs (generated_at)')

    conn.commit()
    conn.close()
    print("Database initialized.")

def get_unrated_articles(feed_profile, limit=50):
    """Gets processed articles that haven't been rated yet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Select articles that have processed_content but lack an impact_score
    cursor.execute('''
    SELECT id, title, processed_content FROM articles
    WHERE processed_content IS NOT NULL AND processed_content != ''
      AND processed_at IS NOT NULL
      AND impact_score IS NULL
      AND feed_profile = ?
    ORDER BY processed_at DESC
    LIMIT ?
    ''', (feed_profile, limit,))
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

# --- Retrieval Functions ---
# Helper no longer needs to build search clause, just filters
def _build_article_filter_clause(start_date=None, end_date=None, feed_profile=None):
    """Helper for date and profile WHERE clauses (search handled separately)."""
    where_clauses = []
    params = []
    if start_date:
        # Use date() without table qualifier inside the function
        where_clauses.append("date(published_date) >= ?")
        params.append(str(start_date))
    if end_date:
        # Use date() without table qualifier inside the function
        where_clauses.append("date(published_date) <= ?")
        params.append(str(end_date))
    if feed_profile:
        # Qualify this one as it's a direct column comparison
        where_clauses.append("articles.feed_profile = ?")
        params.append(feed_profile)

    where_string = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_string, params

def get_all_articles(page=1, per_page=ARTICLES_PER_PAGE_DEFAULT,
                     sort_by='published_date', direction='desc',
                     start_date=None, end_date=None, feed_profile=None, search_term=None):
    """
    Fetches articles, using FTS5 MATCH for searching and bm25() for relevance sorting
    when a search term is provided. Otherwise, uses standard column sorting.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    # --- Build Base WHERE clause (excluding search, using qualified names) ---
    where_string_base, filter_params = _build_article_filter_clause(start_date, end_date, feed_profile)

    # --- Determine Primary Sort Key (Always needed) ---
    allowed_sort_columns = {
        'published_date': 'articles.published_date',
        'impact_score': 'articles.impact_score',
        'fetched_at': 'articles.fetched_at'
    }
    db_sort_column = allowed_sort_columns.get(sort_by, 'articles.published_date') # Default sort
    db_direction = 'ASC' if direction.lower() == 'asc' else 'DESC'
    # --- End Primary Sort Determination ---

    sql = ""
    final_params = []
    order_by_clause = "" # Initialize order by

    # --- Determine Query Structure and Sorting based on Search ---
    if search_term:
        # --- SEARCH ACTIVE: Use JOIN and COMBINED sorting ---
        print("INFO: Search term active, sorting by user choice THEN relevance.")

        # Add FTS MATCH condition to the base WHERE clause
        where_string_fts = where_string_base + " AND articles_fts MATCH ?"
        search_params = [search_term] # Keep search param separate for clarity

        # *** MODIFIED ORDER BY ***
        # 1st: User selected column (date/impact) + direction
        # 2nd: Relevance score (lower bm25 is better -> ASC)
        # 3rd: Final deterministic tie-breaker
        order_by_clause = f"ORDER BY {db_sort_column} {db_direction}, bm25(articles_fts) ASC, articles.id DESC"
        # *** END MODIFIED ORDER BY ***

        # Construct the JOIN query (structure remains the same)
        sql = f'''
        SELECT articles.id, articles.title, articles.url, articles.feed_source,
               articles.published_date, articles.impact_score, articles.image_url,
               articles.feed_profile, articles.processed_content
        FROM articles
        JOIN articles_fts ON articles.id = articles_fts.rowid
        WHERE {where_string_fts}
        {order_by_clause}
        LIMIT ? OFFSET ?
        '''
        # Params order: filter_params (date, profile), search_params, pagination_params
        final_params = filter_params + search_params + [per_page, offset]

    else:
        # --- NO SEARCH: Use standard query and user-selected sorting ---
        print("INFO: No search term, using standard sorting.")

        # Standard ORDER BY (as before)
        order_by_clause = f"ORDER BY {db_sort_column} {db_direction}, articles.id DESC"

        # Construct the standard query (no JOIN needed)
        sql = f'''
        SELECT articles.id, articles.title, articles.url, articles.feed_source,
               articles.published_date, articles.impact_score, articles.image_url,
               articles.feed_profile, articles.processed_content
        FROM articles
        WHERE {where_string_base}
        {order_by_clause}
        LIMIT ? OFFSET ?
        '''
        # Params order: filter_params (date, profile), pagination_params
        final_params = filter_params + [per_page, offset]
    # --- End Conditional Query Building ---

    # print(f"DEBUG SQL: {sql}")
    # print(f"DEBUG PARAMS: {final_params}")
    try:
        cursor.execute(sql, final_params)
        articles = cursor.fetchall()
    except Exception as e:
        print(f"ERROR executing article query: {e}")
        print(f"SQL: {sql}")
        print(f"PARAMS: {final_params}")
        articles = [] # Return empty list on error
    finally:
        conn.close()

    return articles

def get_total_article_count(start_date=None, end_date=None, feed_profile=None, search_term=None):
    """
    Returns total count of articles, using FTS5 MATCH for searching via JOIN.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build base WHERE clause for non-FTS columns (date, profile) on articles table
    where_string_base, filter_params = _build_article_filter_clause(start_date, end_date, feed_profile)

    sql = ""
    final_params = []

    if search_term:
        # --- SEARCH ACTIVE: Use JOIN query for counting ---
        print("INFO (Count): Search term active, using FTS JOIN for count.")

        # Append the MATCH condition, applied to the joined fts table
        # Make sure the base string correctly references articles.column if needed
        where_string_fts = where_string_base + " AND articles_fts MATCH ?"

        # Construct the JOIN query for counting
        # We count articles.id to be specific, though COUNT(*) would likely work too
        sql = f'''
        SELECT COUNT(articles.id)
        FROM articles
        JOIN articles_fts ON articles.id = articles_fts.rowid
        WHERE {where_string_fts}
        '''
        # Params order: filter_params (date, profile) + search_term
        final_params = filter_params + [search_term]

    else:
        # --- NO SEARCH: Use standard count query ---
        print("INFO (Count): No search term, using standard count.")

        # Query only the articles table
        sql = f'SELECT COUNT(*) FROM articles WHERE {where_string_base}'
        # Params: filter_params only
        final_params = filter_params

    # --- Execute Query ---
    # print(f"DEBUG COUNT SQL: {sql}")
    # print(f"DEBUG COUNT PARAMS: {final_params}")
    try:
        cursor.execute(sql, final_params)
        count = cursor.fetchone()[0]
    except Exception as e:
        print(f"ERROR executing count query: {e}")
        print(f"SQL: {sql}")
        print(f"PARAMS: {final_params}")
        count = 0 # Return 0 on error to prevent further issues
    finally:
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

def get_unprocessed_articles(feed_profile, limit=50):
    """Gets articles that haven't been processed yet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, title, url, raw_content FROM articles
    WHERE processed_at IS NULL AND raw_content IS NOT NULL AND raw_content != ''
    AND feed_profile = ?
    ORDER BY fetched_at DESC
    LIMIT ?
    ''', (feed_profile, limit,))
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

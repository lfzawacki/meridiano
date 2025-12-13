"""
SQLModel database models for Meridiano application.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, text

from . import config_base as config


class Article(SQLModel, table=True):
    """Article model representing news articles in the database."""

    # Old SQLite schema for reference
    """
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
    );
    CREATE INDEX IF NOT EXISTS idx_articles_url ON articles (url);
    CREATE INDEX IF NOT EXISTS idx_articles_processed_at ON articles (processed_at);
    CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles (published_date);
    """

    __tablename__ = "articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: Optional[str] = None
    published_date: Optional[datetime] = None
    feed_source: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.now)
    raw_content: Optional[str] = None
    processed_content: Optional[str] = None
    embedding: Optional[str] = None  # JSON string
    processed_at: Optional[datetime] = Field(default=None, index=True)
    cluster_id: Optional[int] = None
    impact_score: Optional[int] = None
    image_url: Optional[str] = None
    feed_profile: str = Field(default="default", index=True)


class Brief(SQLModel, table=True):
    """Brief model representing generated news briefs."""

    # Old SQLite schema for reference
    """
    # Briefs Table
    CREATE TABLE IF NOT EXISTS briefs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        brief_markdown TEXT NOT NULL,
        contributing_article_ids TEXT,
        feed_profile TEXT NOT NULL DEFAULT 'default'
    )
    """

    __tablename__ = "briefs"

    id: Optional[int] = Field(default=None, primary_key=True)
    generated_at: datetime = Field(default_factory=datetime.now)
    brief_markdown: str
    contributing_article_ids: Optional[str] = None  # JSON string
    feed_profile: str = Field(default="default", index=True)


# Database engine and session management
engine = create_engine(config.DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables if they don't exist."""
    SQLModel.metadata.create_all(engine)

    # Old SQLite schema for reference (replaced by to_tsvector in PostgreSQL)
    """
    # --- FTS5 Virtual Table ---
    # Create the virtual table to index title and raw_content from articles
    # content='' means it doesn't store the content itself, only index
    # content_rowid='id' links the FTS rowid to the articles table id column
    CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        title,
        raw_content,
        content='articles',
        content_rowid='id'
    )

    # --- Triggers to keep FTS table synchronized ---
    # After inserting into articles, insert into articles_fts
    CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
        INSERT INTO articles_fts (rowid, title, raw_content)
        VALUES (new.id, new.title, new.raw_content);
    END;

    # Before deleting from articles, delete from articles_fts
    # Need old.id to identify the row in articles_fts
    CREATE TRIGGER IF NOT EXISTS articles_ad BEFORE DELETE ON articles BEGIN
        DELETE FROM articles_fts WHERE rowid=old.id;
    END;

    # After updating articles, update articles_fts
    CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
        UPDATE articles_fts SET title=new.title, raw_content=new.raw_content
        WHERE rowid=old.id;
    END;
    # --- End FTS Setup ---
    """

    # For PostgreSQL, create full-text search index
    if "postgresql" in config.DATABASE_URL.lower():
        with Session(engine) as session:
            try:
                # Create full-text search index
                session.exec(
                    text("""
                    CREATE INDEX IF NOT EXISTS idx_articles_fts
                    ON articles USING GIN(
                        to_tsvector('english',
                            coalesce(title, '') || ' ' || coalesce(raw_content, '')
                        )
                    )
                """)
                )
                session.commit()
                print("PostgreSQL full-text search index created")
            except Exception as e:
                print(f"Note: FTS index creation: {e}")
                session.rollback()


def get_session():
    """Get a database session."""
    return Session(engine)


def init_db():
    """Initialize the database - create all tables."""
    create_db_and_tables()
    print("Database initialized with SQLModel.")


if __name__ == "__main__":
    init_db()

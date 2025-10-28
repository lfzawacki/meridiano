"""
Database operations using SQLModel for the Meridiano application.
This replaces the SQLite-based database.py with modern SQLModel operations.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import and_, asc, desc, func, or_, select
from sqlalchemy import text

import config_base as config
from models import Article, Brief, get_session

ARTICLES_PER_PAGE_DEFAULT = 25


def get_db_connection():
    """Returns a new database session (replaces SQLite connection)"""
    return get_session()


def init_db():
    """Initialize the database - create all tables"""
    from models import init_db as model_init_db

    model_init_db()


def get_unrated_articles(
    feed_profile: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Gets processed articles that haven't been rated yet."""
    with get_session() as session:
        statement = (
            select(Article)
            .where(
                and_(
                    Article.processed_content.is_not(None),
                    Article.processed_content != "",
                    Article.processed_at.is_not(None),
                    Article.impact_score.is_(None),
                    Article.feed_profile == feed_profile,
                )
            )
            .order_by(desc(Article.processed_at))
            .limit(limit)
        )

        articles = session.exec(statement).all()
        return [_article_to_dict(article) for article in articles]


def update_article_rating(article_id: int, impact_score: int) -> None:
    """Updates an article with its impact score."""
    with get_session() as session:
        statement = select(Article).where(Article.id == article_id)
        article = session.exec(statement).first()
        if article:
            article.impact_score = impact_score
            session.add(article)
            session.commit()


def get_article_by_id(article_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves all data for a specific article by its ID."""
    with get_session() as session:
        statement = select(Article).where(Article.id == article_id)
        article = session.exec(statement).first()
        return _article_to_dict(article) if article else None


def _article_to_dict(article: Article) -> Dict[str, Any]:
    """Convert Article model to dictionary for compatibility with existing code."""
    if not article:
        return None

    return article.model_dump(
        include={
            "id",
            "url",
            "title",
            "published_date",
            "feed_source",
            "fetched_at",
            "raw_content",
            "processed_content",
            "embedding",
            "processed_at",
            "cluster_id",
            "impact_score",
            "image_url",
            "feed_profile",
        }
    )


def _brief_to_dict(brief: Brief) -> Dict[str, Any]:
    """Convert Brief model to dictionary for compatibility with existing code."""
    if not brief:
        return None

    return brief.model_dump(
        include={
            "id",
            "generated_at",
            "brief_markdown",
            "contributing_article_ids",
            "feed_profile",
        }
    )

def _build_article_filters(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    feed_profile: Optional[str] = None,
):
    """Helper for building filter conditions for articles."""
    filters = []

    if start_date:
        filters.append(func.date(Article.published_date) >= start_date)
    if end_date:
        filters.append(func.date(Article.published_date) <= end_date)
    if feed_profile:
        filters.append(Article.feed_profile == feed_profile)

    return filters


def get_all_articles(
    page: int = 1,
    per_page: int = ARTICLES_PER_PAGE_DEFAULT,
    sort_by: str = "published_date",
    direction: str = "desc",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    feed_profile: Optional[str] = None,
    search_term: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches articles with filtering, sorting, and full-text search.
    Uses PostgreSQL full-text search when available, falls back to LIKE search.
    """
    with get_session() as session:
        # Start with base query
        statement = select(Article)

        # Apply basic filters
        filters = _build_article_filters(start_date, end_date, feed_profile)
        if filters:
            statement = statement.where(and_(*filters))

        # Apply search if provided
        if search_term:
            if "postgresql" in config.DATABASE_URL.lower():
                # PostgreSQL full-text search
                search_vector = func.to_tsvector(
                    "english",
                    func.coalesce(Article.title, "")
                    + " "
                    + func.coalesce(Article.raw_content, ""),
                )
                # Use SQLAlchemy's match with a plain string and specify the Postgres
                # text search configuration to avoid nesting plainto_tsquery calls.
                statement = statement.where(
                    search_vector.match(search_term, postgresql_regconfig='english')
                )
            else:
                # Fallback to LIKE search for SQLite
                search_filter = or_(
                    Article.title.ilike(f"%{search_term}%"),
                    Article.raw_content.ilike(f"%{search_term}%"),
                )
                statement = statement.where(search_filter)

        # Apply sorting
        sort_columns = {
            "published_date": Article.published_date,
            "impact_score": Article.impact_score,
            "fetched_at": Article.fetched_at,
        }

        sort_column = sort_columns.get(sort_by, Article.published_date)
        if direction.lower() == "asc":
            statement = statement.order_by(asc(sort_column), desc(Article.id))
        else:
            statement = statement.order_by(desc(sort_column), desc(Article.id))

        # Apply pagination
        offset = (page - 1) * per_page
        statement = statement.offset(offset).limit(per_page)

        articles = session.exec(statement).all()
        return [_article_to_dict(article) for article in articles]


def get_total_article_count(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    feed_profile: Optional[str] = None,
    search_term: Optional[str] = None,
) -> int:
    """Returns total count of articles with optional filtering and search."""
    with get_session() as session:
        # Start with base query
        statement = select(func.count(Article.id))

        # Apply basic filters
        filters = _build_article_filters(start_date, end_date, feed_profile)
        if filters:
            statement = statement.where(and_(*filters))

        # Apply search if provided
        if search_term:
            if "postgresql" in config.DATABASE_URL.lower():
                # PostgreSQL full-text search
                search_vector = func.to_tsvector(
                    "english",
                    func.coalesce(Article.title, "")
                    + " "
                    + func.coalesce(Article.raw_content, ""),
                )
                # Use SQLAlchemy's match with a plain string and specify the Postgres
                # text search configuration to avoid nesting plainto_tsquery calls.
                statement = statement.where(
                    search_vector.match(search_term, postgresql_regconfig='english')
                )
            else:
                # Fallback to LIKE search
                search_filter = or_(
                    Article.title.ilike(f"%{search_term}%"),
                    Article.raw_content.ilike(f"%{search_term}%"),
                )
                statement = statement.where(search_filter)

        return session.exec(statement).one()


def add_article(
    url: str,
    title: str,
    published_date: datetime,
    feed_source: str,
    raw_content: str,
    feed_profile: str,
    image_url: Optional[str] = None,
) -> Optional[int]:
    """Adds a new article with optional image URL."""
    with get_session() as session:
        try:
            # Ensure Postgres sequence is in sync to avoid duplicate primary key errors
            if "postgresql" in config.DATABASE_URL.lower():
                try:
                    # Sync the sequence to the current max(id) so nextval() will produce a fresh value.
                    session.exec(
                        text(
                            "SELECT setval(pg_get_serial_sequence('articles','id'), COALESCE((SELECT MAX(id) FROM articles), 0))"
                        )
                    )
                except Exception:
                    # If sequence sync fails, proceed and let the DB raise a meaningful error if any.
                    pass

            article = Article(
                url=url,
                title=title,
                published_date=published_date,
                feed_source=feed_source,
                raw_content=raw_content,
                image_url=image_url,
                feed_profile=feed_profile,
                fetched_at=datetime.now(),
            )
            session.add(article)
            session.commit()
            session.refresh(article)  # Get the ID
            print(f"Added article [{feed_profile}]: {title}")
            return article.id
        except IntegrityError:
            session.rollback()
            return None


def get_unprocessed_articles(
    feed_profile: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Gets articles that haven't been processed yet."""
    with get_session() as session:
        statement = (
            select(Article)
            .where(
                and_(
                    Article.processed_at.is_(None),
                    Article.raw_content.is_not(None),
                    Article.raw_content != "",
                    Article.feed_profile == feed_profile,
                )
            )
            .order_by(desc(Article.fetched_at))
            .limit(limit)
        )

        articles = session.exec(statement).all()
        return [_article_to_dict(article) for article in articles]


def update_article_processing(
    article_id: int, processed_content: str, embedding: Optional[List[float]]
) -> None:
    """Updates an article with its summary, embedding, and processed timestamp."""
    with get_session() as session:
        statement = select(Article).where(Article.id == article_id)
        article = session.exec(statement).first()
        if article:
            article.processed_content = processed_content
            article.embedding = json.dumps(embedding) if embedding else None
            article.processed_at = datetime.now()
            session.add(article)
            session.commit()


def get_articles_for_briefing(
    lookback_hours: int, feed_profile: str
) -> List[Dict[str, Any]]:
    """Gets recently processed articles for a specific feed profile."""
    cutoff_time = datetime.now() - timedelta(hours=lookback_hours)

    with get_session() as session:
        statement = (
            select(Article)
            .where(
                and_(
                    Article.processed_at >= cutoff_time,
                    Article.embedding.is_not(None),
                    Article.feed_profile == feed_profile,
                )
            )
            .order_by(desc(Article.processed_at))
        )

        articles = session.exec(statement).all()
        return [_article_to_dict(article) for article in articles]


def save_brief(
    brief_markdown: str, contributing_article_ids: List[int], feed_profile: str
) -> int:
    """Saves the generated brief including its feed profile."""
    with get_session() as session:
        ids_json = json.dumps(contributing_article_ids)
        brief = Brief(
            brief_markdown=brief_markdown,
            contributing_article_ids=ids_json,
            feed_profile=feed_profile,
            generated_at=datetime.now(),
        )
        session.add(brief)
        session.commit()
        session.refresh(brief)  # Get the ID
        print(f"Saved brief [{feed_profile}] with ID: {brief.id}")
        return brief.id


def get_all_briefs_metadata(
    feed_profile: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves ID, timestamp, and profile for briefs, newest first, optionally filtered."""
    with get_session() as session:
        statement = select(Brief)

        if feed_profile:
            statement = statement.where(Brief.feed_profile == feed_profile)

        statement = statement.order_by(desc(Brief.generated_at))
        briefs = session.exec(statement).all()

        return [_brief_to_dict(brief) for brief in briefs]


def get_brief_by_id(brief_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a specific brief's content and timestamp by its ID."""
    with get_session() as session:
        statement = select(Brief).where(Brief.id == brief_id)
        brief = session.exec(statement).first()
        return _brief_to_dict(brief) if brief else None


def get_distinct_feed_profiles(table: str = "articles") -> List[str]:
    """Gets a list of distinct feed_profile values from a table."""
    if table not in ["articles", "briefs"]:
        raise ValueError("Invalid table name for distinct profiles.")

    with get_session() as session:
        if table == "articles":
            statement = (
                select(Article.feed_profile)
                .distinct()
                .order_by(Article.feed_profile)
            )
            result = session.exec(statement).all()
        else:  # table == 'briefs'
            statement = (
                select(Brief.feed_profile)
                .distinct()
                .order_by(Brief.feed_profile)
            )
            result = session.exec(statement).all()

        return list(result)

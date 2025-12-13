#!/usr/bin/env python3
"""
Migration utility for Meridiano: SQLite to PostgreSQL with SQLModel
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from sqlmodel import select

from . import config_base as config
from .models import Article, Brief, create_db_and_tables, get_session


def migrate_from_sqlite():
    """
    Migrate data from SQLite database to the configured database (PostgreSQL/SQLite)
    """
    # Check if SQLite database exists
    sqlite_db_path = config.DATABASE_FILE
    if not Path(sqlite_db_path).exists():
        print(f"[ERROR] SQLite database not found at {sqlite_db_path}")
        return False

    print(f"[INFO] Migrating from SQLite database: {sqlite_db_path}")
    print(f"[INFO] Target database: {config.DATABASE_URL}")

    # Create new database tables
    create_db_and_tables()

    # SQLite connection
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        # Migrate Articles
        print("\n[INFO] Migrating articles...")
        cursor = sqlite_conn.execute("SELECT * FROM articles")
        articles_migrated = 0
        articles_skipped = 0

        with get_session() as session:
            for row in cursor:
                row = dict(row)
                # Check if article already exists
                existing = session.get(Article, row["id"])
                if existing:
                    print(
                        f"[SKIP] Article already exists (ID {row['id']}): {row['title']}"
                    )
                    articles_skipped += 1
                    continue

                try:
                    article = Article(
                        id=row["id"],  # Preserve original ID
                        url=row["url"],
                        title=row["title"],
                        published_date=datetime.fromisoformat(
                            row["published_date"]
                        )
                        if row["published_date"]
                        else None,
                        feed_source=row["feed_source"],
                        fetched_at=datetime.fromisoformat(row["fetched_at"])
                        if row["fetched_at"]
                        else datetime.now(),
                        raw_content=row["raw_content"],
                        processed_content=row["processed_content"],
                        embedding=row["embedding"],
                        processed_at=datetime.fromisoformat(
                            row["processed_at"]
                        )
                        if row["processed_at"]
                        else None,
                        cluster_id=row["cluster_id"],
                        impact_score=row["impact_score"],
                        image_url=row.get("image_url"),
                        feed_profile=row.get("feed_profile", "default"),
                    )
                    session.add(article)
                    articles_migrated += 1

                    if articles_migrated % 100 == 0:
                        print(
                            f"   [INFO] Migrated {articles_migrated} articles..."
                        )

                except Exception as e:
                    print(f"[ERROR] Error migrating article {row['id']}: {e}")

            session.commit()

        print(
            f"[DONE] Articles migration completed: {articles_migrated} migrated, {articles_skipped} skipped"
        )

        # Migrate Briefs
        print("\n[INFO] Migrating briefs...")
        cursor = sqlite_conn.execute("SELECT * FROM briefs")
        briefs_migrated = 0
        briefs_skipped = 0

        with get_session() as session:
            for row in cursor:
                row = dict(row)
                # Check if brief already exists
                existing = session.get(Brief, row["id"])
                if existing:
                    print(f"[SKIP] Brief already exists (ID {row['id']})")
                    briefs_skipped += 1
                    continue

                try:
                    brief = Brief(
                        id=row["id"],  # Preserve original ID
                        generated_at=datetime.fromisoformat(
                            row["generated_at"]
                        )
                        if row["generated_at"]
                        else datetime.now(),
                        brief_markdown=row["brief_markdown"],
                        contributing_article_ids=row[
                            "contributing_article_ids"
                        ],
                        feed_profile=row.get("feed_profile", "default"),
                    )
                    session.add(brief)
                    briefs_migrated += 1

                except Exception as e:
                    print(f"[ERROR] Error migrating brief {row['id']}: {e}")

            session.commit()

        print(
            f"[DONE] Briefs migration completed: {briefs_migrated} migrated, {briefs_skipped} skipped"
        )

        print("\n[SUCCESS] Migration completed successfully!")
        print(
            f"   [INFO] Articles: {articles_migrated} migrated, {articles_skipped} skipped"
        )
        print(
            f"   [INFO] Briefs: {briefs_migrated} migrated, {briefs_skipped} skipped"
        )

        return True

    except Exception as e:
        print(f"[ERROR] Error during migration: {e}")
        return False
    finally:
        sqlite_conn.close()


def setup_postgresql_fts():
    """
    Set up PostgreSQL full-text search indexes (already handled in models.py)
    """
    if "postgresql" not in config.DATABASE_URL.lower():
        print("[WARN] Not using PostgreSQL, skipping FTS setup")
        return

    print("[INFO] PostgreSQL full-text search is configured in models.py")
    return True


def verify_migration():
    """
    Verify the migration by checking record counts
    """
    print("\n[INFO] Verifying migration...")

    # Check SQLite counts
    sqlite_db_path = config.DATABASE_FILE
    if not Path(sqlite_db_path).exists():
        print("[ERROR] Original SQLite database not found for verification")
        return

    sqlite_conn = sqlite3.connect(sqlite_db_path)

    # Count SQLite records
    sqlite_articles = sqlite_conn.execute(
        "SELECT COUNT(*) FROM articles"
    ).fetchone()[0]
    sqlite_briefs = sqlite_conn.execute(
        "SELECT COUNT(*) FROM briefs"
    ).fetchone()[0]
    sqlite_conn.close()

    # Count new database records
    with get_session() as session:
        new_articles = len(session.exec(select(Article)).all())
        new_briefs = len(session.exec(select(Brief)).all())

    print("[INFO] Record counts:")
    print(f"   Articles: SQLite={sqlite_articles}, New DB={new_articles}")
    print(f"   Briefs: SQLite={sqlite_briefs}, New DB={new_briefs}")

    if sqlite_articles == new_articles and sqlite_briefs == new_briefs:
        print("[SUCCESS] Migration verification passed!")
        return True
    else:
        print("[WARN] Record count mismatch - please review migration")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrate.py [migrate|verify|setup_fts]")
        print("  migrate   - Migrate data from SQLite to configured database")
        print("  verify    - Verify migration by comparing record counts")
        print("  setup_fts - Set up full-text search (PostgreSQL)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "migrate":
        migrate_from_sqlite()
    elif command == "verify":
        verify_migration()
    elif command == "setup_fts":
        setup_postgresql_fts()
    else:
        print(
            "[ERROR] Unknown command. Use 'migrate', 'verify', or 'setup_fts'"
        )

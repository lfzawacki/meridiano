# Changelog

## 0.0.1 [unreleased]

### Added

- RSS output feeds: every feed profile present in the database is served as an RSS 2.0 feed at `/<profile>.rss`
  (e.g. `/tech.rss`), exposing the AI summary, original link, publication date and impact score of each article
  so any RSS reader can consume Meridiano. `RSS_MAX_ITEMS` (default 50) and `RSS_BASE_URL` configure it.

### Fixed

- Fixed date filter type mismatch - updated database functions to accept `date` objects instead of strings
- Fixed database session management - switched to context manager pattern to prevent connection leaks
- Added validation for empty/invalid embedding responses to prevent clustering failures
- Improved rating parsing with regex to handle multi-line LLM responses
- Added logging for PostgreSQL sequence sync errors instead of silently ignoring them

### Changed

- Added logging infrastructure to `database.py`
- update session management in `app.py`
- enhancements in `run_briefing.py` parsing logic and error handling



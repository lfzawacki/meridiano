# Changelog

## 0.0.1 [unreleased]

### Added

- Full article view: the whole article, images included, is stored as sanitized HTML while scraping and shown in a collapsed "Full Article" section on the article page, with a button to fetch/refetch it
- `--fetch-full-content` (and `--retry-failed`) to backfill the full article for articles already in the database
- `--repair-encoding` (with `--dry-run`) to fix stored text saved with broken accents
- Collection reader (`/collection/<id>/read`): reads a collection's full articles one at a time, with prev/next and arrow-key navigation
- Paywall notice on full articles: pages marked subscriber-only (schema.org `isAccessibleForFree: false`) show a warning, and a stronger one when the text stops mid-sentence; `--check-paywall` and `--source` refetch articles stored before detection

### Fixed

- Pages served without a charset (e.g. Folha) were decoded as Latin-1, storing UTF-8 text as mojibake ("vegetaÃ§Ã£o")
- Full article extraction kept no images on sites that lazy-load them or wrap them in widget containers

- Fixed date filter type mismatch - updated database functions to accept `date` objects instead of strings
- Fixed database session management - switched to context manager pattern to prevent connection leaks
- Added validation for empty/invalid embedding responses to prevent clustering failures
- Improved rating parsing with regex to handle multi-line LLM responses
- Added logging for PostgreSQL sequence sync errors instead of silently ignoring them

### Changed

- Added logging infrastructure to `database.py`
- update session management in `app.py`
- enhancements in `run_briefing.py` parsing logic and error handling



# Changelog

## 0.0.1 [unreleased]

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



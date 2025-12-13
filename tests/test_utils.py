"""
Tests for utility functions.
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from meridiano.utils import format_datetime


class TestFormatDatetime:
    """Tests for datetime formatting."""

    def test_format_datetime_none(self):
        """Test formatting None value."""
        result = format_datetime(None)
        assert result == "N/A"

    def test_format_datetime_datetime_object(self):
        """Test formatting datetime object."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = format_datetime(dt)
        assert result == "2024-01-15 14:30"

    def test_format_datetime_datetime_custom_format(self):
        """Test formatting datetime with custom format."""
        dt = datetime(2024, 1, 15, 14, 30, 45)
        result = format_datetime(dt, "%Y-%m-%d")
        assert result == "2024-01-15"

    def test_format_datetime_string(self):
        """Test formatting ISO format string."""
        iso_string = "2024-01-15T14:30:45"
        result = format_datetime(iso_string)
        assert result == "2024-01-15 14:30"

    def test_format_datetime_invalid_string(self):
        """Test formatting invalid string (should return original)."""
        invalid_string = "not-a-date"
        result = format_datetime(invalid_string)
        assert result == invalid_string

    def test_format_datetime_empty_string(self):
        """Test formatting empty string."""
        result = format_datetime("")
        assert result == ""

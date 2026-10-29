"""
Unit tests for date and timezone handling.
"""
from datetime import datetime, timezone
import dateutil.parser
from app.utils.extractor import extract_deadline_details


def test_utc_timezone_awareness():
    text = "Submission deadline is 10 Nov 2026 at 14:00"
    res = extract_deadline_details(text)
    assert res.deadline is not None
    assert res.deadline.tzinfo is not None
    # Compare with UTC timezone
    utc_dt = res.deadline.astimezone(timezone.utc)
    assert utc_dt.hour == 14
    assert utc_dt.day == 10


def test_date_header_parsing_with_offsets():
    raw_date_header = "Tue, 29 Oct 2026 14:20:00 +0530"
    parsed = dateutil.parser.parse(raw_date_header)
    utc_converted = parsed.astimezone(timezone.utc)
    assert utc_converted.hour == 8
    assert utc_converted.minute == 50


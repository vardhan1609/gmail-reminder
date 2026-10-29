"""
Unit tests for deadline extraction: confidence scores, ambiguity detection, cue matching.
"""
from datetime import datetime, timezone
from app.utils.extractor import extract_deadline_details, extract_deadline


def test_extract_explicit_deadline():
    text = "The submission deadline is 25 Dec 2026 at 5:00 PM. No extensions will be given."
    ref_time = datetime(2026, 10, 1, tzinfo=timezone.utc)
    res = extract_deadline_details(text, reference_time=ref_time)

    assert res.deadline is not None
    assert res.deadline.year == 2026
    assert res.deadline.month == 12
    assert res.deadline.day == 25
    assert res.deadline.hour == 17
    assert res.confidence_score >= 0.90
    assert not res.is_ambiguous
    assert res.date_type == "submission_deadline"


def test_extract_relative_deadline():
    ref_time = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    text = "Your project report is due tomorrow."
    res = extract_deadline_details(text, reference_time=ref_time)

    assert res.deadline is not None
    assert res.deadline.day == 11
    assert res.confidence_score >= 0.80


def test_ambiguous_date_detected():
    # Date without year or ambiguous format
    text = "The review meeting is scheduled on 04/05."
    res = extract_deadline_details(text)
    assert res.is_ambiguous or res.confidence_score < 0.70


def test_no_deadline_present():
    text = "Hello team, hope you are having a wonderful productive week."
    res = extract_deadline_details(text)
    assert res.deadline is None
    assert res.confidence_score == 0.0
    assert res.date_type == "none"


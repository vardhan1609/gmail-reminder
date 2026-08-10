"""
Regex/heuristic based deadline extraction. This is the fast, free, offline
first pass. If it finds nothing (or the caller wants higher confidence),
`app/services/deadline_extractor.py` falls back to an LLM.
"""
import re
from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Phrases that usually precede an actual deadline (used to find the right
# spot in a long email body rather than grabbing the first date mentioned,
# e.g. the "Date:" header of the email itself).
DEADLINE_CUES = [
    r"deadline",
    r"due date",
    r"due by",
    r"due on",
    r"last date",
    r"submit(?:ted|ion)? by",
    r"submission date",
    r"before",
    r"on or before",
    r"closes on",
    r"closing date",
]

DATE_PATTERNS = [
    # 5 Aug 2026 / 5th August 2026
    r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}",
    # August 5, 2026 / Aug 5 2026
    r"[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}",
    # 05/08/2026, 05-08-2026, 2026-08-05
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    r"\d{4}-\d{2}-\d{2}",
]

TIME_PATTERN = r"\d{1,2}(?::\d{2})?\s?(?:AM|PM|am|pm)|\d{1,2}:\d{2}\s?(?:hrs)?"

_CUE_RE = re.compile("(" + "|".join(DEADLINE_CUES) + ")", re.IGNORECASE)
_DATE_RE = re.compile("(" + "|".join(DATE_PATTERNS) + ")")
_TIME_RE = re.compile(TIME_PATTERN)

# Simple relative-date phrases as a last resort
_RELATIVE_MAP = {
    "today": lambda now: now,
    "tomorrow": lambda now: now + timedelta(days=1),
    "end of day": lambda now: now.replace(hour=23, minute=59),
    "end of week": lambda now: now + relativedelta(weekday=4),  # next/this Friday
    "next week": lambda now: now + timedelta(weeks=1),
}


def extract_deadline(text: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
    """
    Best-effort extraction of a single deadline datetime from `text`.
    Returns None if nothing confident was found (caller should try LLM
    fallback or skip reminder scheduling).
    """
    reference_time = reference_time or datetime.utcnow()
    if not text:
        return None

    text = text.replace("\n", " ")

    # 1. Look for an explicit date near a deadline cue word (search a window
    #    of ~120 chars after the cue, which comfortably covers "Deadline: 5
    #    Aug 2026, 11:59 PM").
    for cue_match in _CUE_RE.finditer(text):
        window = text[cue_match.end(): cue_match.end() + 120]
        date_match = _DATE_RE.search(window)
        if date_match:
            time_match = _TIME_RE.search(window)
            candidate = date_match.group(0) + (
                f" {time_match.group(0)}" if time_match else ""
            )
            try:
                parsed = dateparser.parse(candidate, fuzzy=True, default=reference_time)
                logger.info("Deadline extracted via cue+date: %s -> %s", candidate, parsed)
                return parsed
            except (ValueError, OverflowError):
                continue

    # 2. Fall back to the first date-like pattern anywhere in the text.
    date_match = _DATE_RE.search(text)
    if date_match:
        time_match = _TIME_RE.search(text[date_match.end(): date_match.end() + 40])
        candidate = date_match.group(0) + (f" {time_match.group(0)}" if time_match else "")
        try:
            parsed = dateparser.parse(candidate, fuzzy=True, default=reference_time)
            logger.info("Deadline extracted via bare date: %s -> %s", candidate, parsed)
            return parsed
        except (ValueError, OverflowError):
            pass

    # 3. Relative phrases ("submit by tomorrow", "due end of week").
    lowered = text.lower()
    for phrase, fn in _RELATIVE_MAP.items():
        if phrase in lowered:
            parsed = fn(reference_time)
            logger.info("Deadline extracted via relative phrase '%s' -> %s", phrase, parsed)
            return parsed

    return None

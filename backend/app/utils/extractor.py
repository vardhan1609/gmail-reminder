"""
Regex and heuristic-based deadline and date extractor.
Distinguishes submission deadlines, event dates, appointment dates, and email header dates.
Computes confidence scores and detects ambiguous dates.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import re
from typing import Optional, Tuple
from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    deadline: Optional[datetime]
    original_text: Optional[str]
    confidence_score: float
    is_ambiguous: bool
    date_type: str  # "submission_deadline", "event_date", "appointment_date", "email_date", "none"


# Strong deadline cues indicate an actionable submission or payment deadline
DEADLINE_CUES = [
    r"deadline\s*(?:is|:)?",
    r"due\s+date\s*(?:is|:)?",
    r"due\s+by",
    r"due\s+on",
    r"last\s+date\s*(?:for|to|of)?",
    r"submit\s*(?:ted|ion)?\s*(?:by|before|on)?",
    r"submission\s+deadline",
    r"must\s+be\s+received\s+by",
    r"closes\s+on",
    r"closing\s+date",
    r"final\s+date",
    r"pay\s+before",
    r"complete\s+by",
]

# Event / meeting cues
EVENT_CUES = [
    r"scheduled\s+(?:for|on)",
    r"meeting\s+(?:on|at)",
    r"webinar\s+(?:on|at)",
    r"session\s+(?:on|at)",
    r"event\s+(?:date|on|takes place on)",
    r"join\s+us\s+on",
]

# Email metadata to ignore / filter out
EMAIL_HEADER_PATTERNS = [
    r"on\s+[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4},?\s+at\s+.*wrote:",
    r"sent\s*:\s*[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}",
    r"date\s*:\s*[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}",
]

DATE_PATTERNS = [
    # 5 Aug 2026 / 5th August 2026 / August 5, 2026
    r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}",
    r"[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}",
    # 5 Aug / Aug 5 (no year - ambiguous)
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*",
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?",
    # 2026-08-05 / 05-08-2026 / 05/08/2026 / 05/06 (2-part date without year)
    r"\d{4}-\d{2}-\d{2}",
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?",
]

TIME_PATTERN = r"\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)|\b\d{1,2}:\d{2}\s*(?:hrs|hours)?"

_DEADLINE_RE = re.compile(r"(" + "|".join(DEADLINE_CUES) + r")", re.IGNORECASE)
_EVENT_RE = re.compile(r"(" + "|".join(EVENT_CUES) + r")", re.IGNORECASE)
_DATE_RE = re.compile(r"(" + "|".join(DATE_PATTERNS) + r")", re.IGNORECASE)
_TIME_RE = re.compile(TIME_PATTERN, re.IGNORECASE)

_RELATIVE_MAP = {
    "today": lambda now: now.replace(hour=23, minute=59, second=0),
    "tomorrow": lambda now: (now + timedelta(days=1)).replace(hour=23, minute=59, second=0),
    "end of day": lambda now: now.replace(hour=23, minute=59, second=0),
    "end of the week": lambda now: (now + relativedelta(weekday=4)).replace(hour=23, minute=59, second=0),
    "next week": lambda now: (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=0),
}


def sanitize_email_text(text: str) -> str:
    """Strip out standard email quote headers so they are not mistaken for deadlines."""
    cleaned = text
    for pattern in EMAIL_HEADER_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def extract_deadline_details(
    text: str, reference_time: Optional[datetime] = None
) -> ExtractionResult:
    """
    Extracts deadline with confidence score, original text snippet, and ambiguity flag.
    Does not invent deadlines when text contains only conversational or ambiguous dates.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    if not text or not text.strip():
        return ExtractionResult(None, None, 0.0, False, "none")

    cleaned_text = sanitize_email_text(text.replace("\n", " "))

    # 1. Check for explicit deadline cues (highest confidence)
    for cue_match in _DEADLINE_RE.finditer(cleaned_text):
        window_start = cue_match.start()
        window_end = min(len(cleaned_text), cue_match.end() + 100)
        window = cleaned_text[window_start:window_end]

        date_match = _DATE_RE.search(window)
        if date_match:
            time_match = _TIME_RE.search(window)
            candidate_raw = date_match.group(0)
            if time_match:
                candidate_raw += f" {time_match.group(0)}"

            try:
                # Detect ambiguity: if format has no year or is a slash date (MM/DD vs DD/MM)
                is_ambiguous = False
                if not re.search(r"\b20\d{2}\b", candidate_raw):
                    is_ambiguous = True
                if re.search(r"^\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?$", candidate_raw.strip()):
                    # Slash dates without spelled month can be ambiguous between day/month
                    parts = re.split(r"[/-]", candidate_raw.strip())
                    if len(parts) >= 2 and int(parts[0]) <= 12 and int(parts[1]) <= 12:
                        is_ambiguous = True

                parsed = dateparser.parse(candidate_raw, fuzzy=True, default=reference_time)
                # Ensure timezone-aware
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)

                confidence = 0.95 if not is_ambiguous else 0.65
                return ExtractionResult(
                    deadline=parsed,
                    original_text=window.strip(),
                    confidence_score=confidence,
                    is_ambiguous=is_ambiguous,
                    date_type="submission_deadline",
                )
            except (ValueError, OverflowError):
                continue

    # 2. Check for event / appointment cues
    for cue_match in _EVENT_RE.finditer(cleaned_text):
        window_start = cue_match.start()
        window_end = min(len(cleaned_text), cue_match.end() + 100)
        window = cleaned_text[window_start:window_end]

        date_match = _DATE_RE.search(window)
        if date_match:
            time_match = _TIME_RE.search(window)
            candidate_raw = date_match.group(0)
            if time_match:
                candidate_raw += f" {time_match.group(0)}"
            try:
                is_ambiguous = False
                if not re.search(r"\b20\d{2}\b", candidate_raw):
                    is_ambiguous = True
                if re.search(r"^\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?$", candidate_raw.strip()):
                    is_ambiguous = True

                parsed = dateparser.parse(candidate_raw, fuzzy=True, default=reference_time)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                confidence = 0.75 if not is_ambiguous else 0.50
                return ExtractionResult(
                    deadline=parsed,
                    original_text=window.strip(),
                    confidence_score=confidence,
                    is_ambiguous=is_ambiguous,
                    date_type="event_date",
                )
            except (ValueError, OverflowError):
                continue

    # 3. Relative phrases: "submit by tomorrow", "due end of the week"
    lowered = cleaned_text.lower()
    for phrase, fn in _RELATIVE_MAP.items():
        if f"due {phrase}" in lowered or f"by {phrase}" in lowered or f"before {phrase}" in lowered:
            parsed = fn(reference_time)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return ExtractionResult(
                deadline=parsed,
                original_text=phrase,
                confidence_score=0.80,
                is_ambiguous=False,
                date_type="submission_deadline",
            )

    # 4. Bare dates without any deadline cue are marked as ambiguous / informational
    bare_match = _DATE_RE.search(cleaned_text)
    if bare_match:
        window = cleaned_text[max(0, bare_match.start() - 20) : min(len(cleaned_text), bare_match.end() + 40)]
        candidate_raw = bare_match.group(0)
        try:
            parsed = dateparser.parse(candidate_raw, fuzzy=True, default=reference_time)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return ExtractionResult(
                deadline=parsed,
                original_text=window.strip(),
                confidence_score=0.35,  # Low confidence: bare date
                is_ambiguous=True,
                date_type="informational_date",
            )
        except (ValueError, OverflowError):
            pass

    return ExtractionResult(None, None, 0.0, False, "none")


def extract_deadline(text: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
    """Compatibility helper returning single datetime if confident, otherwise None."""
    res = extract_deadline_details(text, reference_time)
    if res.confidence_score >= 0.60 and not res.is_ambiguous and res.date_type == "submission_deadline":
        return res.deadline
    return None

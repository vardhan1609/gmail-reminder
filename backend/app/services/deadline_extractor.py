"""
Orchestrates deadline extraction:
1. Heuristic regex pass with cue extraction and confidence scoring.
2. If ambiguous or low confidence and LLM is enabled, call LLM for disambiguation.
3. If still ambiguous, flags it for review rather than inventing a false deadline.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.utils.extractor import extract_deadline_details, ExtractionResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _llm_disambiguate_deadline(subject: str, body: str) -> Optional[ExtractionResult]:
    from app.services.llm import llm_complete

    prompt = (
        "Extract the single most important submission deadline or payment due date from this email.\n"
        "If there is NO clear deadline, or if the date is merely an event date or appointment date, "
        "indicate that in the response.\n\n"
        "Respond ONLY with valid JSON in this exact structure:\n"
        "{\n"
        '  "has_deadline": true/false,\n'
        '  "deadline_iso": "YYYY-MM-DDTHH:MM:SS" or null,\n'
        '  "date_type": "submission_deadline" or "event_date" or "none",\n'
        '  "confidence": 0.0 to 1.0,\n'
        '  "is_ambiguous": true/false,\n'
        '  "snippet": "original text snippet"\n'
        "}\n\n"
        f"Subject: {subject}\n\nBody:\n{body[:3000]}"
    )
    try:
        raw = llm_complete(prompt, json_mode=True).strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        if data.get("has_deadline") and data.get("deadline_iso"):
            dt = datetime.fromisoformat(data["deadline_iso"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return ExtractionResult(
                deadline=dt,
                original_text=data.get("snippet", ""),
                confidence_score=float(data.get("confidence", 0.8)),
                is_ambiguous=bool(data.get("is_ambiguous", False)),
                date_type=data.get("date_type", "submission_deadline"),
            )
    except Exception as exc:
        logger.warning("LLM deadline extraction error: %s", exc)
    return None


def extract_deadline(subject: str, body: str) -> Optional[datetime]:
    """Compatibility function returning datetime or None."""
    res = get_deadline_extraction(subject, body)
    if res.confidence_score >= 0.60 and not res.is_ambiguous and res.date_type == "submission_deadline":
        return res.deadline
    return None


def get_deadline_extraction(subject: str, body: str) -> ExtractionResult:
    """Full extraction with confidence score and ambiguity detection."""
    from app.services.llm import llm_is_enabled

    full_text = f"{subject}\n{body}"
    res = extract_deadline_details(full_text)

    # If confident match found
    if res.confidence_score >= 0.85 and not res.is_ambiguous:
        return res

    # If ambiguous or low confidence, try LLM fallback if configured
    if llm_is_enabled():
        logger.info("Attempting LLM disambiguation for %r", subject)
        llm_res = _llm_disambiguate_deadline(subject, body)
        if llm_res:
            return llm_res

    return res

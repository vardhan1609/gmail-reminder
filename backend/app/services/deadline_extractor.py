"""
Orchestrates deadline extraction: try the free regex/heuristic pass first
(app/utils/extractor.py); only call the LLM if that pass finds nothing and
an LLM provider is configured.
"""
import json
from datetime import datetime
from typing import Optional

from app.config import settings
from app.utils.extractor import extract_deadline as regex_extract_deadline
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _llm_extract_deadline(subject: str, body: str) -> Optional[datetime]:
    from app.services.llm import llm_complete

    prompt = (
        "Extract the single most important deadline (submission date/time, "
        "exam date, last date to pay, event date, etc.) from this university "
        "email. Respond ONLY with JSON: {\"deadline_iso\": \"YYYY-MM-DDTHH:MM:SS\"} "
        "using 24-hour time, or {\"deadline_iso\": null} if there is no clear "
        "deadline. Assume the current year is "
        f"{datetime.utcnow().year} if no year is given.\n\n"
        f"Subject: {subject}\n\nBody:\n{body[:3000]}"
    )
    raw = llm_complete(prompt, json_mode=True).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        if data.get("deadline_iso"):
            return datetime.fromisoformat(data["deadline_iso"])
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM deadline extraction failed to parse response %r: %s", raw, exc)
    return None


def extract_deadline(subject: str, body: str) -> Optional[datetime]:
    from app.services.llm import llm_is_enabled

    deadline = regex_extract_deadline(f"{subject}\n{body}")
    if deadline:
        return deadline

    if llm_is_enabled():
        logger.info("Regex found no deadline for %r, trying LLM", subject)
        return _llm_extract_deadline(subject, body)

    return None

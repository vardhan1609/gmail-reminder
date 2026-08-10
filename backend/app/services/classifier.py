"""
Classifies an email into one of the categories below.

Two tiers:
  1. Rule-based keyword scoring (fast, free, zero dependencies, runs on
     every email).
  2. Optional LLM fallback (only called when rule-based scoring is
     ambiguous i.e. top two categories are close, or nothing matched) if
     any LLM provider is configured.
"""
from collections import Counter

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

CATEGORIES = [
    "Assignment",
    "Exam",
    "Placement",
    "Workshop",
    "Holiday",
    "Fee",
    "Seminar",
    "Meeting",
    "Event",
    "General",
]

KEYWORDS = {
    "Assignment": ["assignment", "homework", "submission", "submit your", "problem set"],
    "Exam": ["exam", "examination", "midterm", "final test", "quiz", "hall ticket", "admit card"],
    "Placement": ["placement", "internship", "recruiter", "campus drive", "job offer", "hiring"],
    "Workshop": ["workshop", "hands-on", "training session", "bootcamp"],
    "Holiday": ["holiday", "vacation", "college closed", "no classes"],
    "Fee": ["fee", "tuition", "payment due", "invoice", "outstanding balance"],
    "Seminar": ["seminar", "guest lecture", "talk by", "colloquium"],
    "Meeting": ["meeting", "agenda", "minutes of meeting", "sync-up"],
    "Event": ["fest", "festival", "competition", "hackathon", "cultural event"],
}


def _rule_based_scores(subject: str, body: str) -> Counter:
    text = f"{subject}\n{body}".lower()
    scores: Counter = Counter()
    for category, words in KEYWORDS.items():
        for word in words:
            if word in text:
                scores[category] += 1
    return scores


def _llm_classify(subject: str, body: str) -> str:
    """Fallback classification via configured LLM provider."""
    from app.services.llm import llm_complete

    prompt = (
        "Classify this university email into exactly one category from this "
        f"list: {', '.join(CATEGORIES)}.\n\n"
        f"Subject: {subject}\n\nBody:\n{body[:2000]}\n\n"
        "Respond with ONLY the category name, nothing else."
    )
    answer = llm_complete(prompt).strip()
    return answer if answer in CATEGORIES else "General"


def classify_email(subject: str, body: str) -> str:
    from app.services.llm import llm_is_enabled

    scores = _rule_based_scores(subject, body)

    if not scores:
        if llm_is_enabled():
            logger.info("No keyword match for %r, falling back to LLM", subject)
            return _llm_classify(subject, body)
        return "General"

    top = scores.most_common(2)
    # Ambiguous if the top two categories are tied / very close -> ask the LLM
    if llm_is_enabled() and len(top) > 1 and top[0][1] - top[1][1] <= 1:
        logger.info("Ambiguous classification for %r (%s), falling back to LLM", subject, top)
        return _llm_classify(subject, body)

    return top[0][0]

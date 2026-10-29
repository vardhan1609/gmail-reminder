"""
Email classification service supporting all specified categories:
- Academics and assignments
- Examinations and results
- Placements and internships
- Fees and payments
- Meetings and events
- Personal messages
- Bills and receipts
- Travel and bookings
- Newsletters and promotions
- Security alerts
- Other

Classification never discards an email: if scoring fails or is unclear,
it safely defaults to "Other".
"""
from collections import Counter
from typing import List, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

CATEGORIES = [
    "Academics and assignments",
    "Examinations and results",
    "Placements and internships",
    "Fees and payments",
    "Meetings and events",
    "Personal messages",
    "Bills and receipts",
    "Travel and bookings",
    "Newsletters and promotions",
    "Security alerts",
    "Other",
]

KEYWORDS = {
    "Academics and assignments": [
        "assignment", "homework", "submission", "submit your", "problem set",
        "lecture", "syllabus", "coursework", "canvas", "blackboard", "moodle",
        "grading", "prof", "professor", "ta", "teaching assistant", "lab manual",
        "class schedule", "reading list", "term paper"
    ],
    "Examinations and results": [
        "exam", "examination", "midterm", "final test", "quiz", "hall ticket",
        "admit card", "grades", "gpa", "marksheet", "transcript", "results",
        "invigilation", "revaluation", "scorecard", "test schedule"
    ],
    "Placements and internships": [
        "placement", "internship", "recruiter", "campus drive", "job offer",
        "hiring", "shortlisted", "interview", "resume", "cv", "stipend",
        "career", "aptitude test", "corporate", "jd", "job description"
    ],
    "Fees and payments": [
        "tuition fee", "fee due", "semester fee", "hostel fee", "payment receipt",
        "dues", "fine", "penalty", "scholarship disbursement", "financial aid",
        "bursar", "account balance"
    ],
    "Meetings and events": [
        "meeting", "agenda", "minutes of meeting", "sync-up", "zoom link",
        "google meet", "townhall", "seminar", "webinar", "conference",
        "guest lecture", "workshop", "hackathon", "cultural fest", "symposium"
    ],
    "Personal messages": [
        "hey", "hello", "how are you", "catch up", "lunch", "dinner",
        "weekend", "personal", "family", "friends", "plans", "chat"
    ],
    "Bills and receipts": [
        "invoice", "billing statement", "order confirmation", "payment confirmation",
        "receipt", "charge", "subscription", "credit card statement", "utility bill",
        "tax invoice"
    ],
    "Travel and bookings": [
        "flight", "ticket", "boarding pass", "hotel reservation", "booking confirmation",
        "itinerary", "pnr", "airbnb", "train ticket", "trip", "check-in"
    ],
    "Newsletters and promotions": [
        "newsletter", "weekly digest", "unsubscribe", "special offer", "discount",
        "sale", "promo", "deal", "marketing", "updates from", "roundup"
    ],
    "Security alerts": [
        "security alert", "password reset", "new login", "suspicious activity",
        "two-factor", "2fa", "verification code", "otp", "unauthorized access",
        "account recovery", "device detected"
    ],
}


def _rule_based_scores(subject: str, body: str) -> Counter:
    text = f"{subject}\n{body}".lower()
    scores: Counter = Counter()
    for category, words in KEYWORDS.items():
        for word in words:
            if word in text:
                # Give higher weight to matches in the subject
                weight = 3 if word in subject.lower() else 1
                scores[category] += weight
    return scores


def _llm_classify(subject: str, body: str) -> str:
    """Fallback classification via LLM provider if configured."""
    try:
        from app.services.llm import llm_complete
        prompt = (
            "Classify the following email into exactly one category from this list: "
            f"{', '.join(CATEGORIES)}.\n\n"
            f"Subject: {subject}\n\nBody:\n{body[:2000]}\n\n"
            "Respond with ONLY the exact category name from the list, nothing else."
        )
        answer = llm_complete(prompt).strip()
        for cat in CATEGORIES:
            if cat.lower() == answer.lower():
                return cat
    except Exception as exc:
        logger.warning("LLM classification failed: %s", exc)
    return "Other"


def classify_email(subject: str, body: str) -> str:
    """
    Classifies an email into one of the designated categories.
    Never fails or throws: returns 'Other' on ambiguity or errors.
    """
    try:
        from app.services.llm import llm_is_enabled
        scores = _rule_based_scores(subject, body)

        if not scores:
            if llm_is_enabled():
                return _llm_classify(subject, body)
            return "Other"

        top = scores.most_common(2)
        # If the top score is positive and clearly separated from second
        if len(top) == 1 or (top[0][1] - top[1][1] >= 2):
            return top[0][0]

        # Close call: try LLM if enabled, else pick the top rule match
        if llm_is_enabled():
            return _llm_classify(subject, body)

        return top[0][0]
    except Exception as exc:
        logger.error("Error in email classification: %s", exc)
        return "Other"

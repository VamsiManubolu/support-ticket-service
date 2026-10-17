"""Keyword-based rules: summary, spam detection, priority suggestion and routing.
Pure, deterministic functions with no I/O."""

import re
from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import Department, TicketCategory, TicketPriority

SUMMARY_MAX_LENGTH = 200
SPAM_THRESHOLD = Decimal("0.5")
# endings allowed on a keyword's last word: charge -> charged, crash -> crashes
WORD_ENDINGS = r"(?:s|es|d|ed|ing)?"

_SPAM_PHRASES = (
    "free money",
    "click here",
    "winner",
    "lottery",
    "crypto",
    "investment opportunity",
    "act now",
    "100% free",
    "buy now",
)
_URGENT_PHRASES = ("outage", "down", "data loss", "security", "breach", "hacked", "urgent")
_HIGH_PHRASES = ("cannot", "can't", "unable", "error", "failed", "charged twice", "refund")
_LOW_PHRASES = ("question", "feature request", "suggestion", "how do i", "just wondering")
_DEPARTMENT_BY_CATEGORY = {
    TicketCategory.BILLING: Department.BILLING,
    TicketCategory.TECHNICAL: Department.TECHNICAL_SUPPORT,
    TicketCategory.ACCOUNT: Department.ACCOUNT_MANAGEMENT,
}
_GENERAL_ROUTING_PHRASES = (
    (Department.BILLING, ("invoice", "payment", "charge", "refund", "subscription")),
    (Department.TECHNICAL_SUPPORT, ("error", "bug", "crash", "not working", "login")),
    (Department.ACCOUNT_MANAGEMENT, ("account", "password", "email change", "profile")),
)


@dataclass(frozen=True)
class SpamResult:
    is_spam: bool
    score: Decimal


def summarize(subject: str, description: str) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s+", " ".join(description.split()), maxsplit=1)[0]
    summary = f"{subject.strip()}: {first_sentence}"
    if len(summary) <= SUMMARY_MAX_LENGTH:
        return summary
    return summary[: SUMMARY_MAX_LENGTH - 1].rstrip() + "…"


# Add up points for spam signals; 0.5 or more counts as spam
def detect_spam(subject: str, description: str) -> SpamResult:
    text = f"{subject} {description}"
    lowered = text.lower()
    score = Decimal("0.35") * sum(_matches(lowered, phrase) for phrase in _SPAM_PHRASES)
    score += Decimal("0.15") * min(len(re.findall(r"https?://", lowered)), 2)
    if text.count("!") >= 3:
        score += Decimal("0.15")
    letters = [char for char in text if char.isalpha()]
    if len(letters) >= 20 and sum(char.isupper() for char in letters) / len(letters) > 0.6:
        score += Decimal("0.25")
    score = min(score, Decimal(1)).quantize(Decimal("0.001"))
    return SpamResult(is_spam=score >= SPAM_THRESHOLD, score=score)


# Pick the highest priority whose keywords appear, else keep the customer's
def suggest_priority(subject: str, description: str, current: TicketPriority) -> TicketPriority:
    text = f"{subject} {description}".lower()
    if _contains_any(text, _URGENT_PHRASES):
        return TicketPriority.URGENT
    if _contains_any(text, _HIGH_PHRASES):
        return TicketPriority.HIGH
    if _contains_any(text, _LOW_PHRASES):
        return TicketPriority.LOW
    return current


# Route by category, or by keywords when the category is GENERAL
def route_department(category: TicketCategory, subject: str, description: str) -> Department:
    if category in _DEPARTMENT_BY_CATEGORY:
        return _DEPARTMENT_BY_CATEGORY[category]
    text = f"{subject} {description}".lower()
    for department, phrases in _GENERAL_ROUTING_PHRASES:
        if _contains_any(text, phrases):
            return department
    return Department.CUSTOMER_SUPPORT


def _matches(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}{WORD_ENDINGS}\b", text) is not None


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_matches(text, phrase) for phrase in phrases)

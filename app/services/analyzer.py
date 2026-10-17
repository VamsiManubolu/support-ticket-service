"""Ticket analysis interface, designed for slow external calls such as an LLM.
KeywordAnalyzer is the default; a real LLM client would implement the same Protocol."""

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.models.enums import Department, TicketCategory, TicketPriority
from app.services import processing


class TransientAnalysisError(Exception):
    """Worth retrying: timeout, rate limit, upstream 5xx."""


@dataclass(frozen=True)
class TicketInput:
    ticket_id: uuid.UUID
    subject: str
    description: str
    category: TicketCategory
    priority: TicketPriority


@dataclass(frozen=True)
class AnalysisResult:
    summary: str
    is_spam: bool
    spam_score: Decimal
    suggested_priority: TicketPriority
    department: Department


class TicketAnalyzer(Protocol):
    async def analyze(self, ticket: TicketInput) -> AnalysisResult: ...


class KeywordAnalyzer:
    def __init__(self, simulated_latency: float = 0.0) -> None:
        self.simulated_latency = simulated_latency

    # Run the keyword rules (after the optional fake delay)
    async def analyze(self, ticket: TicketInput) -> AnalysisResult:
        if self.simulated_latency:
            await asyncio.sleep(self.simulated_latency)
        spam = processing.detect_spam(ticket.subject, ticket.description)
        return AnalysisResult(
            summary=processing.summarize(ticket.subject, ticket.description),
            is_spam=spam.is_spam,
            spam_score=spam.score,
            suggested_priority=processing.suggest_priority(
                ticket.subject, ticket.description, ticket.priority
            ),
            department=processing.route_department(
                ticket.category, ticket.subject, ticket.description
            ),
        )


async def analyze_with_timeout(
    analyzer: TicketAnalyzer, ticket: TicketInput, timeout: float
) -> AnalysisResult:
    try:
        return await asyncio.wait_for(analyzer.analyze(ticket), timeout)
    except TimeoutError as exc:
        raise TransientAnalysisError(f"Analysis timed out after {timeout}s") from exc


@lru_cache
def get_analyzer() -> TicketAnalyzer:
    settings = get_settings()
    return KeywordAnalyzer(simulated_latency=settings.processing_simulated_latency_ms / 1000)

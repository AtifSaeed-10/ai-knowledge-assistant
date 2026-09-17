"""
Per-tier limits, resolved from env at call time.

Read through these helpers rather than importing settings directly so limits
can be re-tuned in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from app_platform import settings
from app_platform.auth.context import RequestContext

RESOURCE_PDFS = "pdfs"
RESOURCE_QUESTIONS = "questions"

# Guests have no billing period; their allowance is for the whole trial.
GUEST_PERIOD = "trial"


@dataclass(frozen=True)
class TierLimits:
    max_pdfs: int
    max_questions: int
    questions_window: str  # "trial" or "month"


def limits_for(context: RequestContext) -> TierLimits:
    if context.is_guest:
        return TierLimits(
            max_pdfs=settings.QUOTA_GUEST_MAX_PDFS,
            max_questions=settings.QUOTA_GUEST_MAX_QUESTIONS,
            questions_window="trial",
        )
    return TierLimits(
        max_pdfs=settings.QUOTA_USER_MAX_PDFS,
        max_questions=settings.QUOTA_USER_MAX_QUESTIONS_MONTHLY,
        questions_window="month",
    )

"""
Held-out operations handbook used by item 12/14/15.

Generic native-text PDF (not the demo corpora). Distinctive phrases per page
are the gold spans. Cases in real_document_cases.json adjudicate this file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf as fitz

HELD_OUT_DOCUMENT_ID = "held-out-handbook"
HELD_OUT_PDF_NAME = "held_out_handbook.pdf"
HELD_OUT_VERSION = "v1"

ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "real_pdfs" / HELD_OUT_PDF_NAME


def _wrap_lines(text: str, width: int = 88) -> list[str]:
    lines: list[str] = []
    for paragraph in re.split(r"\n+", text.strip()):
        words = paragraph.split()
        current: list[str] = []
        size = 0
        for word in words:
            extra = len(word) + (1 if current else 0)
            if current and size + extra > width:
                lines.append(" ".join(current))
                current = [word]
                size = len(word)
            else:
                current.append(word)
                size += extra
        if current:
            lines.append(" ".join(current))
    return lines


def write_text_pdf(path: str | Path, page_texts: list[str]) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    try:
        for text in page_texts:
            page = doc.new_page()
            y = 72.0
            for line in _wrap_lines(text):
                page.insert_text((72, y), line)
                y += 14.0
                if y > 740:
                    break
        doc.save(str(dest))
    finally:
        doc.close()
    return dest


# Ten native-text facts (pages 1-10). Extra pages support item-15 scenarios
# only and are not part of the 20-case release catalog.
FACTS: list[dict[str, Any]] = [
    {
        "page": 1,
        "slug": "notice",
        "claim": (
            "Either party may terminate employment by providing thirty days "
            "written notice to the other party."
        ),
        "quote": "thirty days written notice",
        "question": "How many days of written notice are required to terminate employment?",
        "body": (
            "EMPLOYMENT TERMINATION. Token HB-TERM-30. Either party may terminate "
            "employment by providing thirty days written notice to the other party. "
            "Notice must be delivered in writing to the registered office of the "
            "recipient. Unused paid leave is not part of the notice calculation and "
            "does not extend the termination date. Verbal warnings do not start the "
            "notice clock. Staff records describe how a contract may end under this "
            "clause. The handbook treats termination as a documented process, not an "
            "informal conversation. Copies of notice letters are filed with human "
            "resources within two working days of delivery. This section does not "
            "cover temporary suspensions or unpaid leave. Repeat token HB-TERM-30."
        ),
    },
    {
        "page": 2,
        "slug": "leave",
        "claim": (
            "Full-time staff receive twenty-two days of paid leave in each "
            "calendar year."
        ),
        "quote": "twenty-two days of paid leave",
        "question": "How many days of paid leave does full-time staff receive each year?",
        "body": (
            "PAID LEAVE ENTITLEMENT. Token HB-LEAVE-22. Full-time staff receive "
            "twenty-two days of paid leave in each calendar year. Leave is accrued "
            "monthly and must be requested through the staff portal at least one "
            "week in advance except for illness. Carry-over is capped at five unused "
            "days. Public holidays are counted separately and do not reduce the "
            "twenty-two day bank. Part-time accrual is pro-rated by scheduled hours. "
            "Managers may not substitute cash for unused leave except at exit. Repeat "
            "token HB-LEAVE-22."
        ),
    },
    {
        "page": 3,
        "slug": "onboarding",
        "claim": (
            "New hires complete a four-stage onboarding sequence before receiving "
            "production credentials."
        ),
        "quote": "four-stage onboarding sequence",
        "question": "How many stages are in the onboarding sequence before production credentials?",
        "body": (
            "STAFF ONBOARDING. Token HB-ONB-4. New hires complete a four-stage "
            "onboarding sequence before receiving production credentials. The stages "
            "are orientation, policy acknowledgement, shadowed work, and a skills "
            "check. Skipping a stage is not permitted. A buddy is assigned on day "
            "one and remains available through stage four. Facilities access is "
            "limited to the training floor until the sequence is complete. Human "
            "resources records the completion date in the personnel file. Repeat "
            "token HB-ONB-4."
        ),
    },
    {
        "page": 4,
        "slug": "remote",
        "claim": "Remote-work eligibility is reviewed each March.",
        "quote": "remote-work eligibility is reviewed each March",
        "question": "When is remote-work eligibility reviewed?",
        "body": (
            "REMOTE WORK. Token HB-REMOTE-MAR. Remote-work eligibility is reviewed "
            "each March. Eligibility depends on role type, recent performance, and "
            "coverage needs. Staff who are eligible may work from home up to three "
            "days each week. Core hours remain ten to three in the company time zone. "
            "Equipment is supplied only after the March review confirms eligibility. "
            "Ad-hoc remote days outside the approved pattern require a manager note. "
            "This policy does not apply to roles that must stay on site for safety. "
            "Repeat token HB-REMOTE-MAR."
        ),
    },
    {
        "page": 5,
        "slug": "review",
        "claim": (
            "The January performance-review cycle uses output quality, peer "
            "feedback, and customer outcomes."
        ),
        "quote": "January performance-review cycle",
        "question": "In which month does the performance-review cycle take place?",
        "body": (
            "ANNUAL PERFORMANCE REVIEW. Token HB-REVIEW-JAN. The January "
            "performance-review cycle uses output quality, peer feedback, and "
            "customer outcomes. Those three long-term inputs are weighted equally. "
            "Self-assessments are due on the first working day of January. Managers "
            "hold calibration meetings before letters are issued. Ratings do not "
            "change mid-year except after a documented performance plan. Compensation "
            "adjustments, when any, follow the January letters. Repeat token "
            "HB-REVIEW-JAN."
        ),
    },
    {
        "page": 6,
        "slug": "pantry",
        "claim": (
            "The office pantry restock includes tea, coffee, and oat biscuits."
        ),
        "quote": "tea, coffee, and oat biscuits",
        "question": "What does the office pantry restock include?",
        "body": (
            "WORKPLACE CATERING. Token HB-PANTRY-TEA. The office pantry restock "
            "includes tea, coffee, and oat biscuits. Fresh fruit is optional and "
            "depends on weekly budget. Staff may not store raw meat in the shared "
            "refrigerator. The catering desk places the pantry order every Monday "
            "morning. Allergens are listed on the cupboard door. Personal snacks "
            "must be labeled. This section is separate from client hospitality. "
            "Repeat token HB-PANTRY-TEA."
        ),
    },
    {
        "page": 7,
        "slug": "expense",
        "claim": (
            "Purchases require dual-control expense approvals above five thousand."
        ),
        "quote": "dual-control expense approvals above five thousand",
        "question": "Above what amount do expense approvals require dual control?",
        "body": (
            "EXPENSE CONTROL. Token HB-EXP-5000. Purchases require dual-control "
            "expense approvals above five thousand. Ordinary spend below that amount "
            "needs a single manager signature. Split invoices to avoid the threshold "
            "are treated as a policy breach. Finance keeps the approval log for seven "
            "years. Travel advances follow the same dual-control rule when the trip "
            "budget exceeds five thousand. Repeat token HB-EXP-5000."
        ),
    },
    {
        "page": 8,
        "slug": "retention",
        "claim": (
            "Article 12 of this handbook sets an eighteen-month data-retention "
            "window."
        ),
        "quote": "eighteen-month data-retention window",
        "question": "How long is the data-retention window in Article 12?",
        "body": (
            "RECORDS AND RETENTION. Token HB-RETENTION-18. Article 12 of this "
            "handbook sets an eighteen-month data-retention window. Working files "
            "older than eighteen months are archived or deleted unless a legal hold "
            "is active. Customer tickets follow the same clock. Backups are not an "
            "exception to Article 12. The records officer publishes a quarterly "
            "deletion report. Repeat token HB-RETENTION-18."
        ),
    },
    {
        "page": 9,
        "slug": "incident",
        "claim": "Staff must file incident reports within twenty-four hours.",
        "quote": "incident reports within twenty-four hours",
        "question": "How quickly must staff file incident reports?",
        "body": (
            "INCIDENT REPORTING. Token HB-INC-24H. Staff must file incident reports "
            "within twenty-four hours. The clock starts when the staff member learns "
            "of the event, not when investigation ends. Near misses use the same "
            "form. Reports go to the duty manager and the safety mailbox. Follow-up "
            "actions are assigned within five working days. Failing to file on time "
            "is itself recorded as a process incident. Repeat token HB-INC-24H."
        ),
    },
    {
        "page": 10,
        "slug": "password",
        "claim": "Production passwords follow password rotation every ninety days.",
        "quote": "password rotation every ninety days",
        "question": "How often must production passwords be rotated?",
        "body": (
            "ACCESS CREDENTIALS. Token HB-PASS-90. Production passwords follow "
            "password rotation every ninety days. Reused passwords from the prior "
            "four cycles are rejected. Shared logins are forbidden. Hardware tokens "
            "are issued for administrator roles. Lost tokens are reported as "
            "incidents. Service accounts use vault-managed secrets rather than "
            "personal passwords. Repeat token HB-PASS-90."
        ),
    },
]

EXTRA_PAGES: list[str] = [
    (
        "HANDBOOK DEDICATION. This operations handbook is dedicated to Mira Chen "
        "and Omar Haddad for their work on the records desk. NOTE ON NAMES. "
        "Internal records refer to the Operations Unit as Ops Unit, formerly "
        "Support Desk. Front-matter pages are not employment clauses. Token "
        "HB-FRONT-DEDICATE. Readers looking for notice periods should use the "
        "employment termination section rather than this dedication page."
    ),
    (
        "Figure 1. Pipeline overview of the encoding stage used during handbook "
        "ingestion. Illustration 1 shows intake, split, and store. Table 1. "
        "Hyperparameters used in training the evaluation encoder. "
        "| learning_rate | batch_size | epochs | | 0.001 | 32 | 10 | Token "
        "HB-VISUAL-FIG."
    ),
]


def format_page(fact: dict[str, Any]) -> str:
    """Keep the gold span on its own line so wrap/extraction cannot split it."""
    quote = str(fact["quote"]).strip()
    body = str(fact["body"]).strip()
    if body.lower().startswith(quote.lower()):
        return body
    return f"{quote}\n{body}"


def page_texts() -> list[str]:
    return [format_page(fact) for fact in FACTS] + list(EXTRA_PAGES)


def write_held_out_pdf(path: str | Path | None = None) -> Path:
    dest = Path(path) if path is not None else PDF_PATH
    return write_text_pdf(dest, page_texts())


def localization_case_dict(fact: dict[str, Any]) -> dict[str, Any]:
    page = int(fact["page"])
    claim = str(fact["claim"])
    return {
        "case_id": f"loc-{fact['slug']}",
        "document_id": HELD_OUT_DOCUMENT_ID,
        "pdf_path": HELD_OUT_PDF_NAME,
        "question": str(fact["question"]),
        "claim_text": claim,
        "answer": f"{claim} [E1]",
        "expected_page": page,
        "expected_pages": [page],
        "expected_quote_substring": str(fact["quote"]),
        "content_type": "native_text",
        "evidence_id": "E1",
        "mode": "localization",
        "notes": f"Native-text localization for {fact['slug']} (page {page}).",
    }


def retrieval_case_dict(fact: dict[str, Any]) -> dict[str, Any]:
    page = int(fact["page"])
    claim = str(fact["claim"])
    return {
        "case_id": f"ret-{fact['slug']}",
        "document_id": HELD_OUT_DOCUMENT_ID,
        "pdf_path": HELD_OUT_PDF_NAME,
        "question": str(fact["question"]),
        "claim_text": claim,
        "answer": f"{claim} [E1]",
        "expected_page": page,
        "expected_pages": [page],
        "expected_quote_substring": str(fact["quote"]),
        "content_type": "native_text",
        "evidence_id": "E1",
        "mode": "retrieval",
        "notes": f"Retrieval recall-pool hit for {fact['slug']} (page {page}).",
    }


def catalog_case_dicts() -> list[dict[str, Any]]:
    rows = [localization_case_dict(fact) for fact in FACTS]
    rows.extend(retrieval_case_dict(fact) for fact in FACTS)
    return rows

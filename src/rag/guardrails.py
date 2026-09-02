"""Deterministic, Python-only safety checks for Grounded RAG Generation.

Two distinct jobs, both intentionally NOT delegated to another LLM call
(docs/rag_generation_v1_report.md §7/§10):

1. ``check_groundedness`` -- a READ-ONLY audit of what Claude actually
   returned, categorized A-E per the instructions. Used for tests and for
   any future logging/monitoring; does not modify anything.
2. ``sanitize_answer`` -- the actual enforcement mechanism. It rewrites the
   final ``GroundedAnswer`` text so that even if Claude ignores the system
   prompt entirely (adversarial user, model error), the text that reaches
   the user cannot contain an eligibility overclaim, a fabricated phone
   number/URL, or an unsupported money/percentage figure. This makes the
   safety guarantee independent of the model's own compliance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Set

from .generation_models import (
    GroundedAnswer,
    GroundedGenerationRequest,
    LLMGeneratedFields,
    SECTION_LABELS_KO,
)
from .models import ALL_SECTIONS, RetrievalResult

# ---------------------------------------------------------------------------
# A. Evidence sufficiency (checked BEFORE calling Claude -- §9)
# ---------------------------------------------------------------------------


def sections_with_evidence(retrieved_documents: List[RetrievalResult]) -> Set[str]:
    return {r.section for r in retrieved_documents}


def missing_sections_ko(retrieved_documents: List[RetrievalResult]) -> List[str]:
    """Korean-labeled list of sections that have NO retrieved evidence at
    all -- used to populate ``GroundedAnswer.insufficient_information``,
    computed in Python before Claude ever runs."""
    present = sections_with_evidence(retrieved_documents)
    return [f"{SECTION_LABELS_KO[s]} 정보 없음" for s in ALL_SECTIONS if s not in present]


def has_any_evidence(retrieved_documents: List[RetrievalResult]) -> bool:
    return len(retrieved_documents) > 0


def evidence_text_blob(retrieved_documents: List[RetrievalResult]) -> str:
    return "\n".join(r.content for r in retrieved_documents)


# ---------------------------------------------------------------------------
# B. Eligibility overclaim phrases (instructions §6/§10-B)
# ---------------------------------------------------------------------------

OVERCLAIM_PHRASES = [
    "신청할 수 있습니다",
    "신청하실 수 있습니다",
    "신청 가능합니다",
    "지원 대상입니다",
    "지원대상입니다",
    "대상자입니다",
    "받을 수 있습니다",
    "받으실 수 있습니다",
    "지원받으실 수 있습니다",
    "이용 가능합니다",
    "이용하실 수 있습니다",
    "자격이 됩니다",
    "자격이 있습니다",
    "수급 가능합니다",
    "무조건 받을 수 있",
    "확실히 받으실 수 있",
]

SAFE_REPLACEMENT = "대상일 가능성이 있어요(확정이 아니며 추가 확인이 필요해요)"


def find_overclaim_phrases(text: str) -> List[str]:
    return [p for p in OVERCLAIM_PHRASES if p in text]


# ---------------------------------------------------------------------------
# C/D. Fabricated contact info / amounts not present in evidence
# ---------------------------------------------------------------------------

# Note: uses (?<!\d)/(?!\d) instead of \b for the boundaries. Python's \b is
# a \w/\W transition, and Hangul syllables count as \w in Unicode mode -- a
# phone number immediately followed by a Korean particle with no space
# (e.g. "02-9999-9999로 연락하세요", extremely common) would silently fail
# to match with \b, since digit and Hangul are both \w and no boundary
# exists between them. Only an adjacent *digit* should block a match here.
PHONE_PATTERN = re.compile(r"(?<!\d)(0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}|1\d{3}[-.\s]?\d{4})(?!\d)")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
MONEY_PATTERN = re.compile(r"\d[\d,]*\s?원")
PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?\s?%")


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _supported_by_evidence(match_text: str, evidence_blob: str, numeric: bool = False) -> bool:
    if numeric:
        needle = _digits_only(match_text)
        return bool(needle) and needle in _digits_only(evidence_blob)
    return match_text in evidence_blob


def find_unsupported_contacts(text: str, evidence_blob: str) -> List[str]:
    found = []
    for m in PHONE_PATTERN.finditer(text):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            found.append(m.group())
    for m in URL_PATTERN.finditer(text):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=False):
            found.append(m.group())
    return found


def find_unsupported_amounts(text: str, evidence_blob: str) -> List[str]:
    found = []
    for m in MONEY_PATTERN.finditer(text):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            found.append(m.group())
    for m in PERCENT_PATTERN.finditer(text):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            found.append(m.group())
    return found


# ---------------------------------------------------------------------------
# Groundedness report (read-only audit, categories A-E)
# ---------------------------------------------------------------------------


@dataclass
class GroundednessReport:
    eligibility_overclaim_phrases: List[str] = field(default_factory=list)
    fabricated_application: bool = False
    fabricated_contacts: List[str] = field(default_factory=list)
    unsupported_amounts: List[str] = field(default_factory=list)
    unknown_coercion: bool = False

    @property
    def passed(self) -> bool:
        return not (
            self.eligibility_overclaim_phrases
            or self.fabricated_application
            or self.fabricated_contacts
            or self.unsupported_amounts
            or self.unknown_coercion
        )


def check_groundedness(
    fields: LLMGeneratedFields,
    request: GroundedGenerationRequest,
) -> GroundednessReport:
    """Read-only audit of Claude's raw structured output, BEFORE sanitize_answer
    runs. Never mutates ``fields`` -- see module docstring."""
    all_text = "\n".join(
        [
            fields.summary,
            fields.why_recommended,
            fields.eligibility_explanation,
            fields.support_explanation,
            fields.application_explanation,
            *fields.confirmation_items,
        ]
    )
    evidence_blob = evidence_text_blob(request.retrieved_documents)

    present_sections = sections_with_evidence(request.retrieved_documents)
    fabricated_application = bool(
        fields.application_explanation.strip() and "application" not in present_sections
    )

    unknown_coercion = bool(request.confirmation_needed) and not fields.confirmation_items

    return GroundednessReport(
        eligibility_overclaim_phrases=find_overclaim_phrases(all_text),
        fabricated_application=fabricated_application,
        fabricated_contacts=find_unsupported_contacts(all_text, evidence_blob),
        unsupported_amounts=find_unsupported_amounts(all_text, evidence_blob),
        unknown_coercion=unknown_coercion,
    )


# ---------------------------------------------------------------------------
# Sanitization -- the actual enforcement (defense in depth)
# ---------------------------------------------------------------------------


def sanitize_text(text: str, evidence_blob: str) -> str:
    if not text:
        return text

    cleaned = text
    for phrase in OVERCLAIM_PHRASES:
        if phrase in cleaned:
            cleaned = cleaned.replace(phrase, SAFE_REPLACEMENT)

    for m in list(PHONE_PATTERN.finditer(cleaned)):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            cleaned = cleaned.replace(m.group(), "[출처 확인 필요]")
    for m in list(URL_PATTERN.finditer(cleaned)):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=False):
            cleaned = cleaned.replace(m.group(), "[출처 확인 필요]")
    for m in list(MONEY_PATTERN.finditer(cleaned)):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            cleaned = cleaned.replace(m.group(), "[출처 확인 필요]")
    for m in list(PERCENT_PATTERN.finditer(cleaned)):
        if not _supported_by_evidence(m.group(), evidence_blob, numeric=True):
            cleaned = cleaned.replace(m.group(), "[출처 확인 필요]")

    return cleaned


def sanitize_answer(answer: GroundedAnswer, evidence_blob: str) -> GroundedAnswer:
    """Rewrites every LLM-authored text field on ``answer`` in place-equivalent
    fashion (returns a new object) so the final text can never contain an
    overclaim phrase or an evidence-unsupported phone/URL/amount, regardless
    of what Claude produced."""
    answer.summary = sanitize_text(answer.summary, evidence_blob)
    answer.why_recommended = sanitize_text(answer.why_recommended, evidence_blob)
    answer.eligibility_explanation = sanitize_text(answer.eligibility_explanation, evidence_blob)
    answer.support_explanation = sanitize_text(answer.support_explanation, evidence_blob)
    answer.application_explanation = sanitize_text(answer.application_explanation, evidence_blob)
    answer.confirmation_items = [sanitize_text(c, evidence_blob) for c in answer.confirmation_items]
    return answer

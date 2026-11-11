"""Human Review & Response Quality Assurance for Smart Farming Assistant.

Provides:
  • Multi-factor response quality scoring (confidence, source reliability, evidence completeness).
  • Automatic flagging of low-confidence and unsupported queries.
  • Persistent human review queue (JSON file storage under backend/data/human_reviews.json).
  • Human-in-the-loop review operations: list pending, approve, correct, reject.
  • Strict PII redaction on logged user queries.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_STORAGE_PATH = Path(__file__).parent / "data" / "human_reviews.json"


def sanitize_pii_for_review(text: str) -> str:
    """Scrub emails, Indian phone numbers, and Aadhaar numbers from review queries."""
    cleaned = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", text)
    cleaned = re.sub(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b", "[REDACTED_PHONE]", cleaned)
    cleaned = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", "[REDACTED_AADHAAR]", cleaned)
    return cleaned


@dataclass
class ReviewRecord:
    review_id: str
    created_at: str
    query: str
    canonical_text: str
    intent: str
    confidence: float
    quality_score: float
    source_reliability: float
    evidence_grounding_score: float
    status: str  # "pending" | "approved" | "corrected" | "rejected"
    original_answer: str
    flag_reason: str
    language: str = "en"
    sources: list[str] = field(default_factory=list)
    corrected_answer: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_username: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewRecord:
        allowed = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in allowed}
        rec = cls(**filtered)
        if not rec.language or rec.language == "en":
            if any(ord(c) > 127 for c in rec.query):
                try:
                    from language_detector import detect_language
                    detected = detect_language(rec.query)
                    if detected and detected.get("language_code"):
                        rec.language = detected["language_code"]
                except Exception:
                    pass
        return rec


class HumanReviewManager:
    """Manages evaluation, persistence, and review workflow for agricultural query responses."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = Path(storage_path or DEFAULT_REVIEW_STORAGE_PATH)
        self._reviews: dict[str, ReviewRecord] = {}
        self.load()

    def compute_quality_score(
        self,
        confidence: float,
        sources: list[str],
        retrieved_docs: list[dict[str, Any]],
        is_low_confidence: bool,
    ) -> Tuple[float, float, float]:
        """Compute structured quality score (0.0 to 1.0), source reliability, and evidence grounding."""
        # 1. Source reliability (0.0 to 1.0)
        source_score = 0.30
        if sources:
            official_keywords = ("icar", "ministry", "agmarknet", "pmkisan", "pmfby", "nabard", "krishi")
            matched = any(any(k in s.lower() for k in official_keywords) for s in sources)
            source_score = 0.95 if matched else 0.70

        # 2. Evidence completeness / grounding
        evidence_score = 0.20
        if retrieved_docs:
            top_sim = float(retrieved_docs[0].get("similarity_score", 0.0))
            doc_count = len(retrieved_docs)
            evidence_score = min(1.0, (top_sim * 0.7) + (min(doc_count, 3) * 0.1))

        # 3. Overall quality score
        if is_low_confidence:
            overall = round(max(0.1, min(0.45, (confidence * 0.5) + (evidence_score * 0.5))), 2)
        else:
            overall = round(
                (0.40 * confidence) + (0.35 * source_score) + (0.25 * evidence_score),
                2,
            )
            overall = max(0.0, min(1.0, overall))

        return overall, round(source_score, 2), round(evidence_score, 2)

    def evaluate_and_record(
        self,
        query: str,
        canonical_text: str,
        intent: str,
        confidence: float,
        answer: str,
        sources: list[str],
        retrieved_docs: list[dict[str, Any]],
        is_low_confidence: bool,
    ) -> Optional[ReviewRecord]:
        """Evaluate response quality; if low-confidence or quality < 0.60, stage into pending review queue."""
        quality, source_rel, evidence_score = self.compute_quality_score(
            confidence=confidence,
            sources=sources,
            retrieved_docs=retrieved_docs,
            is_low_confidence=is_low_confidence,
        )

        should_flag = is_low_confidence or (quality < 0.60) or (len(retrieved_docs) == 0)
        if not should_flag:
            return None

        # Build unique deterministic ID
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        h = hashlib.sha256(f"{query}_{ts}".encode()).hexdigest()[:8]
        review_id = f"rev_{h}"

        scrubbed = sanitize_pii_for_review(query)
        flag_reason = (
            "Low retrieval confidence (< 0.40)"
            if is_low_confidence
            else f"Low quality score ({quality} < 0.60)"
        )

        record = ReviewRecord(
            review_id=review_id,
            created_at=ts,
            query=scrubbed,
            canonical_text=canonical_text,
            intent=intent,
            confidence=round(confidence, 3),
            quality_score=quality,
            source_reliability=source_rel,
            evidence_grounding_score=evidence_score,
            status="pending",
            original_answer=answer[:500],
            flag_reason=flag_reason,
        )

        self._reviews[review_id] = record
        self.save()
        logger.info("Created human review record %s (quality=%s, reason=%s)", review_id, quality, flag_reason)
        return record

    def get_pending_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return list of reviews with status 'pending', sorted newest first."""
        pending = [r.to_dict() for r in self._reviews.values() if r.status == "pending"]
        pending.sort(key=lambda x: x["created_at"], reverse=True)
        return pending[:limit]

    def get_review(self, review_id: str) -> Optional[dict[str, Any]]:
        """Retrieve an individual review record by ID."""
        rec = self._reviews.get(review_id)
        return rec.to_dict() if rec else None

    def approve_review(self, review_id: str, notes: Optional[str] = None) -> Tuple[bool, str]:
        """Mark a review record as approved by human reviewer."""
        if review_id not in self._reviews:
            return False, f"Review '{review_id}' not found."
        rec = self._reviews[review_id]
        rec.status = "approved"
        rec.reviewer_notes = notes or "Approved as compliant with agricultural safety standards."
        rec.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()
        return True, "Review approved successfully."

    def reject_review(self, review_id: str, reason: Optional[str] = None) -> Tuple[bool, str]:
        """Mark a review record as rejected."""
        if review_id not in self._reviews:
            return False, f"Review '{review_id}' not found."
        rec = self._reviews[review_id]
        rec.status = "rejected"
        rec.reviewer_notes = reason or "Rejected due to unverified recommendation."
        rec.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()
        return True, "Review rejected."

    def correct_review(
        self,
        review_id: str,
        corrected_answer: str,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Record human correction for an answer."""
        if review_id not in self._reviews:
            return False, f"Review '{review_id}' not found."
        if not corrected_answer or not corrected_answer.strip():
            return False, "Corrected answer cannot be empty."
        rec = self._reviews[review_id]
        rec.status = "corrected"
        rec.corrected_answer = corrected_answer.strip()
        rec.reviewer_notes = notes or "Corrected by agricultural extension expert."
        rec.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.save()
        return True, "Correction saved successfully."

    def get_stats(self) -> dict[str, int]:
        """Return counts of reviews by status."""
        stats = {"total": len(self._reviews), "pending": 0, "approved": 0, "corrected": 0, "rejected": 0}
        for r in self._reviews.values():
            if r.status in stats:
                stats[r.status] += 1
        return stats

    def list_queries(
        self,
        status: Optional[str] = None,
        language: Optional[str] = None,
        intent: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List unanswered and flagged queries with filtering, searching, and pagination."""
        records = list(self._reviews.values())

        if status and status.lower() not in ("all", ""):
            st = status.lower()
            records = [r for r in records if r.status == st]

        if language and language.lower() not in ("all", ""):
            lang = language.lower()
            records = [r for r in records if (r.language or "en").lower() == lang]

        if intent and intent.lower() not in ("all", ""):
            it = intent.lower()
            records = [r for r in records if (r.intent or "").lower() == it]

        if search and search.strip():
            kw = search.strip().lower()
            records = [
                r for r in records
                if kw in r.query.lower()
                or kw in r.canonical_text.lower()
                or kw in r.original_answer.lower()
                or kw in r.review_id.lower()
                or (r.flag_reason and kw in r.flag_reason.lower())
            ]

        if start_date:
            sd = start_date.strip()
            records = [r for r in records if r.created_at[:10] >= sd]
        if end_date:
            ed = end_date.strip()
            records = [r for r in records if r.created_at[:10] <= ed]

        records.sort(key=lambda x: x.created_at, reverse=True)

        total = len(records)
        safe_limit = max(1, min(100, limit))
        safe_offset = max(0, offset)
        paged = records[safe_offset : safe_offset + safe_limit]

        return {
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "stats": self.get_stats(),
            "queries": [r.to_dict() for r in paged],
        }

    def update_review(
        self,
        review_id: str,
        status: str,
        reviewer_notes: Optional[str] = None,
        corrected_answer: Optional[str] = None,
        reviewer_username: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[dict[str, Any]]]:
        """Update review status, expert notes, and optional corrected answer."""
        if review_id not in self._reviews:
            return False, f"Review '{review_id}' not found.", None

        valid_statuses = ("approved", "rejected", "corrected", "pending")
        target_status = status.lower()
        if target_status not in valid_statuses:
            return False, f"Invalid review status '{status}'. Must be one of {valid_statuses}.", None

        rec = self._reviews[review_id]

        if target_status == "corrected":
            if not corrected_answer or not corrected_answer.strip():
                return False, "corrected_answer is required when status is 'corrected'.", None
            rec.corrected_answer = corrected_answer.strip()
            default_notes = "Corrected by agricultural extension expert."
        elif target_status == "approved":
            default_notes = "Approved as compliant with agricultural safety standards."
        elif target_status == "rejected":
            default_notes = "Rejected due to unverified recommendation."
        else:
            default_notes = None

        rec.status = target_status
        rec.reviewer_notes = reviewer_notes.strip() if (reviewer_notes and reviewer_notes.strip()) else default_notes
        rec.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if reviewer_username:
            rec.reviewer_username = reviewer_username

        self.save()
        return True, f"Review '{review_id}' marked as {target_status}.", rec.to_dict()

    def save(self) -> bool:
        """Persist review records to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "_last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "count": len(self._reviews),
                "reviews": [r.to_dict() for r in self._reviews.values()],
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error("Failed to save human reviews to %s: %s", self.storage_path, exc)
            return False

    def load(self) -> bool:
        """Load review records from disk."""
        if not self.storage_path.exists():
            return False
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                reviews_list = data.get("reviews", [])
                for item in reviews_list:
                    rec = ReviewRecord.from_dict(item)
                    self._reviews[rec.review_id] = rec
            return True
        except Exception as exc:
            logger.warning("Could not load human reviews from %s: %s", self.storage_path, exc)
            return False


# Singleton review manager instance
review_manager = HumanReviewManager()

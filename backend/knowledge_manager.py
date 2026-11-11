"""Knowledge Base Management Service for Smart Farming Assistant.

Coordinates:
  1. Authoritative persistent dataset (data/ingested_knowledge.json via DataIngestionPipeline)
  2. In-memory semantic and hybrid retrieval corpus (KnowledgeRepository)
  3. Persistent vector database (ChromaDB or Local NumPy vector store via RAGPipeline)

Provides atomic CRUD operations, vector chunk synchronization, controlled re-indexing,
and safe document text extraction with pre-ingestion preview.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

from data_ingestion import (
    AgriculturalRecord,
    DataIngestionPipeline,
    validate_document,
    normalize_document,
    compute_record_fingerprint,
    extract_text_from_pdf,
    parse_text_or_markdown_document,
    VALID_CATEGORIES,
)
from knowledge_repository import (
    knowledge_repository,
    KnowledgeDocument,
    SourceAttribution,
)
from vector_store import chunk_agricultural_document, VectorDocumentChunk

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".json"}


def agricultural_record_to_knowledge_doc(rec: AgriculturalRecord) -> KnowledgeDocument:
    """Convert an AgriculturalRecord into a KnowledgeDocument for hybrid search."""
    ver_date = "2026-03"
    if rec.retrieval_timestamp:
        try:
            ver_date = rec.retrieval_timestamp[:7]
        except Exception:
            ver_date = "2026-03"

    return KnowledgeDocument(
        doc_id=rec.doc_id,
        category=rec.category,
        title=rec.title,
        sub_category=rec.sub_category or "",
        crops_applicable=list(rec.crops_applicable or []),
        soil_types_applicable=list(rec.soil_types_applicable or []),
        nutrients_applicable=list(rec.nutrients_applicable or []),
        seasons_applicable=list(rec.seasons_applicable or []),
        tags=list(rec.tags or []),
        content_en=rec.content_en or "",
        content_hi=rec.content_hi or "",
        content_ta=rec.content_ta or "",
        content_kn=rec.content_kn or "",
        source=SourceAttribution(
            name=rec.source_name or "ICAR / Government of India",
            organization=rec.organization or "Agricultural Department",
            official_url=rec.official_url or "https://icar.gov.in",
            verified_date=ver_date,
            access_note=rec.access_note or f"Ingested official document ({rec.verification_status}).",
        ),
        guardrail_notice=rec.guardrail_notice or "",
    )


class KnowledgeBaseManager:
    """Unified service orchestrating knowledge storage and vector store synchronization."""

    def __init__(self, pipeline: Optional[DataIngestionPipeline] = None) -> None:
        self.pipeline = pipeline or DataIngestionPipeline()
        if len(self.pipeline) == 0:
            self.pipeline.initialize_default_dataset()

    @property
    def vector_store(self):
        """Lazy accessor for the active RAG vector store."""
        from rag_pipeline import rag_pipeline
        return rag_pipeline.vector_store

    def list_records(
        self,
        category: Optional[str] = None,
        crop: Optional[str] = None,
        language: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List knowledge records with multi-factor filtering, search, and pagination."""
        all_records = self.pipeline.get_all_records()

        # Compute summary stats across complete dataset
        category_counts: dict[str, int] = {}
        crops_counter: dict[str, int] = {}
        for r in all_records:
            cat = r.category or "other"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            for c in r.crops_applicable:
                norm_c = c.strip().lower()
                if norm_c:
                    crops_counter[norm_c] = crops_counter.get(norm_c, 0) + 1

        top_crops = sorted(crops_counter.keys(), key=lambda k: crops_counter[k], reverse=True)[:10]

        # Apply filters
        filtered: list[AgriculturalRecord] = []
        for r in all_records:
            if category and category != "all" and r.category.lower() != category.lower():
                continue

            if crop and crop != "all":
                c_match = any(crop.lower() == c.lower() for c in r.crops_applicable)
                if not c_match:
                    continue

            if language and language != "all":
                lang_code = language.lower()
                content = getattr(r, f"content_{lang_code}", "")
                if not content or not content.strip():
                    continue

            if source and source != "all":
                src_lower = source.lower()
                org_match = src_lower in (r.organization or "").lower()
                name_match = src_lower in (r.source_name or "").lower()
                if not (org_match or name_match):
                    continue

            if search and search.strip():
                terms = search.strip().lower().split()
                searchable_text = (
                    f"{r.title} {r.category} {r.sub_category} {r.doc_id} "
                    f"{' '.join(r.crops_applicable)} {' '.join(r.tags)} "
                    f"{r.content_en} {r.content_hi} {r.content_kn} {r.content_ta} "
                    f"{r.source_name} {r.organization}"
                ).lower()
                if not all(term in searchable_text for term in terms):
                    continue

            filtered.append(r)

        total_matching = len(filtered)
        paged_records = filtered[offset : offset + limit]

        # Check sync status
        vs_count = self.vector_store.count()
        backend_name = getattr(self.vector_store, "backend_name", "unknown")

        return {
            "records": [rec.to_dict() for rec in paged_records],
            "total": total_matching,
            "limit": limit,
            "offset": offset,
            "stats": {
                "total_records": len(all_records),
                "matching_records": total_matching,
                "category_counts": category_counts,
                "top_crops": top_crops,
                "vector_chunks": vs_count,
                "vector_backend": backend_name,
                "in_sync": vs_count >= len(all_records),
            },
        }

    def get_record(self, doc_id: str) -> Optional[dict[str, Any]]:
        """Retrieve full details of a specific agricultural record."""
        rec = self.pipeline.get_record(doc_id)
        if not rec:
            return None
        return rec.to_dict()

    def create_record(self, data: dict[str, Any]) -> Tuple[bool, str, Optional[dict[str, Any]]]:
        """Create a new verified agricultural record and synchronize vector store."""
        # 1. Generate unique doc_id if not supplied
        if not data.get("doc_id") or not str(data.get("doc_id")).strip():
            cat = str(data.get("category", "practice")).strip()[:4]
            timestamp = int(time.time())
            data["doc_id"] = f"doc_{cat}_{timestamp}"

        doc_id = str(data["doc_id"]).strip()

        # Supply sensible defaults for optional fields so validation succeeds
        if not data.get("guardrail_notice"):
            data["guardrail_notice"] = "Follow package of practices and verify with local agricultural extension officer."
        if not data.get("source_name"):
            data["source_name"] = "ICAR / Government of India"
        if not data.get("organization"):
            data["organization"] = "Agricultural Department"
        if not data.get("official_url"):
            data["official_url"] = "https://icar.gov.in"
        if not data.get("sub_category"):
            data["sub_category"] = "general"

        # 2. Check if doc_id already exists
        if self.pipeline.get_record(doc_id):
            return False, f"Record with doc_id '{doc_id}' already exists.", None

        # 3. Validation
        is_valid, errors = validate_document(data)
        if not is_valid:
            return False, f"Validation failed: {'; '.join(errors)}", None

        # 4. Ingest and persist in DataIngestionPipeline
        try:
            norm_rec = normalize_document(data)
            success, msg = self.pipeline.ingest(norm_rec, overwrite=False)
            if not success:
                return False, msg, None
            self.pipeline.save_dataset()
        except Exception as exc:
            logger.error("Failed to persist new knowledge record '%s': %s", doc_id, exc)
            return False, f"Storage error: {exc}", None

        # 5. Synchronize in-memory knowledge repository
        try:
            kdoc = agricultural_record_to_knowledge_doc(norm_rec)
            knowledge_repository.upsert_document(kdoc)
        except Exception as exc:
            logger.warning("Failed to update in-memory knowledge repository: %s", exc)

        # 6. Synchronize vector store
        try:
            chunks = chunk_agricultural_document(norm_rec, chunk_size_words=80, overlap_words=20)
            added_chunks = self.vector_store.add_chunks(chunks)
            logger.info("Synchronized %d chunks for doc_id '%s' in vector store.", added_chunks, doc_id)
        except Exception as exc:
            logger.error("Vector store synchronization failed for doc_id '%s': %s", doc_id, exc)
            # Rollback record
            self.pipeline.delete_record(doc_id)
            knowledge_repository.delete_document(doc_id)
            return False, f"Vector store synchronization failed: {exc}", None

        return True, "Agricultural record created and synchronized with vector store.", norm_rec.to_dict()

    def update_record(self, doc_id: str, data: dict[str, Any]) -> Tuple[bool, str, Optional[dict[str, Any]]]:
        """Update an existing agricultural record and re-synchronize vector chunks."""
        existing = self.pipeline.get_record(doc_id)
        if not existing:
            return False, f"Record '{doc_id}' not found.", None

        # Merge updates onto existing record, protecting primary ID
        merged = existing.to_dict()
        for k, v in data.items():
            if k == "doc_id":
                continue
            if v is not None:
                merged[k] = v

        merged["retrieval_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Validation
        is_valid, errors = validate_document(merged)
        if not is_valid:
            return False, f"Validation failed: {'; '.join(errors)}", None

        # Update in pipeline
        try:
            updated_rec = normalize_document(merged)
            self.pipeline._records[doc_id] = updated_rec
            self.pipeline.save_dataset()
        except Exception as exc:
            logger.error("Failed to update knowledge record '%s': %s", doc_id, exc)
            return False, f"Storage error: {exc}", None

        # Update in-memory knowledge repo
        try:
            kdoc = agricultural_record_to_knowledge_doc(updated_rec)
            knowledge_repository.upsert_document(kdoc)
        except Exception as exc:
            logger.warning("Failed to update in-memory knowledge repository: %s", exc)

        # Re-synchronize vector chunks: remove outdated chunks and add fresh chunks
        try:
            deleted_old = self.vector_store.delete_chunks_by_doc_id(doc_id)
            new_chunks = chunk_agricultural_document(updated_rec, chunk_size_words=80, overlap_words=20)
            added_new = self.vector_store.add_chunks(new_chunks)
            logger.info("Updated doc '%s': replaced %d old chunks with %d new chunks.", doc_id, deleted_old, added_new)
        except Exception as exc:
            logger.error("Vector store re-synchronization failed for doc '%s': %s", doc_id, exc)
            return False, f"Vector store re-indexing error: {exc}", None

        return True, "Agricultural record updated and re-indexed in vector store.", updated_rec.to_dict()

    def delete_record(self, doc_id: str) -> Tuple[bool, str, int]:
        """Delete an agricultural record and purge all associated vector chunks."""
        existing = self.pipeline.get_record(doc_id)
        if not existing:
            return False, f"Record '{doc_id}' not found.", 0

        # 1. Delete from pipeline & dataset file
        deleted_from_dataset = self.pipeline.delete_record(doc_id)
        if not deleted_from_dataset:
            return False, f"Failed to remove record '{doc_id}' from dataset.", 0

        # 2. Delete from in-memory knowledge repository
        knowledge_repository.delete_document(doc_id)

        # 3. Purge chunks from vector database
        deleted_chunks = 0
        try:
            deleted_chunks = self.vector_store.delete_chunks_by_doc_id(doc_id)
            logger.info("Purged %d chunks for deleted doc '%s' from vector store.", deleted_chunks, doc_id)
        except Exception as exc:
            logger.warning("Error purging chunks for doc '%s' from vector store: %s", doc_id, exc)

        return True, f"Record '{doc_id}' deleted and {deleted_chunks} vector chunks purged.", deleted_chunks

    def reindex_all(self) -> dict[str, Any]:
        """Controlled re-indexing: clears vector store and regenerates chunks for all knowledge records."""
        start_time = time.perf_counter()
        records = self.pipeline.get_all_records()

        # Clear vector store
        self.vector_store.clear()

        # Re-chunk all documents
        all_chunks: list[VectorDocumentChunk] = []
        for rec in records:
            chunks = chunk_agricultural_document(rec, chunk_size_words=80, overlap_words=20)
            all_chunks.extend(chunks)

        indexed_count = 0
        if all_chunks:
            indexed_count = self.vector_store.add_chunks(all_chunks)

        # Ensure in-memory knowledge repo matches records
        for rec in records:
            kdoc = agricultural_record_to_knowledge_doc(rec)
            knowledge_repository.upsert_document(kdoc)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        backend_name = getattr(self.vector_store, "backend_name", "unknown")

        logger.info(
            "Re-indexed %d records (%d chunks) into %s in %.2fms",
            len(records),
            indexed_count,
            backend_name,
            duration_ms,
        )

        return {
            "status": "completed",
            "records_processed": len(records),
            "chunks_indexed": indexed_count,
            "duration_ms": duration_ms,
            "backend": backend_name,
        }

    def get_sync_status(self) -> dict[str, Any]:
        """Report synchronization health between authoritative knowledge base and vector store."""
        records = self.pipeline.get_all_records()
        vs_count = self.vector_store.count()
        backend_name = getattr(self.vector_store, "backend_name", "unknown")

        # Extract distinct categories and crops
        categories = sorted(list({r.category for r in records if r.category}))
        all_crops = set()
        for r in records:
            all_crops.update(r.crops_applicable)
        crops = sorted(list(all_crops))

        return {
            "backend": backend_name,
            "total_records": len(records),
            "total_chunks": vs_count,
            "is_synchronized": vs_count > 0 and vs_count >= len(records),
            "categories": categories,
            "crops": crops,
            "languages_supported": ["en", "hi", "kn", "ta"],
            "storage_directory": str(getattr(self.vector_store, "storage_dir", "default")),
        }

    def preview_document_upload(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> Tuple[bool, str, dict[str, Any]]:
        """Safely parse uploaded document and return extracted text and suggested metadata for preview."""
        # Clean filename against path traversal
        clean_name = Path(filename).name
        ext = Path(clean_name).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}", {}

        if len(file_bytes) == 0:
            return False, "Uploaded file is empty (0 bytes).", {}

        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            return False, f"File exceeds maximum upload size limit ({max_mb} MB).", {}

        extracted_text = ""
        metadata: dict[str, Any] = {}

        try:
            if ext == ".pdf":
                # Write to safe temporary file for parser
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = Path(tmp.name)
                try:
                    extracted_text = extract_text_from_pdf(tmp_path)
                finally:
                    tmp_path.unlink(missing_ok=True)

            elif ext in (".txt", ".md"):
                raw_str = file_bytes.decode("utf-8", errors="replace")
                extracted_text, metadata = parse_text_or_markdown_document(raw_str)

            elif ext == ".json":
                import json
                parsed = json.loads(file_bytes.decode("utf-8", errors="replace"))
                if isinstance(parsed, dict):
                    extracted_text = parsed.get("content_en") or parsed.get("content") or ""
                    metadata = {k: v for k, v in parsed.items() if k not in ("content_en", "content")}
                elif isinstance(parsed, list) and parsed:
                    first = parsed[0]
                    extracted_text = first.get("content_en") or first.get("content") or ""
                    metadata = first
        except Exception as exc:
            logger.error("Failed to parse uploaded document '%s': %s", clean_name, exc)
            return False, f"Document parsing error: {exc}", {}

        if not extracted_text.strip():
            return False, "No readable text content could be extracted from the document.", {}

        # Heuristic title and category suggestions
        suggested_title = metadata.get("title")
        if not suggested_title:
            first_line = extracted_text.strip().splitlines()[0].strip("# ").strip()
            suggested_title = first_line[:100] if len(first_line) > 5 else Path(clean_name).stem.replace("_", " ").title()

        suggested_cat = metadata.get("category")
        if not suggested_cat or suggested_cat not in VALID_CATEGORIES:
            text_lower = extracted_text.lower()
            if any(k in text_lower for k in ("disease", "fungus", "rot", "blight", "wilt", "mildew", "virus", "mosaic")):
                suggested_cat = "diseases"
            elif any(k in text_lower for k in ("pest", "insect", "caterpillar", "borer", "whitefly", "aphid")):
                suggested_cat = "pests"
            elif any(k in text_lower for k in ("soil", "nitrogen", "phosphorus", "potash", "ph", "fertilizer")):
                suggested_cat = "soil"
            elif any(k in text_lower for k in ("scheme", "subsidy", "yojana", "pm-kisan", "pmfby")):
                suggested_cat = "government_schemes"
            elif any(k in text_lower for k in ("mandi", "price", "apmc", "msp", "market")):
                suggested_cat = "market_prices"
            elif any(k in text_lower for k in ("paddy", "wheat", "cotton", "maize", "mustard", "chickpea", "seed")):
                suggested_cat = "crops"
            else:
                suggested_cat = "farming_practices"

        words = extracted_text.split()
        return True, "Document extracted successfully for review.", {
            "filename": clean_name,
            "file_type": ext,
            "word_count": len(words),
            "character_count": len(extracted_text),
            "extracted_text": extracted_text[:10000],  # Bound preview length
            "suggested_title": suggested_title,
            "suggested_category": suggested_cat,
            "suggested_crops": metadata.get("crops_applicable", []),
            "metadata": metadata,
            "notice": "Preview only. Review and adjust metadata before submitting to authoritative knowledge base.",
        }


# Module singleton
knowledge_base_manager = KnowledgeBaseManager()

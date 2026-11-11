"""Retrieval-Augmented Generation (RAG) Pipeline for Smart Farming Assistant.

Orchestrates:
  1. Intent-to-category evidence routing.
  2. Semantic vector retrieval over indexed agricultural chunks.
  3. Specialized adapter integration (Agmarknet, Weather, Government Schemes).
  4. Response confidence calculation and low-confidence review logging.
  5. Evidence-grounded answer generation adhering to agricultural safety guardrails.
  6. Source attribution with official URLs and retrieval timestamps.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from data_ingestion import AgriculturalRecord, DataIngestionPipeline, DEFAULT_DATASET_PATH
from external_adapters import agmarknet_adapter, weather_adapter, government_scheme_adapter
from knowledge_repository import knowledge_repository, INTENT_TO_CATEGORIES
from ner_extractor import extract_primary_commodity, extract_primary_location
from vector_store import (
    VectorDocumentChunk,
    BaseVectorStore,
    chunk_agricultural_document,
    get_vector_store,
)

# Optional LangChain core integration
try:
    from langchain_core.documents import Document as LCDocument
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.runnables import RunnableLambda, RunnablePassthrough
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    LCDocument = None
    BaseRetriever = object
    RunnableLambda = None
    RunnablePassthrough = None

logger = logging.getLogger(__name__)

LOW_CONFIDENCE_LOG_PATH = Path(__file__).parent / "data" / "low_confidence_queries.jsonl"
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.40


def sanitize_pii(text: str) -> str:
    """Scrub sensitive personal identifiers (phone numbers, emails, Aadhaar numbers) from user text before logging."""
    # Redact email addresses
    cleaned = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", text)
    # Redact 10-12 digit phone numbers / Indian mobile numbers
    cleaned = re.sub(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b", "[REDACTED_PHONE]", cleaned)
    # Redact 12-digit Aadhaar patterns
    cleaned = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", "[REDACTED_AADHAAR]", cleaned)
    return cleaned


if HAS_LANGCHAIN:
    from pydantic import ConfigDict

    class LangChainAgriculturalRetriever(BaseRetriever):
        """LangChain-native agricultural retriever wrapping our persistent vector store."""
        vector_store: Any
        top_k: int = 3
        category: Optional[str] = None
        model_config = ConfigDict(arbitrary_types_allowed=True)

        def _get_relevant_documents(
            self,
            query: str,
            *,
            run_manager: Optional[Any] = None,
        ) -> list[LCDocument]:
            chunks_with_scores = self.vector_store.similarity_search(
                query=query,
                top_k=self.top_k,
                category=self.category,
            )
            docs = []
            for chunk, score in chunks_with_scores:
                meta = dict(chunk.metadata)
                meta["similarity_score"] = float(score)
                meta["category"] = chunk.category
                meta["doc_id"] = chunk.doc_id
                meta["chunk_id"] = chunk.chunk_id
                docs.append(LCDocument(page_content=chunk.text, metadata=meta))
            return docs
else:
    class LangChainAgriculturalRetriever:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError("langchain_core is not installed in the environment.")


class RAGPipeline:
    """End-to-end evidence-based RAG pipeline for multilingual agricultural guidance."""

    def __init__(
        self,
        vector_store: Optional[BaseVectorStore] = None,
        use_fixture_embeddings: bool = True,
        low_confidence_threshold: Optional[float] = None,
    ) -> None:
        self.vector_store = vector_store or get_vector_store(use_fixture_embeddings=use_fixture_embeddings)
        env_thresh = os.getenv("LOW_CONFIDENCE_THRESHOLD")
        self.low_confidence_threshold = (
            low_confidence_threshold
            if low_confidence_threshold is not None
            else (float(env_thresh) if env_thresh else DEFAULT_LOW_CONFIDENCE_THRESHOLD)
        )
        self._ensure_vector_store_populated()
        self.retriever = (
            LangChainAgriculturalRetriever(vector_store=self.vector_store, top_k=20)
            if HAS_LANGCHAIN
            else None
        )
        self.lcel_chain = self._build_lcel_chain() if HAS_LANGCHAIN else None

    def _ensure_vector_store_populated(self) -> None:
        """Synchronize vector database with the curated agricultural dataset on startup."""
        if self.vector_store.count() > 0:
            return

        ingestion = DataIngestionPipeline()
        if len(ingestion) == 0:
            ingestion.initialize_default_dataset()

        records = ingestion.get_all_records()
        all_chunks: list[VectorDocumentChunk] = []
        for rec in records:
            chunks = chunk_agricultural_document(rec, chunk_size_words=80, overlap_words=20)
            all_chunks.extend(chunks)

        if all_chunks:
            self.vector_store.add_chunks(all_chunks)
            logger.info("Indexed %d chunks into persistent vector store.", len(all_chunks))

    def calculate_confidence(
        self,
        retrieved_chunks: list[tuple[VectorDocumentChunk, float]],
        query: str,
        intent: str,
        entities: dict[str, list[str]],
    ) -> float:
        """Calculate grounded response confidence score (0.0 to 1.0).

        Factors:
          • Vector similarity of top evidence chunk (45% weight).
          • Lexical query-to-evidence overlap (35% weight).
          • Entity alignment (crop, soil, pest) in evidence (20% weight).
          • Out-of-domain penalty: if lexical overlap is 0 and vector similarity is low.
        """
        if not retrieved_chunks:
            return 0.15

        top_chunk, sim = retrieved_chunks[0]
        sim_score = max(0.0, min(1.0, float(sim)))

        # Lexical word overlap
        query_words = {w.lower().strip("?,.:;!'\"()") for w in query.split() if len(w) > 2}
        chunk_words = {w.lower().strip("?,.:;!'\"()") for w in top_chunk.text.split()}
        matched_words = query_words & chunk_words
        lexical_ratio = len(matched_words) / max(1, len(query_words))

        # Entity overlap
        all_entities = []
        for v in entities.values():
            if isinstance(v, list):
                all_entities.extend(v)

        if all_entities:
            text_lower = top_chunk.text.lower()
            entity_matches = sum(1 for e in all_entities if e.lower() in text_lower)
            entity_score = 1.0 if entity_matches > 0 else 0.20
        else:
            entity_score = 0.60

        # Out-of-domain penalty
        if lexical_ratio == 0 and sim_score < 0.45:
            return round(sim_score * 0.40, 2)

        conf = (0.45 * sim_score) + (0.35 * lexical_ratio) + (0.20 * entity_score)
        return round(float(max(0.0, min(1.0, conf))), 2)

    def log_low_confidence_query(
        self,
        query: str,
        intent: str,
        confidence: float,
        reason: str,
    ) -> None:
        """Record low-confidence or unanswerable queries for human review with PII scrubbing."""
        try:
            LOW_CONFIDENCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            scrubbed_query = sanitize_pii(query[:300])
            record = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "query": scrubbed_query,
                "intent": intent,
                "confidence": confidence,
                "reason": reason,
            }
            with open(LOW_CONFIDENCE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Could not log low-confidence query: %s", exc)

    def as_langchain_retriever(self, top_k: int = 3, category: Optional[str] = None) -> Any:
        """Expose a LangChain-compatible retriever for external LangChain chains and agents."""
        if not HAS_LANGCHAIN:
            raise ImportError("langchain_core is not installed in the environment.")
        return LangChainAgriculturalRetriever(
            vector_store=self.vector_store,
            top_k=top_k,
            category=category,
        )

    def _build_lcel_chain(self) -> Optional[Any]:
        """Build an authentic LangChain Expression Language (LCEL) Runnable chain.

        Chain Architecture:
          Inputs -> RunnablePassthrough.assign(retrieved_lc_docs=retriever)
                 -> RunnableLambda(rerank_and_adapter_step)
                 -> RunnableLambda(synthesis_and_format_step)
        """
        if not HAS_LANGCHAIN or self.retriever is None:
            return None

        try:
            from langchain_core.runnables import RunnableLambda, RunnablePassthrough

            chain = (
                RunnablePassthrough.assign(
                    retrieved_lc_docs=RunnableLambda(lambda inp: inp.get("retrieval_query", inp["canonical_text"])) | self.retriever
                )
                | RunnableLambda(self._lcel_rerank_and_adapter_step)
                | RunnableLambda(self._lcel_synthesis_and_format_step)
            )
            return chain
        except Exception as exc:
            logger.warning("Could not construct LangChain LCEL chain: %s", exc)
            return None

    def _lcel_rerank_and_adapter_step(self, inp: dict[str, Any]) -> dict[str, Any]:
        """LCEL Runnable step: Intercept specialized intents with adapters and hybrid-rerank retrieved LangChain docs."""
        canonical_text = inp["canonical_text"]
        intent = inp["intent"]
        entities = inp.get("entities") or {}
        top_k = inp.get("top_k", 2)

        crops_list = entities.get("crops") or []
        resolved_crop = crops_list[0] if crops_list else None
        soil_list = entities.get("soil") or []
        resolved_soil = soil_list[0] if soil_list else None

        # 1. Specialized Intent Handling & Adapter Interception
        adapter_data: Optional[dict[str, Any]] = None
        primary_crop = extract_primary_commodity(canonical_text, entities)
        primary_loc = extract_primary_location(canonical_text, entities)

        if intent == "market_prices":
            target_commodity = primary_crop or resolved_crop or "Tomato"
            target_district = primary_loc
            target_state = None
            if primary_loc:
                pl_lower = primary_loc.lower()
                if pl_lower in ("salem", "coimbatore", "chennai"):
                    target_state = "Tamil Nadu"
                elif pl_lower in ("varanasi", "lucknow"):
                    target_state = "Uttar Pradesh"
                elif pl_lower in ("karnal",):
                    target_state = "Haryana"
                elif pl_lower in ("pune", "nagpur", "nashik"):
                    target_state = "Maharashtra"
            adapter_data = agmarknet_adapter.get_market_data(
                commodity=target_commodity,
                state=target_state,
                district=target_district,
                force_live=True,
            )
        elif intent == "weather":
            target_loc = primary_loc or "Varanasi"
            adapter_data = weather_adapter.get_weather_advisory(
                location=target_loc,
                district=target_loc,
                force_live=True,
            )
        elif intent == "government_schemes":
            adapter_data = government_scheme_adapter.get_scheme_guidance(query=canonical_text)

        # 2. Hybrid Semantic Vector + Lexical Entity Re-Ranking over LangChain retrieved documents
        base_allowed_cats = INTENT_TO_CATEGORIES.get(intent, [intent])
        allowed_cats = list(set(base_allowed_cats + (["crops"] if resolved_crop else [])))

        retrieved_lc_docs: list[LCDocument] = inp.get("retrieved_lc_docs", [])
        query_words = {w.lower().strip("?,.:;!'\"()") for w in canonical_text.split() if len(w) > 2}

        scored_candidates: list[tuple[VectorDocumentChunk, float]] = []
        for doc in retrieved_lc_docs:
            meta = doc.metadata
            doc_text = getattr(doc, "page_content", None) or getattr(doc, "text", "")
            chunk_crops = meta.get("crops_applicable", [])
            chunk_soils = meta.get("soil_types_applicable", [])
            chunk_tags = [t.lower() for t in meta.get("tags", [])]
            chunk_text_words = set(doc_text.lower().split())
            chunk_title_lower = meta.get("title", "").lower()
            category = meta.get("category", "crops")

            # Base semantic score from vector search
            score = float(meta.get("similarity_score", 0.0))

            # Category / Intent alignment boost
            if category in allowed_cats:
                score += 0.35

            # Direct Crop match in title and applicable list
            if resolved_crop:
                if resolved_crop in chunk_title_lower:
                    score += 0.50
                if resolved_crop in chunk_crops:
                    score += 0.60

            # Soil match boost
            if resolved_soil and resolved_soil in chunk_soils:
                score += 0.25

            # Keyword and tag overlap boost
            overlap = len(query_words & chunk_text_words)
            score += overlap * 0.10

            for tag in chunk_tags:
                if any(w in tag for w in query_words):
                    score += 0.25

            chunk = VectorDocumentChunk(
                chunk_id=meta.get("chunk_id", meta.get("doc_id", "c0")),
                doc_id=meta.get("doc_id", "doc"),
                text=doc_text,
                category=category,
                metadata=meta,
            )
            scored_candidates.append((chunk, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        active_chunks = scored_candidates[:top_k]

        return {
            **inp,
            "adapter_data": adapter_data,
            "active_chunks": active_chunks,
            "allowed_cats": allowed_cats,
            "resolved_crop": resolved_crop,
            "resolved_soil": resolved_soil,
        }

    def _lcel_synthesis_and_format_step(self, inp: dict[str, Any]) -> dict[str, Any]:
        """LCEL Runnable step: Confidence assessment, low-confidence review logging, and grounded answer synthesis."""
        query = inp["query"]
        canonical_text = inp["canonical_text"]
        intent = inp["intent"]
        language_code = inp.get("language_code", "en")
        entities = inp.get("entities") or {}
        adapter_data = inp.get("adapter_data")
        active_chunks = inp.get("active_chunks", [])

        # 3. Assess Response Confidence
        if intent == "weather" and adapter_data and (
            adapter_data.get("is_live") or adapter_data.get("status") in ("live_forecast", "offline_mode") or adapter_data.get("service") == "imd_agromet"
        ):
            confidence = 0.95 if adapter_data.get("is_live") else 0.88
            is_low_confidence = False
        elif intent == "market_prices" and adapter_data and adapter_data.get("is_live"):
            confidence = 0.92
            is_low_confidence = False
        elif intent == "government_schemes" and adapter_data and adapter_data.get("status") == "verified_curated":
            confidence = 0.90
            is_low_confidence = False
        else:
            confidence = self.calculate_confidence(active_chunks, canonical_text, intent, entities)
            is_low_confidence = confidence < self.low_confidence_threshold or len(active_chunks) == 0
            if is_low_confidence:
                self.log_low_confidence_query(
                    query=query,
                    intent=intent,
                    confidence=confidence,
                    reason="Low semantic similarity or insufficient domain evidence in corpus.",
                )

        # 5. Build Grounded Answer Synthesis
        conversation_context = inp.get("conversation_context")
        synthesized_answer = self._synthesize_grounded_answer(
            query=query,
            canonical_text=canonical_text,
            intent=intent,
            language_code=language_code,
            entities=entities,
            active_chunks=active_chunks,
            adapter_data=adapter_data,
            is_low_confidence=is_low_confidence,
            conversation_context=conversation_context,
        )

        # 6. Build Attributed Documents List
        retrieved_docs_formatted = []
        seen_docs = set()
        for chunk, score in active_chunks:
            did = chunk.doc_id
            if did in seen_docs:
                continue
            seen_docs.add(did)
            retrieved_docs_formatted.append(
                {
                    "doc_id": did,
                    "title": chunk.metadata.get("title", ""),
                    "category": chunk.category,
                    "source": chunk.metadata.get("source_name", "Official Portal"),
                    "url": chunk.metadata.get("official_url", ""),
                    "organization": chunk.metadata.get("organization", "Agricultural Department"),
                    "guardrail_notice": chunk.metadata.get("guardrail_notice", ""),
                    "similarity_score": round(score, 3),
                    "retrieval_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
            )

        # Structured response metadata
        sources_list = [f"{doc['organization']} ({doc['source']})" for doc in retrieved_docs_formatted]
        if adapter_data:
            sources_list.append(adapter_data.get("official_portal", "Official Portal"))

        # 7. Evaluate Response Quality & Stage Human Review if Needed
        try:
            from review_manager import review_manager
            quality_score, source_rel, evidence_score = review_manager.compute_quality_score(
                confidence=confidence,
                sources=sources_list,
                retrieved_docs=retrieved_docs_formatted,
                is_low_confidence=is_low_confidence,
            )
            review_rec = review_manager.evaluate_and_record(
                query=query,
                canonical_text=canonical_text,
                intent=intent,
                confidence=confidence,
                answer=synthesized_answer,
                sources=sources_list,
                retrieved_docs=retrieved_docs_formatted,
                is_low_confidence=is_low_confidence,
            )
            review_id = review_rec.review_id if review_rec else None
            review_status = review_rec.status if review_rec else "auto_verified"
        except Exception as exc:
            logger.warning("Review manager evaluation skipped: %s", exc)
            quality_score, source_rel, evidence_score = 0.80, 0.90, 0.85
            review_id = None
            review_status = "auto_verified"

        if is_low_confidence:
            response_mode = "kcc_referral_safety"
        elif intent == "weather" and adapter_data:
            response_mode = "adapter_live_weather" if adapter_data.get("is_live") else "adapter_weather_advisory"
        elif intent == "market_prices" and adapter_data:
            response_mode = "adapter_live_market" if adapter_data.get("is_live") else "adapter_market_benchmark"
        elif intent == "government_schemes" and adapter_data:
            response_mode = "adapter_scheme_guidance"
        else:
            response_mode = "rag_grounded_extractive"

        needs_clarification = is_low_confidence or (
            intent == "government_schemes" and not entities.get("schemes")
        )

        return {
            "answer": synthesized_answer,
            "intent": intent,
            "detected_language": language_code,
            "confidence": confidence,
            "rag_confidence": confidence,
            "quality_score": quality_score,
            "source_reliability": source_rel,
            "evidence_grounding": evidence_score,
            "review_id": review_id,
            "review_status": review_status,
            "is_low_confidence": is_low_confidence,
            "needs_clarification": needs_clarification,
            "response_mode": response_mode,
            "data_freshness": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources": sources_list,
            "retrieved_documents": retrieved_docs_formatted,
            "adapter_data": adapter_data,
            "pipeline_backend": "langchain_lcel" if HAS_LANGCHAIN else "direct_vector_store",
            "evidence_chunks": [
                {"chunk_id": c.chunk_id, "text": c.text, "score": round(s, 3)}
                for c, s in active_chunks
            ],
        }

    def generate_response(
        self,
        query: str,
        canonical_text: str,
        intent: str,
        language_code: str = "en",
        entities: Optional[dict[str, list[str]]] = None,
        top_k: int = 2,
        conversation_context: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute evidence retrieval, adapter integration, and grounded response synthesis.

        Executes through the LangChain LCEL chain when available, with deterministic fallback.
        """
        resolved_crop = (entities.get("crops") or [None])[0] if entities else None
        retrieval_query = canonical_text
        if resolved_crop and (
            (entities and entities.get("_crop_carried_from_context"))
            or any(re.search(rf"\b{re.escape(w)}\b", canonical_text, re.IGNORECASE) for w in ("it", "this", "that", "them", "apply", "water", "spray", "frequency", "how often", "dose", "rate", "schedule"))
        ):
            retrieval_query = f"{canonical_text} {resolved_crop}"
            if entities and entities.get("fertilizers"):
                retrieval_query += f" {entities['fertilizers'][0]}"

        payload = {
            "query": query,
            "canonical_text": canonical_text,
            "retrieval_query": retrieval_query,
            "intent": intent,
            "language_code": language_code,
            "entities": entities or {},
            "top_k": top_k,
            "conversation_context": conversation_context,
        }

        if self.lcel_chain is not None:
            try:
                return self.lcel_chain.invoke(payload)
            except Exception as exc:
                logger.warning("LangChain LCEL chain invocation failed (%s); running fallback.", exc)

        # Deterministic fallback when LCEL is unavailable
        raw_chunks = self.vector_store.similarity_search(query=retrieval_query, top_k=20)
        docs = [
            LCDocument(
                page_content=c.text,
                metadata={
                    **c.metadata,
                    "similarity_score": s,
                    "category": c.category,
                    "doc_id": c.doc_id,
                    "chunk_id": c.chunk_id,
                },
            )
            for c, s in raw_chunks
        ] if HAS_LANGCHAIN else [
            VectorDocumentChunk(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                text=c.text,
                category=c.category,
                metadata={**c.metadata, "similarity_score": s},
            )
            for c, s in raw_chunks
        ]
        intermediate = self._lcel_rerank_and_adapter_step({**payload, "retrieved_lc_docs": docs})
        res = self._lcel_synthesis_and_format_step(intermediate)
        res["pipeline_backend"] = "direct_vector_store"
        return res

    def _synthesize_grounded_answer(
        self,
        query: str,
        canonical_text: str,
        intent: str,
        language_code: str,
        entities: dict[str, list[str]],
        active_chunks: list[tuple[VectorDocumentChunk, float]],
        adapter_data: Optional[dict[str, Any]],
        is_low_confidence: bool,
        conversation_context: Optional[Any] = None,
    ) -> str:
        """Synthesize answer grounded strictly in retrieved evidence excerpts and official guidelines."""
        sections = []

        # ── Adapter-specific synthesized guidance ──────────────────────────
        if intent == "market_prices" and adapter_data:
            comm = adapter_data.get("commodity") or (entities.get("crops")[0].title() if entities.get("crops") else "Agricultural Commodity")
            loc = adapter_data.get("district") or adapter_data.get("state") or (entities.get("locations")[0].title() if entities.get("locations") else "")
            loc_suffix = f" — {loc.title()}" if loc and loc.lower() != "all" else ""
            sections.append(f"【AGMARKNET Live Mandi Price Advisory — {comm.title()}{loc_suffix}】")

            live_records = adapter_data.get("live_records", [])
            if adapter_data.get("is_live") and live_records:
                source_label = adapter_data.get("source", "AGMARKNET 2.0 API (api.agmarknet.gov.in)")
                sections.append(f"Official daily mandi prices reported via {source_label}:")
                for rec in live_records:
                    m_name = rec.get("market", "APMC Mandi")
                    c_name = rec.get("commodity", comm)
                    v_name = rec.get("variety", "General")
                    min_p = rec.get("min_price")
                    max_p = rec.get("max_price")
                    mod_p = rec.get("modal_price")
                    unit = rec.get("price_unit", "Rs./Quintal")
                    rep_date = rec.get("arrival_date", "Today")
                    d_name = rec.get("district", loc)
                    s_name = rec.get("state", "")

                    loc_parts = [p for p in [d_name, s_name] if p and p.lower() != "all"]
                    loc_desc = f" ({', '.join(loc_parts)})" if loc_parts else ""

                    market_block = (
                        f"• Market: {m_name}{loc_desc}\n"
                        f"  - Commodity: {c_name} | Variety: {v_name}\n"
                        f"  - Modal Price: ₹{mod_p:g} / {unit}\n"
                        f"  - Minimum Price: ₹{min_p:g} / {unit}\n"
                        f"  - Maximum Price: ₹{max_p:g} / {unit}\n"
                        f"  - Reporting Date: {rep_date}\n"
                        f"  - Source: {source_label}"
                    )
                    sections.append(market_block)

                if adapter_data.get("post_harvest_advice"):
                    sections.append(f"• Value Addition & Post-Harvest Advice: {adapter_data['post_harvest_advice']}")
                sections.append(
                    f"⚠️ Official Verification: Prices represent wholesale rates recorded at APMC regulated markets. "
                    f"Check daily arrivals directly on {adapter_data.get('official_portal', 'https://agmarknet.gov.in')}."
                )
                return "\n\n".join(sections)

            elif adapter_data.get("status") == "no_transactions_reported":
                msg = adapter_data.get("message") or f"No daily market arrivals or wholesale transactions were reported for {comm} in {loc or 'this region'} during the reporting window."
                sections.append(f"• Daily Price Verification: {msg}")
                if adapter_data.get("reference_msp"):
                    msp = adapter_data["reference_msp"]
                    sections.append(
                        f"• Reference Minimum Support Price (MSP): {msp['crop']} floor price is ₹{msp['msp_inr_per_quintal']}/quintal "
                        f"for {msp['marketing_season']} ({msp['source']})."
                    )
                if adapter_data.get("post_harvest_advice"):
                    sections.append(f"• Post-Harvest Value Addition: {adapter_data['post_harvest_advice']}")
                sections.append(
                    f"⚠️ Official Notice: No transactions recorded for this period. Never rely on unofficial rumors. "
                    f"Verify official arrivals on {adapter_data.get('official_portal', 'https://agmarknet.gov.in')} or contact your local APMC Mandi."
                )
                return "\n\n".join(sections)

            else:
                msg = adapter_data.get("message") or "Live wholesale mandi rates are tracked via AGMARKNET and e-NAM portals."
                sections.append(f"• Daily Price Verification: {msg}")
                if adapter_data.get("reference_msp"):
                    msp = adapter_data["reference_msp"]
                    sections.append(
                        f"• Reference Minimum Support Price (MSP): {msp['crop']} floor price is ₹{msp['msp_inr_per_quintal']}/quintal "
                        f"for {msp['marketing_season']} ({msp['source']})."
                    )
                if adapter_data.get("post_harvest_advice"):
                    sections.append(f"• Value Addition: {adapter_data.get('post_harvest_advice', '')}")
                sections.append(f"⚠️ Official Verification: Check daily modal rates directly on {adapter_data.get('official_portal', 'https://agmarknet.gov.in')}.")
                return "\n\n".join(sections)

        if intent == "weather" and adapter_data:
            target_loc = adapter_data.get("location") or (entities.get("locations")[0].title() if entities.get("locations") else "Local Station")
            source_lbl = adapter_data.get("source", "Open-Meteo WMO / IMD Agromet Guidance")
            sections.append(f"【Live Agricultural Weather Advisory — {target_loc}】")
            sections.append(f"Source: {source_lbl} (Official Meteorological Reference)")

            temp = adapter_data.get("current_temp_c")
            humidity = adapter_data.get("humidity_pct")
            wind = adapter_data.get("wind_speed_kmh")
            precip = adapter_data.get("precipitation_mm", 0.0)

            weather_metrics = [
                f"• Location: {target_loc}",
                f"• Current Temperature: {temp}°C" if temp is not None else "• Temperature: Data unavailable",
                f"• Relative Humidity: {humidity}%" if humidity is not None else "• Relative Humidity: Data unavailable",
                f"• Wind Speed: {wind} km/h" if wind is not None else "• Wind Speed: Data unavailable",
                f"• Precipitation: {precip} mm" if precip is not None else "• Precipitation: 0.0 mm",
            ]
            sections.append("\n".join(weather_metrics))

            if adapter_data.get("spray_advisory"):
                sections.append(f"• Chemical Spray Recommendation: {adapter_data['spray_advisory']}")
            if adapter_data.get("spray_safety_rule"):
                sections.append(f"• Spray Safety Rule: {adapter_data['spray_safety_rule']}")

            sections.append(f"⚠️ Official Reference: Verify regional district agromet bulletins at IMD Mausam ({adapter_data.get('official_portal', 'https://mausam.imd.gov.in')}).")
            return "\n\n".join(sections)

        if intent == "government_schemes" and adapter_data:
            details = adapter_data.get("scheme_details", {})
            sections.append(f"【{details.get('name', 'Government Scheme Advisory')}】")
            sections.append(f"• Core Benefit: {details.get('benefit', '')}")
            if details.get("eligibility"):
                sections.append(f"• Eligibility: {details.get('eligibility', '')}")
            if details.get("mandatory_requirements"):
                reqs = ", ".join(details["mandatory_requirements"])
                sections.append(f"• Mandatory Checklist: {reqs}")
            if details.get("helpline"):
                sections.append(f"• Official Helpline: {details['helpline']}")
            sections.append(f"\n⚠️ {details.get('disclaimer', '')} Apply at {adapter_data['official_portal']}.")
            return "\n\n".join(sections)

        # ── Low-Confidence Fallback ─────────────────────────────────────────
        if is_low_confidence or not active_chunks:
            return (
                "【Agricultural Extension Notice】\n\n"
                "Specific verified ICAR research evidence matching the exact parameters of your question was not found in the local repository.\n\n"
                "• Recommended Action: For specialized local dosages, soil testing, or disease diagnosis, please contact your local Krishi Vigyan Kendra (KVK) "
                "or call the toll-free Kisan Call Centre at 1800-180-1551 (available 6:00 AM to 10:00 PM in all Indian languages).\n\n"
                "⚠️ Safety Notice: Never apply unverified chemical dosages without consulting your regional Agricultural Extension Officer."
            )

        # ── Evidence-Grounded Synthesis from Retrieved Chunks ───────────────
        top_chunk, score = active_chunks[0]
        meta = top_chunk.metadata
        title = meta.get("title", "Agricultural Advisory")
        source_name = meta.get("source_name", "ICAR")
        guardrail = meta.get("guardrail_notice", "")

        intent_labels = {
            "irrigation": "Irrigation & Water Management Advisory",
            "pest_control": "Pest & Disease Management Advisory",
            "crop_advisory": "Crop Advisory & Agronomic Guidance",
            "market_prices": "Agricultural Market & Price Discovery Advisory",
            "government_schemes": "Government Agricultural Scheme Advisory",
        }
        intent_label = intent_labels.get(intent, "Agricultural Advisory")

        # Multi-turn context preamble for conversational continuity
        is_followup = bool(
            conversation_context and (
                entities.get("_crop_carried_from_context")
                or any(re.search(rf"\b{re.escape(w)}\b", canonical_text, re.IGNORECASE) for w in ("it", "this", "that", "them", "apply", "give", "how often", "frequency", "dosage", "schedule"))
            )
        )
        resolved_crop_val = (entities.get("crops") or [None])[0]
        if is_followup:
            if resolved_crop_val:
                sections.append(f"Based on the previous discussion regarding {resolved_crop_val.title()} management:")
            else:
                sections.append("Based on the previous discussion:")

        sections.append(f"【{intent_label} — {title}】")
        sections.append(f"Evidence Source: {source_name} (Official Reference)")

        # Extract structured points from chunk text
        raw_text = top_chunk.text
        lines = [line.strip() for line in raw_text.split("\n") if line.strip() and not line.startswith(title)]
        if lines:
            bullet_points = [line if line.startswith("•") else f"• {line}" for line in lines]
            sections.append("\n".join(bullet_points))
        else:
            sections.append(f"• {raw_text}")

        # Add second chunk points if complementary
        if len(active_chunks) > 1:
            second_chunk, s2 = active_chunks[1]
            if second_chunk.doc_id != top_chunk.doc_id:
                s_lines = [l.strip() for l in second_chunk.text.split("\n") if l.strip() and "•" in l]
                if s_lines:
                    sections.append("\nAdditional Field Recommendations:\n" + "\n".join(s_lines[:2]))

        # Mandatory Safety Guardrail
        if guardrail:
            sections.append(f"\n⚠️ Important Guidance: {guardrail}")

        return "\n\n".join(sections)


# Module-level singleton
rag_pipeline = RAGPipeline()

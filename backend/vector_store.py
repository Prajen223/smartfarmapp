"""Persistent Vector Store & Embedding Pipeline for Smart Farming Assistant.

Provides:
  • BaseVectorStore abstraction interface.
  • Genuine PersistentLocalVectorStore using NumPy cosine similarity and disk persistence.
  • ChromaDBVectorStore wrapper when ChromaDB is available in the environment.
  • Document chunking with metadata preservation.
  • Embeddings: DeterministicFixtureEmbeddings for ultra-fast offline testing and
    LocalHuggingFaceEmbeddings using local cached transformer weights.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_STORE_DIR = Path(__file__).parent / "data" / "vector_store"


@dataclass
class VectorDocumentChunk:
    """A granular chunk of an agricultural knowledge document with preserved provenance."""
    chunk_id: str
    doc_id: str
    text: str
    category: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> VectorDocumentChunk:
        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            text=data["text"],
            category=data.get("category", "farming_practices"),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
        )


# ---------------------------------------------------------------------------
# Embeddings Abstraction
# ---------------------------------------------------------------------------

class BaseEmbeddings(ABC):
    """Abstract interface for text embedding models."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a normalized dense vector."""
        pass

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""
        return [self.embed_text(t) for t in texts]


class DeterministicFixtureEmbeddings(BaseEmbeddings):
    """Fast, deterministic, offline embedding generator using token hashing and normalized projection.

    Provides stable, reproducible 128-dimensional dense vectors for testing and offline
    environments without downloading or loading large transformer weights.
    """

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        for word in words:
            # Deterministic MD5 hash to index and sign
            h = hashlib.md5(word.encode("utf-8")).digest()
            idx = int.from_bytes(h[:2], "big") % self.dimension
            sign = 1.0 if (h[2] % 2 == 0) else -1.0
            vec[idx] += sign

            # Secondary projection for bigram features
            idx2 = int.from_bytes(h[2:4], "big") % self.dimension
            vec[idx2] += sign * 0.5

        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        return vec.tolist()


class LocalHuggingFaceEmbeddings(BaseEmbeddings):
    """Embedding extractor using locally cached Hugging Face transformer weights.

    Extracts dense embeddings via mean-pooling over hidden representations.
    """

    _instance = None
    _model = None
    _tokenizer = None

    def __init__(self, model_name: str = "valhalla/distilbart-mnli-12-1") -> None:
        self.model_name = model_name
        self._load_local_model()

    def _load_local_model(self) -> None:
        if LocalHuggingFaceEmbeddings._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModel
            logger.info("Loading cached local transformer model for embeddings: %s", self.model_name)
            LocalHuggingFaceEmbeddings._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                local_files_only=True,
            )
            LocalHuggingFaceEmbeddings._model = AutoModel.from_pretrained(
                self.model_name,
                local_files_only=True,
            )
            LocalHuggingFaceEmbeddings._model.eval()
        except Exception as exc:
            logger.warning(
                "Could not load local transformer '%s' (%s). Falling back to DeterministicFixtureEmbeddings.",
                self.model_name,
                exc,
            )
            self._fallback = DeterministicFixtureEmbeddings()

    def embed_text(self, text: str) -> list[float]:
        if getattr(self, "_fallback", None) is not None:
            return self._fallback.embed_text(text)

        import torch
        tokenizer = LocalHuggingFaceEmbeddings._tokenizer
        model = LocalHuggingFaceEmbeddings._model

        if tokenizer is None or model is None:
            return DeterministicFixtureEmbeddings().embed_text(text)

        inputs = tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
            # Mean pooling
            emb = outputs.last_hidden_state.mean(dim=1).squeeze(0).numpy()
            norm = np.linalg.norm(emb)
            if norm > 1e-9:
                emb = emb / norm
            return emb.tolist()


# ---------------------------------------------------------------------------
# Document Chunking
# ---------------------------------------------------------------------------

def chunk_agricultural_document(
    doc: Any,
    chunk_size_words: int = 80,
    overlap_words: int = 20,
) -> list[VectorDocumentChunk]:
    """Split an agricultural document into overlapping semantic chunks while preserving metadata.

    Supports both AgriculturalRecord and KnowledgeDocument objects.
    """
    doc_id = getattr(doc, "doc_id", "unknown")
    category = getattr(doc, "category", "crops")
    title = getattr(doc, "title", "")
    content_en = getattr(doc, "content_en", "")

    # Extract provenance metadata
    source_attr = getattr(doc, "source", None)
    if source_attr is not None:
        source_name = getattr(source_attr, "name", "ICAR / Government of India")
        org = getattr(source_attr, "organization", "Agricultural Department")
        url = getattr(source_attr, "official_url", "")
    else:
        source_name = getattr(doc, "source_name", "ICAR / Government of India")
        org = getattr(doc, "organization", "Agricultural Department")
        url = getattr(doc, "official_url", "")

    base_metadata = {
        "title": title,
        "source_name": source_name,
        "organization": org,
        "official_url": url,
        "category": category,
        "guardrail_notice": getattr(doc, "guardrail_notice", ""),
        "crops_applicable": getattr(doc, "crops_applicable", []),
        "soil_types_applicable": getattr(doc, "soil_types_applicable", []),
        "tags": getattr(doc, "tags", []),
        "verification_status": getattr(doc, "verification_status", "verified_curated"),
    }

    # Split English content by sentences/paragraphs or word window
    words = content_en.split()
    if not words:
        # Fallback to title
        return [
            VectorDocumentChunk(
                chunk_id=f"{doc_id}_c0",
                doc_id=doc_id,
                text=f"{title}: {content_en}",
                category=category,
                metadata=base_metadata,
            )
        ]

    chunks: list[VectorDocumentChunk] = []
    step = max(1, chunk_size_words - overlap_words)
    chunk_idx = 0

    for i in range(0, len(words), step):
        chunk_words = words[i : i + chunk_size_words]
        if not chunk_words:
            break
        chunk_text = f"{title}\n" + " ".join(chunk_words)
        meta = dict(base_metadata)
        meta["chunk_index"] = chunk_idx

        chunks.append(
            VectorDocumentChunk(
                chunk_id=f"{doc_id}_c{chunk_idx}",
                doc_id=doc_id,
                text=chunk_text,
                category=category,
                metadata=meta,
            )
        )
        chunk_idx += 1
        if i + chunk_size_words >= len(words):
            break

    return chunks


# ---------------------------------------------------------------------------
# Vector Store Interface & Implementations
# ---------------------------------------------------------------------------

class BaseVectorStore(ABC):
    """Abstract interface for persistent vector databases."""

    @abstractmethod
    def add_chunks(self, chunks: list[VectorDocumentChunk]) -> int:
        """Add or update document chunks with embeddings in the vector store."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
        filter_dict: Optional[dict] = None,
    ) -> list[tuple[VectorDocumentChunk, float]]:
        """Search for chunks closest to the query vector, returning (chunk, similarity_score)."""
        pass

    @abstractmethod
    def save(self) -> bool:
        """Persist index and embeddings to disk."""
        pass

    @abstractmethod
    def load(self) -> bool:
        """Load stored index from disk."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Total number of indexed chunks."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored vectors and chunks."""
        pass

    @abstractmethod
    def delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """Remove all chunks associated with a specific document ID. Returns number of removed chunks."""
        pass


class PersistentLocalVectorStore(BaseVectorStore):
    """Persistent local vector store using NumPy normalized cosine similarity and JSON/NPY disk persistence.

    Fully persistent across restarts; no external network or C++ binary compilation required.
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        embeddings: Optional[BaseEmbeddings] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir or DEFAULT_VECTOR_STORE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "vector_index.json"
        self.embeddings_file = self.storage_dir / "embeddings.npy"

        self.embeddings_model = embeddings or DeterministicFixtureEmbeddings()
        self._chunks: dict[str, VectorDocumentChunk] = {}
        self._embeddings_matrix: Optional[np.ndarray] = None
        self._chunk_ids_order: list[str] = []

        self.load()

    @property
    def backend_name(self) -> str:
        return "local_persistent_vector_store"

    def add_chunks(self, chunks: list[VectorDocumentChunk]) -> int:
        if not chunks:
            return 0

        # Compute embeddings for chunks that don't have them
        texts_to_embed = []
        indices_to_embed = []
        for i, chunk in enumerate(chunks):
            if chunk.embedding is None:
                texts_to_embed.append(chunk.text)
                indices_to_embed.append(i)

        if texts_to_embed:
            computed = self.embeddings_model.embed_batch(texts_to_embed)
            for orig_idx, emb in zip(indices_to_embed, computed):
                chunks[orig_idx].embedding = emb

        # Upsert chunks into dictionary
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

        self._rebuild_matrix()
        self.save()
        return len(chunks)

    def _rebuild_matrix(self) -> None:
        """Build a 2D NumPy matrix of L2-normalized embeddings for fast vector similarity."""
        self._chunk_ids_order = list(self._chunks.keys())
        if not self._chunk_ids_order:
            self._embeddings_matrix = None
            return

        expected_dim = getattr(self.embeddings_model, "dimension", None)
        vec_list = []
        for cid in self._chunk_ids_order:
            chunk = self._chunks[cid]
            if chunk.embedding is None or (expected_dim is not None and len(chunk.embedding) != expected_dim):
                chunk.embedding = self.embeddings_model.embed_text(chunk.text)
            vec_list.append(chunk.embedding)

        mat = np.array(vec_list, dtype=np.float32)

        # Ensure L2 normalization along rows
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self._embeddings_matrix = mat / norms

    def similarity_search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
        filter_dict: Optional[dict] = None,
    ) -> list[tuple[VectorDocumentChunk, float]]:
        if self._embeddings_matrix is None or not self._chunks:
            return []

        # Generate query vector and normalize
        q_vec = np.array(self.embeddings_model.embed_text(query), dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 1e-9:
            q_vec = q_vec / q_norm
        else:
            return []

        # Cosine similarity via dot product against normalized matrix
        similarities = np.dot(self._embeddings_matrix, q_vec)

        results: list[tuple[VectorDocumentChunk, float]] = []
        for idx, sim in enumerate(similarities):
            cid = self._chunk_ids_order[idx]
            chunk = self._chunks[cid]

            # Category filter
            if category and chunk.category != category:
                continue

            # Metadata filter dict
            if filter_dict:
                match = True
                for k, v in filter_dict.items():
                    if chunk.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            results.append((chunk, float(sim)))

        # Sort descending by similarity score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def save(self) -> bool:
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            # Save chunks metadata
            payload = {
                "backend": self.backend_name,
                "chunk_count": len(self._chunks),
                "chunks": [chunk.to_dict() for chunk in self._chunks.values()],
            }
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            # Save numpy embeddings matrix
            if self._embeddings_matrix is not None:
                np.save(self.embeddings_file, self._embeddings_matrix)
            return True
        except Exception as exc:
            logger.error("Failed to save vector store to %s: %s", self.storage_dir, exc)
            return False

    def load(self) -> bool:
        if not self.index_file.exists():
            return False
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                chunks_data = data.get("chunks", [])
                self._chunks = {item["chunk_id"]: VectorDocumentChunk.from_dict(item) for item in chunks_data}

            if self.embeddings_file.exists():
                loaded_matrix = np.load(self.embeddings_file)
                expected_dim = getattr(self.embeddings_model, "dimension", None)
                if expected_dim is not None and loaded_matrix.ndim == 2 and loaded_matrix.shape[1] != expected_dim:
                    logger.warning(
                        "Stored embeddings dimension %s does not match active model dimension %s. Rebuilding index matrix.",
                        loaded_matrix.shape[1],
                        expected_dim,
                    )
                    self._rebuild_matrix()
                else:
                    self._embeddings_matrix = loaded_matrix
                    self._chunk_ids_order = list(self._chunks.keys())
            else:
                self._rebuild_matrix()
            return True
        except Exception as exc:
            logger.warning("Could not load vector store from %s: %s", self.index_file, exc)
            return False

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()
        self._embeddings_matrix = None
        self._chunk_ids_order.clear()
        if self.index_file.exists():
            self.index_file.unlink(missing_ok=True)
        if self.embeddings_file.exists():
            self.embeddings_file.unlink(missing_ok=True)

    def delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """Remove all chunks associated with a specific document ID."""
        to_delete = [
            cid for cid, chunk in self._chunks.items()
            if chunk.doc_id == doc_id
            or (chunk.metadata and chunk.metadata.get("doc_id") == doc_id)
            or cid == doc_id
            or cid.startswith(f"{doc_id}_c")
        ]
        if not to_delete:
            return 0
        for cid in to_delete:
            del self._chunks[cid]
        self._rebuild_matrix()
        self.save()
        return len(to_delete)


# ---------------------------------------------------------------------------
# ChromaDB Serialization Helpers
# ---------------------------------------------------------------------------

def _sanitize_metadata_for_chroma(raw_meta: dict[str, Any]) -> dict[str, Union[str, int, float, bool]]:
    """Sanitize metadata dictionary for ChromaDB by converting lists/dicts to strings and omitting empty lists."""
    sanitized: dict[str, Union[str, int, float, bool]] = {}
    for k, v in raw_meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            sanitized[k] = v
        elif isinstance(v, list):
            if len(v) == 0:
                continue
            sanitized[k] = ", ".join(str(item) for item in v)
        elif isinstance(v, dict):
            sanitized[k] = json.dumps(v)
        else:
            sanitized[k] = str(v)
    return sanitized


def _restore_metadata_from_chroma(meta: dict[str, Any]) -> dict[str, Any]:
    """Restore list attributes from ChromaDB comma-separated strings."""
    restored = dict(meta)
    for key in ("crops_applicable", "soil_types_applicable", "tags"):
        if key in restored and isinstance(restored[key], str):
            val = restored[key].strip()
            restored[key] = [item.strip() for item in val.split(",") if item.strip()] if val else []
    return restored


# ---------------------------------------------------------------------------
# ChromaDB Wrapper (Activated when chromadb package is present)
# ---------------------------------------------------------------------------

class ChromaDBVectorStore(BaseVectorStore):
    """Production vector store backed by ChromaDB persistent local collections."""

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        collection_name: str = "agricultural_knowledge",
        embeddings: Optional[BaseEmbeddings] = None,
    ) -> None:
        import chromadb
        self.storage_dir = Path(storage_dir or DEFAULT_VECTOR_STORE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.storage_dir))
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embeddings_model = embeddings or DeterministicFixtureEmbeddings()

    @property
    def backend_name(self) -> str:
        return "chromadb"

    def add_chunks(self, chunks: list[VectorDocumentChunk]) -> int:
        if not chunks:
            return 0
        ids = [c.chunk_id for c in chunks]
        docs = [c.text for c in chunks]
        metadatas = [_sanitize_metadata_for_chroma(c.metadata) for c in chunks]

        # Compute embeddings using our embeddings model for consistent vector representations
        embeddings_list = []
        for c in chunks:
            if c.embedding is None:
                c.embedding = self.embeddings_model.embed_text(c.text)
            embeddings_list.append(c.embedding)

        self.collection.upsert(
            ids=ids,
            documents=docs,
            metadatas=metadatas,
            embeddings=embeddings_list,
        )
        return len(chunks)

    def similarity_search(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
        filter_dict: Optional[dict] = None,
    ) -> list[tuple[VectorDocumentChunk, float]]:
        where_clause = {}
        if category:
            where_clause["category"] = category
        if filter_dict:
            where_clause.update(filter_dict)

        q_vec = self.embeddings_model.embed_text(query)

        results = self.collection.query(
            query_embeddings=[q_vec],
            n_results=top_k,
            where=where_clause if where_clause else None,
        )
        out = []
        if results and results.get("ids") and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                txt = results["documents"][0][i] if results.get("documents") else ""
                raw_meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                meta = _restore_metadata_from_chroma(raw_meta)
                dist = results["distances"][0][i] if results.get("distances") else 0.5
                score = max(0.0, 1.0 - float(dist))
                chunk = VectorDocumentChunk(
                    chunk_id=cid,
                    doc_id=meta.get("doc_id", cid.split("_c")[0]),
                    text=txt,
                    category=meta.get("category", "crops"),
                    metadata=meta,
                )
                out.append((chunk, score))
        return out

    def save(self) -> bool:
        # ChromaDB PersistentClient persists automatically on disk
        return True

    def load(self) -> bool:
        return True

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("Could not clear ChromaDB collection: %s", exc)

    def delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """Remove all chunks associated with a specific document ID from ChromaDB."""
        try:
            matching = self.collection.get(where={"doc_id": doc_id})
            ids = matching.get("ids", [])
            if not ids:
                all_records = self.collection.get()
                all_ids = all_records.get("ids", [])
                ids = [cid for cid in all_ids if cid == doc_id or cid.startswith(f"{doc_id}_c")]

            if ids:
                self.collection.delete(ids=ids)
                return len(ids)
            return 0
        except Exception as exc:
            logger.warning("Error deleting chunks for doc_id '%s' in ChromaDB: %s", doc_id, exc)
            return 0


# VectorStoreInterface alias
VectorStoreInterface = BaseVectorStore


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def get_vector_store(
    storage_dir: Optional[Path] = None,
    use_fixture_embeddings: bool = True,
    prefer_chromadb: Optional[bool] = None,
    backend: Optional[str] = None,
) -> BaseVectorStore:
    """Create and return a vector store with configurable backend selection.

    Selection Priority:
      1. backend argument ("chromadb", "numpy", "local")
      2. VECTOR_STORE_BACKEND environment variable
      3. prefer_chromadb parameter
      4. Default: "numpy" (PersistentLocalVectorStore for deterministic test baseline)
    """
    import os

    configured_backend = backend or os.getenv("VECTOR_STORE_BACKEND", "").strip().lower()
    if not configured_backend:
        if prefer_chromadb is True:
            configured_backend = "chromadb"
        else:
            configured_backend = "numpy"

    emb_model = DeterministicFixtureEmbeddings() if use_fixture_embeddings else LocalHuggingFaceEmbeddings()

    if configured_backend == "chromadb":
        try:
            import chromadb  # pyrefly: ignore [missing-import]
            logger.info("Initializing ChromaDB persistent vector database.")
            return ChromaDBVectorStore(storage_dir=storage_dir, embeddings=emb_model)
        except Exception as exc:
            logger.warning("ChromaDB requested but unavailable (%s); falling back to PersistentLocalVectorStore.", exc)

    return PersistentLocalVectorStore(storage_dir=storage_dir, embeddings=emb_model)

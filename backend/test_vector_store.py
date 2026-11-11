"""Unit tests for vector_store.py — Persistent Vector Database & Embeddings."""

import tempfile
import unittest
from pathlib import Path

from vector_store import (
    VectorDocumentChunk,
    DeterministicFixtureEmbeddings,
    PersistentLocalVectorStore,
    chunk_agricultural_document,
    get_vector_store,
)
from data_ingestion import AgriculturalRecord


class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)
        self.embeddings = DeterministicFixtureEmbeddings(dimension=64)
        self.store = PersistentLocalVectorStore(
            storage_dir=self.storage_path,
            embeddings=self.embeddings,
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_embeddings_generation_and_normalization(self):
        emb1 = self.embeddings.embed_text("paddy irrigation AWD water management")
        emb2 = self.embeddings.embed_text("rice flooding alternate wetting drying")
        emb_empty = self.embeddings.embed_text("")

        self.assertEqual(len(emb1), 64)
        self.assertEqual(len(emb2), 64)
        self.assertEqual(len(emb_empty), 64)

        # Norm should be ~1.0
        import numpy as np
        norm1 = np.linalg.norm(emb1)
        self.assertAlmostEqual(norm1, 1.0, places=4)

    def test_add_chunks_and_persistence(self):
        chunks = [
            VectorDocumentChunk(
                chunk_id="chunk_001",
                doc_id="doc_paddy_001",
                text="Alternate Wetting and Drying (AWD) in paddy saves 30% water.",
                category="crops",
                metadata={"crop": "paddy", "source": "ICAR-NRRI"},
            ),
            VectorDocumentChunk(
                chunk_id="chunk_002",
                doc_id="doc_wheat_001",
                text="Wheat crown root initiation (CRI) stage requires first irrigation at 20-25 DAS.",
                category="crops",
                metadata={"crop": "wheat", "source": "ICAR-IIWBR"},
            ),
        ]
        count = self.store.add_chunks(chunks)
        self.assertEqual(count, 2)
        self.assertEqual(self.store.count(), 2)

        # Reload store from disk
        reloaded_store = PersistentLocalVectorStore(
            storage_dir=self.storage_path,
            embeddings=self.embeddings,
        )
        self.assertEqual(reloaded_store.count(), 2)
        self.assertIn("chunk_001", reloaded_store._chunks)
        self.assertIn("chunk_002", reloaded_store._chunks)

    def test_semantic_similarity_search(self):
        chunks = [
            VectorDocumentChunk(
                chunk_id="chunk_tomato",
                doc_id="doc_tomato",
                text="Tomato blossom end rot is caused by calcium deficiency and irregular watering.",
                category="crops",
                metadata={"crops_applicable": ["tomato"]},
            ),
            VectorDocumentChunk(
                chunk_id="chunk_cotton",
                doc_id="doc_cotton",
                text="Pink bollworm in cotton can be monitored using sex pheromone traps at 4-5 per acre.",
                category="pests",
                metadata={"crops_applicable": ["cotton"]},
            ),
        ]
        self.store.add_chunks(chunks)

        results_tomato = self.store.similarity_search("tomato calcium deficiency and watering", top_k=1)
        self.assertGreater(len(results_tomato), 0)
        self.assertEqual(results_tomato[0][0].chunk_id, "chunk_tomato")
        self.assertGreater(results_tomato[0][1], 0.0)

        results_cotton = self.store.similarity_search("bollworm moth traps cotton pest", top_k=1)
        self.assertGreater(len(results_cotton), 0)
        self.assertEqual(results_cotton[0][0].chunk_id, "chunk_cotton")

    def test_category_filtering(self):
        chunks = [
            VectorDocumentChunk(
                chunk_id="c_pest",
                doc_id="d_pest",
                text="Sucking pests aphids whiteflies control.",
                category="pests",
            ),
            VectorDocumentChunk(
                chunk_id="c_irrigation",
                doc_id="d_irrigation",
                text="Drip irrigation fertigation water saving.",
                category="farming_practices",
            ),
        ]
        self.store.add_chunks(chunks)

        # Searching with category filter
        results = self.store.similarity_search("water irrigation", category="pests")
        for chunk, _ in results:
            self.assertEqual(chunk.category, "pests")

    def test_chunk_agricultural_document(self):
        rec = AgriculturalRecord(
            doc_id="doc_test_100",
            category="crops",
            title="Paddy Water Scheduling",
            sub_category="cereals",
            source_name="ICAR-NRRI",
            organization="ICAR",
            official_url="https://nrri.nic.in",
            content_en=(
                "Paddy cultivation requires careful water management. "
                "Practice Alternate Wetting and Drying rather than continuous flooding. "
                "Keep 2-3 cm shallow water during tillering and panicle initiation, "
                "then allow the soil to develop hairline cracks before re-watering. "
                "This improves root aeration and reduces methane emissions significantly."
            ),
            crops_applicable=["paddy"],
            guardrail_notice="Calibrate with Soil Health Card.",
        )
        chunks = chunk_agricultural_document(rec, chunk_size_words=15, overlap_words=5)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertEqual(c.doc_id, "doc_test_100")
            self.assertEqual(c.category, "crops")
            self.assertEqual(c.metadata["source_name"], "ICAR-NRRI")
            self.assertEqual(c.metadata["official_url"], "https://nrri.nic.in")
            self.assertTrue(len(c.metadata["guardrail_notice"]) > 0)

    def test_chromadb_vector_store_crud_and_metadata_sanitization(self):
        """Milestone 2: Verify ChromaDBVectorStore insertion, search, and metadata sanitization."""
        from vector_store import ChromaDBVectorStore
        chroma_dir = self.storage_path / "chroma_test"
        chroma_store = ChromaDBVectorStore(storage_dir=chroma_dir, collection_name="test_col", embeddings=self.embeddings)
        self.assertEqual(chroma_store.backend_name, "chromadb")

        chunk = VectorDocumentChunk(
            chunk_id="chunk_chroma_001",
            doc_id="doc_tomato",
            text="Tomato plants require uniform moisture to prevent blossom end rot.",
            category="crops",
            metadata={
                "title": "Tomato Guidelines",
                "crops_applicable": ["tomato"],
                "soil_types_applicable": [],  # Empty list must be sanitized
                "tags": [],
            },
        )
        count = chroma_store.add_chunks([chunk])
        self.assertEqual(count, 1)
        self.assertEqual(chroma_store.count(), 1)

        # Duplicate insertion should upsert without duplicating count
        chroma_store.add_chunks([chunk])
        self.assertEqual(chroma_store.count(), 1)

        # Search
        results = chroma_store.similarity_search("tomato moisture", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].chunk_id, "chunk_chroma_001")
        self.assertEqual(results[0][0].metadata["crops_applicable"], ["tomato"])

    def test_factory_vector_store_backend_selection(self):
        """Milestone 2: Verify get_vector_store supports configurable backends."""
        store_numpy = get_vector_store(backend="numpy")
        self.assertEqual(store_numpy.backend_name, "local_persistent_vector_store")

        store_chroma = get_vector_store(storage_dir=self.storage_path / "chroma_factory", backend="chromadb")
        self.assertEqual(store_chroma.backend_name, "chromadb")

    def test_dimension_mismatch_rebuild(self):
        """Milestone 2: Verify PersistentLocalVectorStore rebuilds matrix safely on dimension mismatch."""
        import numpy as np
        chunk = VectorDocumentChunk(
            chunk_id="c_dim",
            doc_id="doc_dim",
            text="Organic farming compost nitrogen fixation.",
            category="farming_practices",
        )
        self.store.add_chunks([chunk])
        self.store.save()

        # Artificially overwrite embeddings.npy with incompatible 32-dim matrix
        incompatible = np.ones((1, 32), dtype=np.float32)
        np.save(self.store.embeddings_file, incompatible)

        # Reloading should detect mismatch and rebuild with current 64-dim embeddings
        reloaded = PersistentLocalVectorStore(storage_dir=self.storage_path, embeddings=self.embeddings)
        self.assertEqual(reloaded._embeddings_matrix.shape[1], 64)

    def test_chunk_boundaries_metadata_and_embedding_consistency(self):
        """Milestone 2: Verify chunk boundaries, chunk index inheritance, and embedding dimension consistency."""
        import numpy as np
        doc = AgriculturalRecord(
            doc_id="doc_paddy_deep",
            category="crops",
            title="Comprehensive Paddy Agronomy",
            sub_category="cereals",
            source_name="ICAR-NRRI",
            organization="Central Rice Research Institute",
            official_url="https://nrri.nic.in/paddy",
            content_en="Word " * 200,  # 200 words to ensure multiple distinct chunks
            crops_applicable=["paddy", "rice"],
            soil_types_applicable=["alluvial", "clay"],
            guardrail_notice="Follow regional advisory.",
        )
        chunks = chunk_agricultural_document(doc, chunk_size_words=80, overlap_words=20)
        self.assertGreaterEqual(len(chunks), 3)

        # Verify chunk IDs and sequential indices
        for idx, ch in enumerate(chunks):
            self.assertEqual(ch.doc_id, "doc_paddy_deep")
            self.assertEqual(ch.chunk_id, f"doc_paddy_deep_c{idx}")
            self.assertEqual(ch.metadata["chunk_index"], idx)
            self.assertEqual(ch.metadata["title"], "Comprehensive Paddy Agronomy")
            self.assertEqual(ch.metadata["organization"], "Central Rice Research Institute")
            self.assertEqual(ch.metadata["official_url"], "https://nrri.nic.in/paddy")

        # Ingest into store and verify embedding dimensions and unit norms
        default_embeddings = DeterministicFixtureEmbeddings(dimension=128)
        store = PersistentLocalVectorStore(
            storage_dir=self.storage_path / "dim_check",
            embeddings=default_embeddings,
        )
        store.add_chunks(chunks)
        self.assertEqual(store.count(), len(chunks))

        # Check all stored embeddings have identical expected dimension and normalized norm
        for ch in store._chunks.values():
            self.assertIsNotNone(ch.embedding)
            self.assertEqual(len(ch.embedding), 128)
            norm = np.linalg.norm(ch.embedding)
            self.assertAlmostEqual(norm, 1.0, places=4)


if __name__ == "__main__":
    unittest.main()

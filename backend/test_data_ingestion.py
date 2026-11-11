"""Unit tests for data_ingestion.py — Stage 2: Data Curation & Ingestion Pipeline."""

import json
import tempfile
import unittest
from pathlib import Path

from data_ingestion import (
    AgriculturalRecord,
    DataIngestionPipeline,
    validate_document,
    normalize_document,
    compute_record_fingerprint,
    get_official_curated_seed_records,
    extract_text_from_pdf,
    parse_text_or_markdown_document,
)


class TestDataIngestionValidation(unittest.TestCase):
    """Test validation of required fields, attribution, and guardrails."""

    def test_valid_record_passes_validation(self):
        valid_doc = {
            "doc_id": "test_001",
            "category": "crops",
            "title": "Tomato Nursery and Drip Irrigation Guidelines",
            "sub_category": "vegetables",
            "source_name": "ICAR — IIHR",
            "organization": "Indian Council of Agricultural Research",
            "official_url": "https://iihr.res.in",
            "content_en": "Raise tomato seedlings under nylon insect nets to protect against whiteflies.",
            "guardrail_notice": "Always verify regional spray advisories with your local KVK.",
        }
        is_valid, errors = validate_document(valid_doc)
        self.assertTrue(is_valid, f"Expected valid document, but got errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_missing_attribution_fails_validation(self):
        doc_no_source = {
            "doc_id": "test_002",
            "category": "soil",
            "title": "Soil Testing Protocol",
            "sub_category": "soil_health",
            "source_name": "",  # missing
            "organization": "",  # missing
            "official_url": "https://soilhealth.dac.gov.in",
            "content_en": "Soil testing should be done across 12 parameters every 3 years.",
            "guardrail_notice": "Do not dry samples under direct sunlight.",
        }
        is_valid, errors = validate_document(doc_no_source)
        self.assertFalse(is_valid)
        self.assertTrue(any("source_name" in err for err in errors))
        self.assertTrue(any("organization" in err for err in errors))

    def test_invalid_url_fails_validation(self):
        doc_bad_url = {
            "doc_id": "test_003",
            "category": "crops",
            "title": "Rice Package of Practices",
            "sub_category": "cereals",
            "source_name": "ICAR-NRRI",
            "organization": "ICAR",
            "official_url": "ftp://not-a-web-url/doc.pdf",
            "content_en": "Adopt Alternate Wetting and Drying rather than continuous flooding.",
            "guardrail_notice": "Calibrate fertilizer doses according to Soil Health Card.",
        }
        is_valid, errors = validate_document(doc_bad_url)
        self.assertFalse(is_valid)
        self.assertTrue(any("official_url" in err.lower() for err in errors))

    def test_missing_guardrail_notice_fails_validation(self):
        doc_no_guardrail = {
            "doc_id": "test_004",
            "category": "pests",
            "title": "Pest Management in Cotton",
            "sub_category": "borers",
            "source_name": "ICAR-CICR",
            "organization": "ICAR",
            "official_url": "https://cicr.icar.gov.in",
            "content_en": "Install pheromone traps at 4-5 per acre for monitoring pink bollworm.",
            "guardrail_notice": "",  # missing
        }
        is_valid, errors = validate_document(doc_no_guardrail)
        self.assertFalse(is_valid)
        self.assertTrue(any("guardrail" in err.lower() for err in errors))

    def test_insufficient_content_length_fails_validation(self):
        doc_short_content = {
            "doc_id": "test_005",
            "category": "irrigation",
            "title": "Drip Irrigation",
            "sub_category": "water",
            "source_name": "MoA&FW",
            "organization": "Ministry of Agriculture",
            "official_url": "https://pmksy.gov.in",
            "content_en": "Too short.",  # < 30 chars
            "guardrail_notice": "Check filter.",
        }
        is_valid, errors = validate_document(doc_short_content)
        self.assertFalse(is_valid)
        self.assertTrue(any("content" in err.lower() for err in errors))

    def test_invalid_category_fails_validation(self):
        doc_bad_category = {
            "doc_id": "test_006",
            "category": "cryptocurrency_farming",  # invalid
            "title": "Farming Guidelines",
            "sub_category": "unknown",
            "source_name": "Unknown",
            "organization": "Unknown",
            "official_url": "https://agricoop.nic.in",
            "content_en": "Farming guidelines with sufficient character length for testing.",
            "guardrail_notice": "Standard notice.",
        }
        is_valid, errors = validate_document(doc_bad_category)
        self.assertFalse(is_valid)
        self.assertTrue(any("category" in err.lower() for err in errors))

    def test_fabricated_live_price_claim_fails_validation(self):
        doc_fake_live_price = {
            "doc_id": "test_007",
            "category": "market_prices",
            "title": "Tomato Mandi Price",
            "sub_category": "prices",
            "source_name": "Agmarknet",
            "organization": "DMI",
            "official_url": "https://agmarknet.gov.in",
            "is_live_fetched": False,
            "content_en": "Today's live price: Rs 45/kg in Azadpur Mandi. Highly volatile.",
            "guardrail_notice": "Prices fluctuate continuously.",
        }
        is_valid, errors = validate_document(doc_fake_live_price)
        self.assertFalse(is_valid)
        self.assertTrue(any("fabricate" in err.lower() for err in errors))


class TestDataIngestionPipeline(unittest.TestCase):
    """Test deduplication, batch ingestion, file loading, and offline resilience."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dataset_path = Path(self.temp_dir.name) / "test_knowledge.json"
        self.pipeline = DataIngestionPipeline(dataset_path=self.temp_dataset_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_ingest_and_persistence(self):
        doc = {
            "doc_id": "doc_temp_001",
            "category": "farming_practices",
            "title": "Bio-fertilizers and Phosphate Solubilizing Bacteria",
            "sub_category": "soil_fertility",
            "source_name": "ICAR — NCOF",
            "organization": "National Centre of Organic Farming",
            "official_url": "https://pgsindia-ncof.gov.in",
            "content_en": "PSB culture inoculates soil to solubilize insoluble phosphorus.",
            "guardrail_notice": "Do not mix bio-fertilizers with chemical fungicides.",
        }
        success, msg = self.pipeline.ingest(doc)
        self.assertTrue(success, f"Failed ingestion: {msg}")
        self.assertEqual(len(self.pipeline), 1)

        # Save and reload
        self.pipeline.save_dataset()
        new_pipeline = DataIngestionPipeline(dataset_path=self.temp_dataset_path)
        self.assertEqual(len(new_pipeline), 1)
        rec = new_pipeline.get_record("doc_temp_001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.title, "Bio-fertilizers and Phosphate Solubilizing Bacteria")

    def test_duplicate_doc_id_rejected_unless_overwrite(self):
        doc = {
            "doc_id": "doc_dup_001",
            "category": "crops",
            "title": "Wheat Sowing Guidelines",
            "sub_category": "cereals",
            "source_name": "ICAR-IIWBR",
            "organization": "ICAR",
            "official_url": "https://iiwbr.icar.gov.in",
            "content_en": "Wheat should be sown in November for optimal tillering.",
            "guardrail_notice": "Do not delay first irrigation.",
        }
        success1, _ = self.pipeline.ingest(doc)
        self.assertTrue(success1)

        # Duplicate doc_id without overwrite
        success2, msg2 = self.pipeline.ingest(doc, overwrite=False)
        self.assertFalse(success2)
        self.assertIn("already exists", msg2)

        # Overwrite=True succeeds
        success3, _ = self.pipeline.ingest(doc, overwrite=True)
        self.assertTrue(success3)

    def test_duplicate_title_and_url_fingerprint_rejected(self):
        doc1 = {
            "doc_id": "doc_fp_001",
            "category": "government_schemes",
            "title": "PM-KISAN Scheme Guidelines",
            "sub_category": "dbt",
            "source_name": "MoA&FW",
            "organization": "Ministry of Agriculture",
            "official_url": "https://pmkisan.gov.in",
            "content_en": "PM-KISAN provides Rs 6,000 per financial year in 3 installments.",
            "guardrail_notice": "Aadhaar e-KYC is mandatory.",
        }
        doc2 = {
            "doc_id": "doc_fp_002",  # different ID but same title and URL
            "category": "government_schemes",
            "title": "PM-KISAN Scheme Guidelines",
            "sub_category": "dbt",
            "source_name": "MoA&FW",
            "organization": "Ministry of Agriculture",
            "official_url": "https://pmkisan.gov.in",
            "content_en": "Different text but identical official document title and URL.",
            "guardrail_notice": "Aadhaar e-KYC is mandatory.",
        }
        self.assertTrue(self.pipeline.ingest(doc1)[0])
        success2, msg2 = self.pipeline.ingest(doc2)
        self.assertFalse(success2)
        self.assertIn("Duplicate document already exists", msg2)

    def test_offline_json_file_ingestion(self):
        sample_file = Path(self.temp_dir.name) / "offline_sample.json"
        sample_data = [
            {
                "doc_id": "offline_001",
                "category": "crops",
                "title": "Maize Intercropping Guidelines",
                "sub_category": "cereals",
                "source_name": "ICAR-IIMR",
                "organization": "Indian Institute of Maize Research",
                "official_url": "https://iimr.icar.gov.in",
                "content_en": "Intercropping maize with cowpea or soybean suppresses weed growth.",
                "guardrail_notice": "Ensure adequate nitrogen for both crops.",
            }
        ]
        sample_file.write_text(json.dumps(sample_data), encoding="utf-8")

        summary = self.pipeline.ingest_from_offline_file(sample_file)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["ingested"], 1)
        self.assertEqual(summary["failed_validation"], 0)
        self.assertIsNotNone(self.pipeline.get_record("offline_001"))

    def test_live_fetch_offline_resilience(self):
        """Verify that live fetching fails gracefully when network is unavailable without crashing."""
        success, msg = self.pipeline.fetch_and_ingest_live(
            url="https://icar.gov.in/test-non-existent-live-endpoint",
            category="crops",
            metadata={"title": "Test Live Advisory"},
            timeout=1.0,
        )
        self.assertFalse(success)
        # Should indicate offline / unreachable / failed rather than throwing an unhandled exception
        self.assertTrue("offline" in msg.lower() or "failed" in msg.lower() or "unreachable" in msg.lower())

    def test_all_official_seed_records_are_valid(self):
        """Assert that every curated seed record passes validation and has complete provenance."""
        seeds = get_official_curated_seed_records()
        self.assertGreaterEqual(len(seeds), 20, "Expected at least 20 official curated seed records")

        seen_ids = set()
        for rec in seeds:
            self.assertNotIn(rec["doc_id"], seen_ids, f"Duplicate seed doc_id: {rec['doc_id']}")
            seen_ids.add(rec["doc_id"])

            is_valid, errors = validate_document(rec)
            self.assertTrue(is_valid, f"Seed record '{rec['doc_id']}' failed validation: {errors}")
            self.assertTrue(rec["official_url"].startswith("http"), f"Invalid URL for '{rec['doc_id']}'")
            self.assertFalse(rec["is_live_fetched"], "Curated seed records must be marked is_live_fetched=False")
            self.assertEqual(rec["verification_status"], "verified_curated")
            self.assertTrue(len(rec["guardrail_notice"]) > 10, f"Guardrail notice missing for '{rec['doc_id']}'")


    def test_pdf_ingestion_and_text_extraction(self):
        """Verify that PDF documents are parsed, validated, and ingested successfully."""
        import zlib
        sample_pdf = Path(self.temp_dir.name) / "test_advisory.pdf"
        stream_content = b"BT /F1 12 Tf (ICAR IIWBR Wheat Package of Practices and Crown Root Irrigation Guidelines) Tj ET"
        comp_stream = zlib.compress(stream_content)

        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Length " + str(len(comp_stream)).encode() + b" /Filter /FlateDecode >>\nstream\n"
            + comp_stream + b"\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n"
            b"trailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n500\n%%EOF\n"
        )
        sample_pdf.write_bytes(pdf_bytes)

        # Direct extraction test
        extracted = extract_text_from_pdf(sample_pdf)
        self.assertIn("Wheat Package of Practices", extracted)

        # Ingestion through pipeline
        metadata = {
            "doc_id": "pdf_test_001",
            "category": "crops",
            "title": "Wheat Irrigation Advisory from PDF",
            "source_name": "ICAR-IIWBR",
            "organization": "Indian Council of Agricultural Research",
            "official_url": "https://iiwbr.icar.gov.in/wheat_advisory.pdf",
            "guardrail_notice": "Do not delay first irrigation past 25 days.",
        }
        summary = self.pipeline.ingest_from_offline_file(sample_pdf, metadata=metadata)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["ingested"], 1)
        self.assertEqual(summary["failed_validation"], 0)

        record = self.pipeline.get_record("pdf_test_001")
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Wheat Irrigation Advisory from PDF")
        self.assertIn("Crown Root Irrigation", record.content_en)

    def test_markdown_and_text_file_ingestion_with_frontmatter(self):
        """Verify that Markdown and text files with YAML frontmatter are ingested properly."""
        md_file = Path(self.temp_dir.name) / "drip_irrigation_guide.md"
        md_content = (
            "---\n"
            "doc_id: md_test_001\n"
            "category: farming_practices\n"
            "title: Micro Irrigation and Drip Fertigation Guide\n"
            "source_name: NCIPM — ICAR\n"
            "organization: National Research Centre for Integrated Pest Management\n"
            "official_url: https://ncipm.icar.gov.in/drip_guide\n"
            "guardrail_notice: Clean sand filters weekly to prevent emitter clogging.\n"
            "crops_applicable: [tomato, cotton, chili]\n"
            "---\n"
            "Drip irrigation delivers water directly to crop root zones with 90 percent water-use efficiency."
        )
        md_file.write_text(md_content, encoding="utf-8")

        summary = self.pipeline.ingest_from_offline_file(md_file)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["ingested"], 1)
        self.assertEqual(summary["failed_validation"], 0)

        rec = self.pipeline.get_record("md_test_001")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.category, "farming_practices")
        self.assertIn("tomato", rec.crops_applicable)
        self.assertIn("root zones", rec.content_en)


if __name__ == "__main__":
    unittest.main()

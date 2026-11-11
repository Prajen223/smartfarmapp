"""Tests for the agricultural NER module (ner_extractor.py).

Run with:   python -m pytest test_ner_extractor.py -v
or:         python -m unittest test_ner_extractor
"""

import unittest

from ner_extractor import extract_agricultural_entities, NERResult


class TestCropDetection(unittest.TestCase):
    """Verify crop entities are detected across scripts."""

    def test_english_single_crop(self):
        result = extract_agricultural_entities("How often should I water my tomato plants?")
        self.assertIn("tomato", result["crops"])
        self.assertEqual(result["pests"], [])

    def test_multiple_crops_english(self):
        result = extract_agricultural_entities(
            "I grow paddy and wheat in my field."
        )
        self.assertIn("paddy", result["crops"])
        self.assertIn("wheat", result["crops"])

    def test_tamil_crop_script(self):
        # தக்காளி = tomato, நெல் = paddy
        result = extract_agricultural_entities("தக்காளி சாகுபடியில் நெல் வயல்")
        self.assertIn("tomato", result["crops"])
        self.assertIn("paddy", result["crops"])

    def test_hindi_transliteration(self):
        result = extract_agricultural_entities("gehu aur dhan ki kheti")
        self.assertIn("wheat", result["crops"])
        self.assertIn("paddy", result["crops"])

    def test_hindi_script_crop(self):
        # गेहूं = wheat
        result = extract_agricultural_entities("मेरे गेहूं में कीड़े हैं")
        self.assertIn("wheat", result["crops"])

    def test_telugu_crop(self):
        # వరి = paddy
        result = extract_agricultural_entities("వరి పంట వివరాలు")
        self.assertIn("paddy", result["crops"])

    def test_no_crop_mentioned(self):
        result = extract_agricultural_entities("What is the weather today?")
        self.assertEqual(result["crops"], [])

    def test_sugarcane_and_groundnut(self):
        result = extract_agricultural_entities("sugarcane and groundnut cultivation in Maharashtra")
        self.assertIn("sugarcane", result["crops"])
        self.assertIn("groundnut", result["crops"])

    def test_crop_aliases(self):
        # "rice" is an alias for paddy
        result = extract_agricultural_entities("rice field irrigation methods")
        self.assertIn("paddy", result["crops"])


class TestPestDetection(unittest.TestCase):
    """Verify pest entities are detected correctly."""

    def test_english_pest(self):
        result = extract_agricultural_entities(
            "My tomato plants are attacked by aphids and whitefly."
        )
        self.assertIn("aphid", result["pests"])
        self.assertIn("whitefly", result["pests"])

    def test_stem_borer(self):
        result = extract_agricultural_entities("yellow stem borer in paddy crop")
        self.assertIn("stem_borer", result["pests"])

    def test_bollworm(self):
        result = extract_agricultural_entities(
            "pink bollworm infestation in cotton"
        )
        self.assertIn("pink_bollworm", result["pests"])
        self.assertIn("cotton", result["crops"])

    def test_tamil_pest_script(self):
        # அசுவினி = aphid
        result = extract_agricultural_entities("அசுவினி பூச்சி தாக்குதல்")
        self.assertIn("aphid", result["pests"])

    def test_helicoverpa_alias(self):
        result = extract_agricultural_entities("helicoverpa damage on fruit")
        self.assertIn("fruit_borer", result["pests"])

    def test_no_pest_mentioned(self):
        result = extract_agricultural_entities("how much water does paddy need?")
        self.assertEqual(result["pests"], [])

    def test_multiple_pests(self):
        result = extract_agricultural_entities(
            "thrips and mealybug on onion crop"
        )
        self.assertIn("thrips", result["pests"])
        self.assertIn("mealybug", result["pests"])


class TestDiseaseDetection(unittest.TestCase):
    """Verify disease entities are detected correctly."""

    def test_blight(self):
        result = extract_agricultural_entities(
            "early blight is affecting my tomato leaves"
        )
        self.assertIn("blight", result["diseases"])

    def test_powdery_mildew(self):
        result = extract_agricultural_entities("powdery mildew on grapes leaves")
        self.assertIn("powdery_mildew", result["diseases"])

    def test_wilt(self):
        result = extract_agricultural_entities("tomato wilt disease treatment")
        self.assertIn("wilt", result["diseases"])

    def test_rust(self):
        result = extract_agricultural_entities(
            "leaf rust is spreading in my wheat field"
        )
        self.assertIn("rust", result["diseases"])
        self.assertIn("wheat", result["crops"])

    def test_mosaic_virus(self):
        result = extract_agricultural_entities("mosaic virus in chili plants")
        self.assertIn("mosaic_virus", result["diseases"])
        self.assertIn("chili", result["crops"])

    def test_blast(self):
        result = extract_agricultural_entities("rice blast disease management")
        self.assertIn("blast", result["diseases"])

    def test_hindi_script_disease(self):
        # झुलसा = blight in Hindi
        result = extract_agricultural_entities("झुलसा रोग से बचाव कैसे करें")
        self.assertIn("blight", result["diseases"])

    def test_no_disease_mentioned(self):
        result = extract_agricultural_entities("how to apply urea to paddy?")
        self.assertEqual(result["diseases"], [])


class TestFertilizerDetection(unittest.TestCase):
    """Verify fertilizer entities are detected."""

    def test_urea(self):
        result = extract_agricultural_entities("how much urea should I apply to wheat?")
        self.assertIn("urea", result["fertilizers"])

    def test_dap(self):
        result = extract_agricultural_entities("DAP application rate for paddy")
        self.assertIn("dap", result["fertilizers"])

    def test_zinc_sulphate(self):
        result = extract_agricultural_entities("zinc deficiency in my paddy crop")
        self.assertIn("zinc_sulphate", result["fertilizers"])

    def test_bio_fertilizer(self):
        result = extract_agricultural_entities(
            "azospirillum seed treatment for paddy"
        )
        self.assertIn("bio_fertilizer", result["fertilizers"])

    def test_fym(self):
        result = extract_agricultural_entities(
            "apply farmyard manure before transplanting"
        )
        self.assertIn("fym", result["fertilizers"])

    def test_nske(self):
        result = extract_agricultural_entities("use neem oil to control whitefly")
        self.assertIn("nske", result["fertilizers"])

    def test_tamil_fertilizer_script(self):
        # யூரியா = urea
        result = extract_agricultural_entities("யூரியா எவ்வளவு போட வேண்டும்?")
        self.assertIn("urea", result["fertilizers"])

    def test_no_fertilizer_mentioned(self):
        result = extract_agricultural_entities("what are government schemes for farmers?")
        self.assertEqual(result["fertilizers"], [])


class TestLocationDetection(unittest.TestCase):
    """Verify Indian state/region detection."""

    def test_single_state(self):
        result = extract_agricultural_entities("paddy cultivation in Punjab")
        self.assertIn("punjab", result["locations"])

    def test_multiple_states(self):
        result = extract_agricultural_entities(
            "wheat grown in Punjab and Haryana"
        )
        self.assertIn("punjab", result["locations"])
        self.assertIn("haryana", result["locations"])

    def test_tamil_nadu(self):
        result = extract_agricultural_entities(
            "irrigation practices in Tamil Nadu"
        )
        self.assertIn("tamil nadu", result["locations"])

    def test_tamilnadu_no_space(self):
        result = extract_agricultural_entities("Tamilnadu farmer schemes")
        self.assertIn("tamil nadu", result["locations"])

    def test_maharashtra_alias(self):
        result = extract_agricultural_entities("soybean farming in Vidarbha region")
        self.assertIn("maharashtra", result["locations"])

    def test_no_location(self):
        result = extract_agricultural_entities("how to control aphids on tomato?")
        self.assertEqual(result["locations"], [])


class TestCombinedEntities(unittest.TestCase):
    """Test queries containing multiple entity types simultaneously."""

    def test_rich_query(self):
        text = (
            "My tomato and paddy plants in Punjab have blight and aphid infestation. "
            "Should I use urea or DAP?"
        )
        result = extract_agricultural_entities(text)
        self.assertIn("tomato", result["crops"])
        self.assertIn("paddy", result["crops"])
        self.assertIn("blight", result["diseases"])
        self.assertIn("aphid", result["pests"])
        self.assertIn("urea", result["fertilizers"])
        self.assertIn("dap", result["fertilizers"])
        self.assertIn("punjab", result["locations"])

    def test_empty_input(self):
        result = extract_agricultural_entities("")
        self.assertEqual(result["crops"], [])
        self.assertEqual(result["pests"], [])
        self.assertEqual(result["diseases"], [])
        self.assertEqual(result["fertilizers"], [])
        self.assertEqual(result["locations"], [])

    def test_return_type_is_correct(self):
        result = extract_agricultural_entities("tomato blight")
        self.assertIsInstance(result, dict)
        self.assertIn("crops", result)
        self.assertIn("pests", result)
        self.assertIn("diseases", result)
        self.assertIn("fertilizers", result)
        self.assertIn("locations", result)

    def test_case_insensitive_matching(self):
        result1 = extract_agricultural_entities("TOMATO blight UREA")
        result2 = extract_agricultural_entities("tomato blight urea")
        self.assertEqual(result1["crops"], result2["crops"])
        self.assertEqual(result1["diseases"], result2["diseases"])
        self.assertEqual(result1["fertilizers"], result2["fertilizers"])

    def test_no_duplicate_labels(self):
        # "rice blast disease" — 'rice' maps to paddy, 'blast' maps to blast
        result = extract_agricultural_entities("rice blast disease rice rice rice")
        self.assertEqual(len(result["crops"]), 1)  # paddy appears once
        self.assertEqual(len(result["diseases"]), 1)  # blast appears once


if __name__ == "__main__":
    unittest.main()

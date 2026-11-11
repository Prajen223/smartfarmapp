"""Tests for enhanced NER features: soil, scheme, Kannada script, and Hugging Face integration."""

import unittest
from ner_extractor import extract_agricultural_entities


class TestSoilDetection(unittest.TestCase):
    def test_english_soil_types(self):
        res = extract_agricultural_entities("Which crops grow well in black soil and alluvial soil?")
        self.assertIn("black", res["soil"])
        self.assertIn("alluvial", res["soil"])

    def test_hindi_soil(self):
        # काली मिट्टी = black soil, लाल मिट्टी = red soil
        res = extract_agricultural_entities("काली मिट्टी में कपास और लाल मिट्टी में मूंगफली")
        self.assertIn("black", res["soil"])
        self.assertIn("red", res["soil"])
        self.assertIn("cotton", res["crops"])
        self.assertIn("groundnut", res["crops"])

    def test_kannada_soil(self):
        # ಕಪ್ಪು ಮಣ್ಣು = black soil
        res = extract_agricultural_entities("ಕಪ್ಪು ಮಣ್ಣಿನಲ್ಲಿ ಯಾವ ಬೆಳೆ ಬೆಳೆಯಬಹುದು?")
        self.assertIn("black", res["soil"])

    def test_laterite_and_sandy(self):
        res = extract_agricultural_entities("laterite soil acidity and sandy soil drainage")
        self.assertIn("laterite", res["soil"])
        self.assertIn("sandy", res["soil"])


class TestSchemeDetection(unittest.TestCase):
    def test_english_schemes(self):
        res = extract_agricultural_entities("How to apply for PM-KISAN subsidy and PMFBY crop insurance?")
        self.assertIn("pm_kisan", res["schemes"])
        self.assertIn("pmfby", res["schemes"])

    def test_hindi_schemes(self):
        # पीएम किसान = PM Kisan, किसान क्रेडिट कार्ड = KCC
        res = extract_agricultural_entities("पीएम किसान योजना और किसान क्रेडिट कार्ड के नियम")
        self.assertIn("pm_kisan", res["schemes"])
        self.assertIn("kcc", res["schemes"])

    def test_kannada_schemes(self):
        # ಪಿಎಂ ಕಿಸಾನ್ = PM Kisan
        res = extract_agricultural_entities("ಪಿಎಂ ಕಿಸಾನ್ ಹಣ ಯಾವಾಗ ಬರುತ್ತದೆ?")
        self.assertIn("pm_kisan", res["schemes"])

    def test_soil_health_card_and_drip(self):
        res = extract_agricultural_entities("soil health card testing and PMKSY drip irrigation subsidy")
        self.assertIn("soil_health_card", res["schemes"])
        self.assertIn("pmksy", res["schemes"])


class TestKannadaEntities(unittest.TestCase):
    def test_kannada_crops(self):
        # ಭತ್ತ = paddy, ರಾಗಿ / ಗೋಧಿ = wheat, ಮೆಕ್ಕೆಜೋಳ = maize
        res = extract_agricultural_entities("ಭತ್ತ ಮತ್ತು ಗೋಧಿ ಬೆಳೆಗಳಿಗೆ ನೀರಾವರಿ")
        self.assertIn("paddy", res["crops"])
        self.assertIn("wheat", res["crops"])

    def test_kannada_pests(self):
        # ಬಿಳಿ ನೊಣ = whitefly, ಜೇಡ ಹುಳ = spider mite
        res = extract_agricultural_entities("ಬಿಳಿ ನೊಣ ಬಾಧೆ ನಿವಾರಣೆ")
        self.assertIn("whitefly", res["pests"])

    def test_kannada_diseases(self):
        # ಅಂಗಮಾರಿ = blight, ಬೂದು ರೋಗ = powdery mildew
        res = extract_agricultural_entities("ಟೊಮೆಟೊ ಅಂಗಮಾರಿ ರೋಗ ಮತ್ತು ಬೂದು ರೋಗ")
        self.assertIn("tomato", res["crops"])
        self.assertIn("blight", res["diseases"])
        self.assertIn("powdery_mildew", res["diseases"])


if __name__ == "__main__":
    unittest.main()

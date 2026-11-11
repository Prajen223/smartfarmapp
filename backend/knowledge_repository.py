"""Agricultural Knowledge Repository for Smart Farming Assistant.

Provides structured, verified agricultural documents organized into 6 core domains:
  1. Crops
  2. Soil
  3. Pests
  4. Diseases
  5. Farming Practices
  6. Government Schemes

Sources:
  • ICAR (Indian Council of Agricultural Research) Institutes (IARI, NRRI, CICR, IIHR, IISS)
  • Kisan Call Centre (KCC) Verified FAQs (1800-180-1551 / dackkms.gov.in)
  • Official Government Scheme Portals (pmkisan.gov.in, pmfby.gov.in, soilhealth.dac.gov.in, enam.gov.in)

Retrieval Ready:
  Every record includes rich metadata (doc_id, category, sub_category, crops_applicable,
  soil_types_applicable, tags, verified_date, official_url) ready for semantic and vector
  retrieval in RAG architectures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class SourceAttribution:
    name: str
    organization: str
    official_url: str
    verified_date: str
    access_note: str


@dataclass
class KnowledgeDocument:
    doc_id: str
    category: str  # "crops" | "soil" | "pests" | "diseases" | "farming_practices" | "government_schemes"
    title: str
    sub_category: str
    crops_applicable: list[str] = field(default_factory=list)
    soil_types_applicable: list[str] = field(default_factory=list)
    nutrients_applicable: list[str] = field(default_factory=list)
    seasons_applicable: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    content_en: str = ""
    content_hi: str = ""
    content_kn: str = ""
    content_ta: str = ""
    source: SourceAttribution = field(
        default_factory=lambda: SourceAttribution(
            name="ICAR",
            organization="Central Research Institute",
            official_url="https://icar.gov.in",
            verified_date="2026-03",
            access_note="Public scientific advisory"
        )
    )
    guardrail_notice: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# In-memory corpus of structured, verified documents
DOCUMENT_CORPUS: list[KnowledgeDocument] = [
    # ── 1. CROPS ──────────────────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_crop_001",
        category="crops",
        title="Paddy (Rice) Package of Practices & Water Aeration",
        sub_category="cereals",
        crops_applicable=["paddy"],
        soil_types_applicable=["clay", "clay_loam", "alluvial"],
        tags=["paddy", "rice", "awd", "n-p-k", "nursery", "transplanting"],
        content_en=(
            "Package of Practices for Paddy (Rice):\n"
            "• Sowing & Seed Rate: 10-12 kg/acre for SRI or 20-25 kg/acre for traditional transplanting.\n"
            "• Water Management: Adopt Alternate Wetting and Drying (AWD). Keep 2-3 cm shallow water during "
            "tillering and panicle initiation, then allow soil to develop hairline cracks before re-watering.\n"
            "• Nutrient Schedule: Apply Nitrogen in 3 split doses (50% basal, 25% active tillering, 25% panicle initiation).\n"
            "• Zinc Deficiency: If lower leaves exhibit reddish-brown bronzing, spray 0.5% Zinc Sulphate + 0.25% lime solution."
        ),
        content_hi=(
            "धान की वैज्ञानिक खेती और जल प्रबंधन:\n"
            "• बीज दर: श्री (SRI) विधि के लिए 10-12 किग्रा/एकड़, सामान्य रोपाई के लिए 20-25 किग्रा/एकड़।\n"
            "• जल प्रबंधन: लगातार जलभराव से बचें। कल्ले फूटते समय हल्का पानी रखें और बीच-बीच में खेत में हवा लगने दें।\n"
            "• उर्वरक: यूरिया को तीन भागों में दें (बुवाई/रोपाई, कल्ले फूटते समय, और बाली निकलते समय)।\n"
            "• जिंक की कमी: पत्तियों पर कत्थई धब्बे दिखने पर जिंक सल्फेट (0.5%) का छिड़काव करें।"
        ),
        content_kn=(
            "ಭತ್ತದ ವೈಜ್ಞಾನಿಕ ಕೃಷಿ ಮತ್ತು ನೀರು ನಿರ್ವಹಣೆ:\n"
            "• ಬಿತ್ತನೆ ಬೀಜದ ಪ್ರಮಾಣ: ಸಾಂಪ್ರದಾಯಿಕ ನಾಟಿಗೆ ಎಕರೆಗೆ 20-25 ಕೆಜಿ, ಎಸ್.ಆರ್.ಐ (SRI) ಪದ್ಧತಿಗೆ 10-12 ಕೆಜಿ.\n"
            "• ನೀರಿನ ನಿರ್ವಹಣೆ: ನಿರಂತರ ನೀರು ನಿಲ್ಲಿಸುವ ಬದಲು ಆವರ್ತಕ ತೇವ-ಒಣ ಪದ್ಧತಿ (AWD) ಅನುಸರಿಸಿ.\n"
            "• ರಸಗೊಬ್ಬರ: ಸಾರಜನಕವನ್ನು ಮೂರು ಕಂತುಗಳಲ್ಲಿ ನೀಡಿ (ನಾಟಿ ವೇಳೆ, ತೆನೆ ಕಟ್ಟುವ ಮುನ್ನ).\n"
            "• ಸತು (Zinc) ಕೊರತೆ: ಎಲೆಗಳಲ್ಲಿ ಕಂದು ಬಣ್ಣದ ಚುಕ್ಕೆಗಳು ಕಂಡುಬಂದರೆ ಜಿಂಕ್ ಸಲ್ಫೇಟ್ ಸಿಂಪಡಿಸಿ."
        ),
        source=SourceAttribution(
            name="ICAR — National Rice Research Institute (NRRI)",
            organization="Central Agricultural Research Institute",
            official_url="https://nrri.nic.in",
            verified_date="2026-02",
            access_note="Compiled from ICAR-NRRI Package of Practices for Rice."
        ),
        guardrail_notice="Exact fertilizer dose should be calibrated to your Soil Health Card test values.",
    ),
    KnowledgeDocument(
        doc_id="doc_crop_002",
        category="crops",
        title="Wheat Cultivation and Critical Crown Root Initiation (CRI)",
        sub_category="cereals",
        crops_applicable=["wheat"],
        soil_types_applicable=["alluvial", "loamy", "clay_loam"],
        tags=["wheat", "cri", "irrigation", "timely_sowing", "rust"],
        content_en=(
            "Wheat Agronomy & Irrigation Timing:\n"
            "• Sowing Window: Optimal sowing is between November 1 and November 20 in Northern plains.\n"
            "• Critical Stage: Crown Root Initiation (CRI) occurs at 20-25 days after sowing. First irrigation at this stage is mandatory for tiller survival.\n"
            "• Subsequent Irrigations: Tillering (40-45 DAS), Jointing (60-65 DAS), Flowering (80-85 DAS), and Milk/Grain filling (100-105 DAS).\n"
            "• Fertilizer: Apply full dose of P and K with 1/3rd Nitrogen at basal sowing; remaining N in two top-dressings."
        ),
        content_hi=(
            "गेहूं की फसल और क्रांतिक सिंचाई चरण:\n"
            "• बुवाई का समय: 1 नवंबर से 20 नवंबर सर्वोत्तम समय है।\n"
            "• क्राउन रूट दीक्षा (CRI चरण): बुवाई के 20-25 दिन बाद पहली सिंचाई अत्यंत आवश्यक है।\n"
            "• उर्वरक: फास्फोरस व पोटाश की पूरी मात्रा तथा यूरिया का 1/3 भाग बुवाई के समय दें, शेष यूरिया दो बार में सिंचाई के साथ दें।"
        ),
        content_kn=(
            "ಗೋಧಿ ಬೆಳೆ ಮತ್ತು ನೀರಾವರಿ ನಿರ್ವಹಣೆ:\n"
            "• ಬಿತ್ತನೆ ಸಮಯ: ನವೆಂಬರ್ ತಿಂಗಳು ಸೂಕ್ತ.\n"
            "• ಮೊದಲ ನೀರಾವರಿ: ಬಿತ್ತನೆಯಾದ 20-25 ದಿನಗಳಲ್ಲಿ (ಬೇರು ಬೇರೂರುವ ಹಂತ) ನೀರುಣಿಸುವುದು ಅತ್ಯಂತ ಮುಖ್ಯ.\n"
            "• ಗೊಬ್ಬರ: ಡಿಎಪಿ ಮತ್ತು ಪೊಟ್ಯಾಷ್ ಬಿತ್ತನೆ ವೇಳೆ ಪೂರ್ಣವಾಗಿ, ಯೂರಿಯಾವನ್ನು ಕಂತುಗಳಲ್ಲಿ ನೀಡಿ."
        ),
        source=SourceAttribution(
            name="ICAR — Indian Institute of Wheat and Barley Research (IIWBR)",
            organization="Central Agricultural Research Institute",
            official_url="https://iiwbr.icar.gov.in",
            verified_date="2026-01",
            access_note="ICAR-IIWBR Wheat agronomy and irrigation guidelines."
        ),
        guardrail_notice="Do not delay the first irrigation past 25 days post-sowing, as crown root starvation permanently reduces yield.",
    ),
    KnowledgeDocument(
        doc_id="doc_crop_003",
        category="crops",
        title="Tomato Cultivation, Staking, and Fruit Setting",
        sub_category="vegetables",
        crops_applicable=["tomato"],
        soil_types_applicable=["red", "loamy", "alluvial", "black"],
        tags=["tomato", "staking", "blossom_end_rot", "calcium", "drip"],
        content_en=(
            "Tomato Production Guidelines:\n"
            "• Nursery Management: Raise seedlings under 40-mesh insect-proof nylon net to protect against whitefly and Leaf Curl Virus.\n"
            "• Transplanting: 25-30 days old healthy seedlings with 60x45 cm spacing.\n"
            "• Staking: Support plants with bamboo sticks or wire trellises at 30 days to avoid soil contact and fruit rot.\n"
            "• Irrigation: Regular, uniform moisture is critical. Irregular watering causes Blossom End Rot (Calcium deficiency) and fruit cracking."
        ),
        content_hi=(
            "टमाटर की खेती और फल प्रबंधन:\n"
            "• नर्सरी: सफेद मक्खी से बचाव के लिए कीट-रोधी जाली के नीचे पौधे तैयार करें।\n"
            "• रोपाई: 25-30 दिन पुराने स्वस्थ पौधों को 60x45 सेमी दूरी पर लगाएं।\n"
            "• सहारा (स्टेकिंग): 30 दिन बाद पौधों को बांस या सुतली का सहारा दें ताकि फल जमीन को न छुएं।\n"
            "• सिंचाई: संतुलित सिंचाई करें। अचानक भारी सिंचाई से फल फटने लगते हैं।"
        ),
        content_kn=(
            "ಟೊಮೆಟೊ ಬೆಳೆ ಮತ್ತು ನಿರ್ವಹಣೆ:\n"
            "• ನರ್ಸರಿ: ಬಿಳಿ ನೊಣದಿಂದ ಬರುವ ಎಲೆ ಮುರುಟು ರೋಗ ತಡೆಯಲು ರಕ್ಷಣಾತ್ಮಕ ಜಾಲರಿ ಬಳಸಿ.\n"
            "• ನಾಟಿ: 25-30 ದಿನಗಳ ಸಸಿಗಳನ್ನು ನಾಟಿ ಮಾಡಿ.\n"
            "• ಆಸರೆ ಕಟ್ಟುವುದು: ಗಿಡಗಳು ನೆಲಕ್ಕೆ ತಾಗದಂತೆ ಕೋಲು ಅಥವಾ ತಂತಿಯ ಆಸರೆ ನೀಡಿ.\n"
            "• ನೀರುಣಿಕೆ: ಹನಿ ನೀರಾವರಿ ಮೂಲಕ ಸ್ಥಿರ ತೇವಾಂಶ ಕಾಪಾಡಿ."
        ),
        source=SourceAttribution(
            name="ICAR — Indian Institute of Horticultural Research (IIHR)",
            organization="Horticultural Research Institute",
            official_url="https://iihr.res.in",
            verified_date="2026-03",
            access_note="IIHR Tomato Production Technology."
        ),
        guardrail_notice="Always inspect undersides of tomato leaves weekly for early whitefly vectors.",
    ),

    # ── 2. SOIL ───────────────────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_soil_001",
        category="soil",
        title="Black Cotton Soil (Regur) Properties and Drainage Management",
        sub_category="soil_types",
        crops_applicable=["cotton", "soybean", "sugarcane", "paddy", "chickpea"],
        soil_types_applicable=["black"],
        tags=["black_soil", "regur", "clay", "montmorillonite", "drainage", "cotton"],
        content_en=(
            "Black Cotton Soil (Regur) Agronomy:\n"
            "• Properties: High clay content (predominantly montmorillonite), excellent moisture retention, high cation exchange capacity (CEC).\n"
            "• Physical Behavior: Swells strongly when wet and develops deep, wide cracks when dry, facilitating self-ploughing and aeration.\n"
            "• Challenges: Highly prone to waterlogging and compaction when wet; difficult to work immediately after heavy rainfall.\n"
            "• Management: Provide broad bed and furrow (BBF) systems for drainage. Avoid over-irrigation. Apply gypsum if sodicity (ESP > 15) is detected."
        ),
        content_hi=(
            "काली मिट्टी (रेगुर) की विशेषताएं और प्रबंधन:\n"
            "• गुण: उच्च जलधारण क्षमता, भारी चिकनी मिट्टी, पोटाश और चूने से भरपूर।\n"
            "• व्यवहार: गीली होने पर फूलती है और सूखने पर गहरी दरारें पड़ती हैं।\n"
            "• समस्या: जलभराव की समस्या।\n"
            "• प्रबंधन: जल निकासी के लिए मेड़ व नाली (BBF) पद्धति अपनाएं। खेत में पानी रुकने न दें।"
        ),
        content_kn=(
            "ಕಪ್ಪು ಹತ್ತಿ ಮಣ್ಣು (ರೆಗೂರ್) ನಿರ್ವಹಣೆ:\n"
            "• ಗುಣಲಕ್ಷಣ: ಹೆಚ್ಚಿನ ತೇವಾಂಶ ಹಿಡಿದಿಟ್ಟುಕೊಳ್ಳುವ ಸಾಮರ್ಥ್ಯ, ಜೇಡಿ ಅಂಶ ಅಧಿಕ.\n"
            "• ವರ್ತನೆ: ಒಣಗಿದಾಗ ಆಳವಾದ ಬಿರುಕುಗಳು ಬೀಳುತ್ತವೆ, ನೆನೆದಾಗ ಜಿಗುಟಾಗುತ್ತದೆ.\n"
            "• ನಿರ್ವಹಣೆ: ನೀರು ನಿಲ್ಲದಂತೆ ಬಸಿಗಾಲುವೆ (Drainage) ವ್ಯವಸ್ಥೆ ಮಾಡಿ."
        ),
        source=SourceAttribution(
            name="ICAR — Indian Institute of Soil Science (IISS)",
            organization="National Soil Research Institute",
            official_url="https://iiss.icar.gov.in",
            verified_date="2026-02",
            access_note="ICAR-IISS Soil Management Bulletins."
        ),
        guardrail_notice="Do not enter black cotton fields with heavy machinery when soil moisture is above field capacity.",
    ),
    KnowledgeDocument(
        doc_id="doc_soil_002",
        category="soil",
        title="Soil Health Card Testing & Balanced Nutrient Management",
        sub_category="soil_health",
        crops_applicable=[],
        soil_types_applicable=["alluvial", "black", "red", "laterite", "sandy"],
        tags=["soil_health_card", "soil_testing", "ph", "organic_carbon", "npk", "zinc"],
        content_en=(
            "Soil Health Card (SHC) Protocol:\n"
            "• 12 Parameters Analyzed: Primary nutrients (N, P, K), Secondary nutrient (S), Micronutrients (Zn, Fe, Cu, Mn, Bo), and Physical parameters (pH, EC, Organic Carbon).\n"
            "• Sampling Procedure: Take 8-10 'V' shaped soil core samples per acre from 0-15 cm depth. Thoroughly mix, quarter down to 500 grams, dry in shade, and label.\n"
            "• pH Correction: For acidic soils (pH < 6.0), apply agricultural lime or dolomite. For alkaline soils (pH > 8.5), incorporate gypsum with leaching.\n"
            "• Organic Carbon (OC): Target OC > 0.75%. If below 0.5%, incorporate 4-5 tons/acre of well-rotted FYM, vermicompost, or green manure."
        ),
        content_hi=(
            "मृदा स्वास्थ्य कार्ड (Soil Health Card) और संतुलित पोषण:\n"
            "• 12 मानक: नाइट्रोजन, फास्फोरस, पोटाश, सल्फर, जिंक, लोहा, तांबा, मैंगनीज, बोरोन, पीएच, ईसी, जैविक कार्बन।\n"
            "• नमूना लेने की विधि: खेत में 8-10 स्थानों से 'V' आकार में 15 सेमी गहराई से मिट्टी लें। अच्छी तरह मिलाकर 500 ग्राम नमूना प्रयोगशाला भेजें।\n"
            "• जैविक कार्बन: मिट्टी में जैविक खाद (गोबर की खाद या केंचुआ खाद) नियमित रूप से मिलाएं।"
        ),
        content_kn=(
            "ಮಣ್ಣು ಆರೋಗ್ಯ ಕಾರ್ಡ್ ಮತ್ತು ಪೋಷಕಾಂಶಗಳ ಸಮತೋಲನ:\n"
            "• 12 ಪರೀಕ್ಷೆಗಳು: ಸಾರಜನಕ, ರಂಜಕ, ಪೊಟ್ಯಾಷ್, ಲಘು ಪೋಷಕಾಂಶಗಳು ಮತ್ತು ಸಾವಯವ ಇಂಗಾಲ.\n"
            "• ಮಣ್ಣಿನ ಮಾದರಿ: 15 ಸೆಂ.ಮೀ ಆಳದಲ್ಲಿ 'V' ಆಕಾರದಲ್ಲಿ ಮಾದರಿ ಸಂಗ್ರಹಿಸಿ ನೆರಳಿನಲ್ಲಿ ಒಣಗಿಸಿ ಪರೀಕ್ಷೆಗೆ ಕಳುಹಿಸಿ."
        ),
        source=SourceAttribution(
            name="Ministry of Agriculture & Farmers Welfare — Soil Health Division",
            organization="Central Government Scheme Directorate",
            official_url="https://soilhealth.dac.gov.in",
            verified_date="2026-03",
            access_note="Official Government Soil Health Card operational guidelines."
        ),
        guardrail_notice="Soil samples must always be dried in shade, never under direct sun or oven heat.",
    ),

    # ── 3. PESTS ──────────────────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_pest_001",
        category="pests",
        title="Integrated Pest Management (IPM) for Sucking Pests (Aphids, Whiteflies, Thrips)",
        sub_category="sucking_pests",
        crops_applicable=["tomato", "chili", "cotton", "brinjal", "okra"],
        soil_types_applicable=[],
        tags=["aphids", "whiteflies", "thrips", "ipm", "sticky_traps", "nske", "neem_oil"],
        content_en=(
            "IPM Protocol for Sucking Pests:\n"
            "• Symptoms: Yellowing, leaf curling, crinkling, sooty mold on honeydew secretions, and transmission of viral diseases.\n"
            "• Mechanical Control: Install 10-12 yellow sticky traps per acre for whiteflies/aphids and blue sticky traps for thrips at canopy height.\n"
            "• Botanical Sprays: Spray 5% Neem Seed Kernel Extract (NSKE) or cold-pressed Neem Oil (10,000 ppm) at 3 ml/liter early in the morning.\n"
            "• Biological Predators: Conserve ladybird beetles and green lacewings (Chrysoperla carnea); avoid broad-spectrum pyrethroid insecticides which wipe out natural enemies."
        ),
        content_hi=(
            "रस चूसक कीटों (माहू, सफेद मक्खी, थ्रिप्स) का एकीकृत प्रबंधन:\n"
            "• लक्षण: पत्तियों का मुड़ना, पीला पड़ना, वायरस का फैलाव।\n"
            "• चिपचिपे प्रपंच: सफेद मक्खी व माहू के लिए पीले और थ्रिप्स के लिए नीले स्टिकी ट्रैप (10-12 प्रति एकड़) लगाएं।\n"
            "• प्राकृतिक उपचार: 5% नीम के बीज का अर्क (NSKE) या नीम तेल (3 मिली/लीटर) का छिड़काव करें।"
        ),
        content_kn=(
            "ರಸಹೀರುವ ಕೀಟಗಳ (ಗಿಡಹೇನು, ಬಿಳಿ ನೊಣ, ಥ್ರಿಪ್ಸ್) ಸಮಗ್ರ ನಿಯಂತ್ರಣ:\n"
            "• ಹಳದಿ ಮತ್ತು ನೀಲಿ ಬಣ್ಣದ ಅಂಟು ಬಲೆಗಳನ್ನು (ಎಕರೆಗೆ 10-12) ಬೆಳೆಯ ಎತ್ತರಕ್ಕೆ ತಕ್ಕಂತೆ ಅಳವಡಿಸಿ.\n"
            "• ಆರಂಭಿಕ ಹಂತದಲ್ಲಿ ಶೇ. 5 ರ ಬೇವಿನ ಬೀಜದ ಕಷಾಯ (NSKE) ಅಥವಾ ಬೇವಿನ ಎಣ್ಣೆ ಸಿಂಪಡಿಸಿ."
        ),
        source=SourceAttribution(
            name="ICAR — National Research Centre for Integrated Pest Management (NCIPM)",
            organization="Central Pest Management Institute",
            official_url="https://ncipm.icar.gov.in",
            verified_date="2026-02",
            access_note="NCIPM IPM validation guidelines for vegetable and field crops."
        ),
        guardrail_notice="Never spray synthetic insecticides during peak bee-pollination hours (8 AM - 11 AM).",
    ),
    KnowledgeDocument(
        doc_id="doc_pest_002",
        category="pests",
        title="Pink Bollworm & Stem Borer Monitoring and Biological Control",
        sub_category="borers",
        crops_applicable=["cotton", "paddy", "maize"],
        soil_types_applicable=[],
        tags=["pink_bollworm", "stem_borer", "borers", "pheromone_trap", "trichogramma"],
        content_en=(
            "Borer Pest Management Guidelines:\n"
            "• Pheromone Trapping: Install 4-5 sex-pheromone traps per acre for early monitoring. Economic threshold (ETL) is 8 moths/trap/night for 3 consecutive nights.\n"
            "• Egg Parasitoids: Release Trichogramma chilonis / Trichogramma japonicum cards at 50,000 parasitized eggs/acre at 7-10 day intervals starting at early squaring or tillering.\n"
            "• Cultural Sanitation: Shred and destroy crop stalks immediately after harvest to eliminate overwintering diapausing larvae."
        ),
        content_hi=(
            "गुलाबी इल्ली और तना छेदक का नियंत्रण:\n"
            "• फेरोमोन ट्रैप: कीट निगरानी के लिए 4-5 फेरोमोन ट्रैप प्रति एकड़ लगाएं।\n"
            "• जैविक परजीवी: ट्राइकोग्रामा परजीवी कार्ड का प्रयोग करें।\n"
            "• खेत की सफाई: फसल कटाई के तुरंत बाद अवशेषों को नष्ट करें ताकि लार्वा अगली फसल में न पहुंचे।"
        ),
        content_kn=(
            "ಗುಲಾಬಿ ಕಾಯಿಕೊರಕ ಮತ್ತು ಕಾಂಡ ಕೊರೆಯುವ ಹುಳು ನಿಯಂತ್ರಣ:\n"
            "• ಮೋಹಕ ಬಲೆಗಳು (Pheromone traps): ಎಕರೆಗೆ 4-5 ಬಲೆಗಳನ್ನು ಅಳವಡಿಸಿ ಕೀಟಗಳ ಸಂಖ್ಯೆ ಗಮನಿಸಿ.\n"
            "• ಟ್ರೈಕೋಡರ್ಮಾ / ಟ್ರೈಕೋಗ್ರಾಮಾ ಪರಾವಲಂಬಿ ಕಾರ್ಡ್‌ಗಳನ್ನು ಬಳಸಿ ನೈಸರ್ಗಿಕ ನಿಯಂತ್ರಣ ಮಾಡಿ."
        ),
        source=SourceAttribution(
            name="ICAR — Central Institute for Cotton Research (CICR)",
            organization="Commodity Research Institute",
            official_url="https://cicr.icar.gov.in",
            verified_date="2026-01",
            access_note="ICAR-CICR Pink Bollworm advisory and management bulletins."
        ),
        guardrail_notice="Chemical intervention should only be initiated if trap catches cross ETL levels.",
    ),

    # ── 4. DISEASES ───────────────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_disease_001",
        category="diseases",
        title="Early Blight & Late Blight Management in Solanaceous Crops",
        sub_category="fungal_diseases",
        crops_applicable=["tomato", "potato"],
        soil_types_applicable=[],
        tags=["early_blight", "late_blight", "blight", "alternaria", "phytophthora", "copper_oxychloride"],
        content_en=(
            "Blight Disease Management in Tomato and Potato:\n"
            "• Early Blight (Alternaria solani): Produces concentric target-board brown rings on older lower leaves. Favored by high humidity and moderate temperatures.\n"
            "• Late Blight (Phytophthora infestans): Water-soaked lesions turning dark brown/black with white fungal growth on undersides in cool, foggy weather.\n"
            "• Preventative Cultural Measures: Avoid overhead irrigation; water only roots. Prune lower diseased foliage. Maintain plant spacing for airflow.\n"
            "• Organic/Preventative Spray: Spray Copper Oxychloride (2.5 g/liter) or Mancozeb (2 g/liter) as protective sprays at first sign of cloudy, humid conditions."
        ),
        content_hi=(
            "टमाटर और आलू में झुलसा (Blight) रोग का प्रबंधन:\n"
            "• अगेती झुलसा: निचली पत्तियों पर गोल छल्लेदार भूरे धब्बे बनते हैं।\n"
            "• पछेती झुलसा: ठंडे और नम मौसम में पत्तियों पर काले-भूरे धब्बे और सफेद फफूंद दिखती है।\n"
            "• रोकथाम: पत्तियों पर पानी न डालें, केवल जड़ों में दें। कॉपर ऑक्सीक्लोराइड का छिड़काव सुरक्षात्मक रूप से करें।"
        ),
        content_kn=(
            "ಅಂಗಮಾರಿ ರೋಗ (Early & Late Blight) ನಿರ್ವಹಣೆ:\n"
            "• ಆರಂಭಿಕ ಹಂತದಲ್ಲಿ ಎಲೆಗಳ ಮೇಲೆ ಕಂದು ಬಣ್ಣದ ವೃತ್ತಾಕಾರದ ಚುಕ್ಕೆಗಳು ಕಾಣಿಸಿಕೊಳ್ಳುತ್ತವೆ.\n"
            "• ಗಿಡದ ಎಲೆಗಳಿಗೆ ನೀರು ತಾಗದಂತೆ ಬುಡಕ್ಕೆ ನೀರು ಹಾಯಿಸಿ. ತಾಮ್ರಯುಕ್ತ ಶಿಲೀಂಧ್ರನಾಶಕಗಳನ್ನು ನಿಯಮಾನುಸಾರ ಸಿಂಪಡಿಸಿ."
        ),
        source=SourceAttribution(
            name="ICAR — Central Potato Research Institute (CPRI)",
            organization="Central Agricultural Institute",
            official_url="https://cpri.icar.gov.in",
            verified_date="2026-02",
            access_note="CPRI Late Blight Decision Support System."
        ),
        guardrail_notice="Do not apply fungicide sprays immediately before rain. Always respect minimum pre-harvest intervals.",
    ),
    KnowledgeDocument(
        doc_id="doc_disease_002",
        category="diseases",
        title="Rice Blast and Wheat Rust Disease Management",
        sub_category="fungal_diseases",
        crops_applicable=["paddy", "wheat"],
        soil_types_applicable=[],
        tags=["rice_blast", "wheat_rust", "blast", "rust", "seed_treatment"],
        content_en=(
            "Blast and Rust Protocols:\n"
            "• Rice Blast (Magnaporthe oryzae): Diamond/spindle-shaped lesions with grey centers and brown borders. Leaf, node, and neck blast stages. Moderate Nitrogen applications to prevent susceptibility.\n"
            "• Wheat Rust (Puccinia spp.): Yellow stripe rust, brown leaf rust, or black stem rust pustules. Plant approved rust-resistant varieties for your zone.\n"
            "• Seed Treatment: Treat seeds with Pseudomonas fluorescens or Trichoderma viride at 10 g/kg seed before sowing to suppress seed-borne inoculum."
        ),
        content_hi=(
            "धान का झोंका (ब्लास्ट) और गेहूं का रतुआ (रस्ट) रोग:\n"
            "• धान का झोंका: पत्तियों पर आंख के आकार के धब्बे। अत्यधिक यूरिया के प्रयोग से बचें।\n"
            "• गेहूं का रतुआ: पत्तियों पर पीली या भूरी धारियां। प्रमाणित रोग-रोधी किस्मों की ही बुवाई करें।\n"
            "• बीज उपचार: बुवाई से पहले बीजों का ट्राइकोडर्मा या स्यूडोमोनास से उपचार अवश्य करें।"
        ),
        content_kn=(
            "ಭತ್ತದ ಬ್ಲಾಸ್ಟ್ (ಬೆಂಕಿ ರೋಗ) ಮತ್ತು ಗೋಧಿಯ ತುಕ್ಕು ರೋಗ:\n"
            "• ಸಾರಜನಕ ಗೊಬ್ಬರದ ಅತಿಯಾದ ಬಳಕೆಯನ್ನು ತಪ್ಪಿಸಿ.\n"
            "• ಬಿತ್ತನೆಗೆ ಮುನ್ನ ಬೀಜೋಪಚಾರ ಮಾಡುವುದು ರೋಗ ಬರದಂತೆ ತಡೆಯಲು ಮುಖ್ಯ."
        ),
        source=SourceAttribution(
            name="ICAR — Indian Agricultural Research Institute (IARI)",
            organization="Premier National Agricultural Institute",
            official_url="https://iari.res.in",
            verified_date="2026-01",
            access_note="IARI Division of Plant Pathology advisories."
        ),
        guardrail_notice="Never use uncertified seed saved from fields that suffered severe blast or rust outbreaks.",
    ),

    # ── 5. FARMING PRACTICES ──────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_practice_001",
        category="farming_practices",
        title="Micro-Irrigation Engineering (Drip and Sprinkler) & Fertigation",
        sub_category="water_management",
        crops_applicable=["tomato", "cotton", "banana", "sugarcane", "chili", "maize"],
        soil_types_applicable=["alluvial", "black", "red", "sandy", "loamy"],
        tags=["drip_irrigation", "sprinkler", "fertigation", "water_saving", "pmksy"],
        content_en=(
            "Drip Irrigation and Fertigation System Architecture:\n"
            "• Water Saving: Saves 40% to 60% irrigation water compared to surface flooding, reducing weed proliferation and evaporation loss.\n"
            "• Uniform Distribution: Pressure-compensating drippers deliver water and soluble nutrients directly to the active root zone.\n"
            "• Fertigation Schedule: Apply 100% water-soluble fertilizers (e.g. 19-19-19, Urea, Potassium Nitrate) in small weekly increments, boosting nutrient use efficiency by 30-40%.\n"
            "• Maintenance: Flush sub-mains and laterals bi-weekly. Clean disk/screen filters weekly. Treat with dilute acid (0.1% hydrochloric or phosphoric acid) once a season to clear mineral scaling."
        ),
        content_hi=(
            "टपक (ड्रिप) व फव्वारा सिंचाई प्रणाली और फर्टीगेशन:\n"
            "• जल बचत: पारंपरिक बाढ़ सिंचाई की तुलना में 40% से 60% पानी की बचत।\n"
            "• फर्टीगेशन: घुलनशील खादों को ड्रिप के पानी के साथ सीधे जड़ों तक पहुंचाएं, जिससे खाद की बर्बादी रुकती है।\n"
            "• रखरखाव: जाली वाले फिल्टर की साप्ताहिक सफाई करें और ड्रिप पाइपों को महीने में एक बार फ्लश करें।"
        ),
        content_kn=(
            "ಹನಿ ನೀರಾವರಿ ಮತ್ತು ಗೊಬ್ಬರ ನೀಡುವಿಕೆ (ಫರ್ಟಿಗೇಷನ್):\n"
            "• ಶೇ. 40 ರಿಂದ 60 ರಷ್ಟು ನೀರು ಉಳಿತಾಯವಾಗುತ್ತದೆ ಮತ್ತು ಕಳೆ ನಿಯಂತ್ರಣ ಸುಲಭವಾಗುತ್ತದೆ.\n"
            "• ನೀರಿನಲ್ಲಿ ಕರಗುವ ಗೊಬ್ಬರಗಳನ್ನು ಹನಿ ನೀರಾವರಿ ಮೂಲಕ ಗಿಡದ ಬೇರುಗಳಿಗೆ ನೇರವಾಗಿ ತಲುಪಿಸಬಹುದು."
        ),
        source=SourceAttribution(
            name="National Mission on Micro Irrigation — MoA&FW",
            organization="Central Mission Directorate",
            official_url="https://pmksy.gov.in",
            verified_date="2026-02",
            access_note="Operational Guidelines for Per Drop More Crop (Micro Irrigation)."
        ),
        guardrail_notice="Never inject raw insoluble DAP or single superphosphate into drip lines without pre-filtration.",
    ),
    KnowledgeDocument(
        doc_id="doc_practice_002",
        category="farming_practices",
        title="Crop Rotation, Green Manuring, and Bio-fertilizers",
        sub_category="soil_fertility",
        crops_applicable=[],
        soil_types_applicable=["alluvial", "black", "red", "laterite", "sandy"],
        tags=["crop_rotation", "green_manure", "dhaincha", "rhizobium", "azospirillum", "psb"],
        content_en=(
            "Ecological Soil Fertility Management:\n"
            "• Legume Crop Rotation: Alternate exhaustive cereal crops (paddy, wheat, maize) with pulses (gram, moong, cowpea) to fix 30-50 kg/ha atmospheric Nitrogen.\n"
            "• In-Situ Green Manuring: Sow Dhaincha (Sesbania aculeata) or Sunnhemp (Crotalaria juncea) at onset of pre-monsoon rains. Incorporate into soil at 45-50 days before flowering to add 15-20 tons/ha green biomass.\n"
            "• Bio-fertilizer Inoculation: Use Rhizobium for pulses, Azospirillum / Azotobacter for cereals, and Phosphate Solubilizing Bacteria (PSB) to unlock insoluble soil phosphorus."
        ),
        content_hi=(
            "फसल चक्र, हरी खाद और जैव उर्वरक:\n"
            "• फसल चक्र: अनाज वाली फसलों के बाद दलहनी फसलें अवश्य लें ताकि जमीन की उर्वरा शक्ति बनी रहे।\n"
            "• हरी खाद: ढैंचा या सनई को 45-50 दिन बाद खेत में हल चलाकर दबा दें।\n"
            "• जैव उर्वरक: राइजोबियम और पीएसबी (PSB) कल्चर से बीज शोधन करें।"
        ),
        content_kn=(
            "ಬೆಳೆ ಪರಿವರ್ತನೆ ಮತ್ತು ಹಸಿರೆಲೆ ಗೊಬ್ಬರ:\n"
            "• ಧಾನ್ಯ ಬೆಳೆಗಳ ನಂತರ ದ್ವಿದಳ ಧಾನ್ಯ ಬೆಳೆಗಳನ್ನು ಬೆಳೆಯುವುದರಿಂದ ಭೂಮಿಯ ಫಲವತ್ತತೆ ಹೆಚ್ಚುತ್ತದೆ.\n"
            "• ಡಯಾಂಚ ಅಥವಾ ಸೆಣಬನ್ನು ಹೂ ಬಿಡುವ ಮುನ್ನ ಮಣ್ಣಿಗೆ ಸೇರಿಸಿ ಉಳುಮೆ ಮಾಡಿ."
        ),
        source=SourceAttribution(
            name="ICAR — National Centre for Organic Farming (NCOF)",
            organization="National Organic & Bio-fertilizer Institute",
            official_url="https://pgsindia-ncof.gov.in",
            verified_date="2026-03",
            access_note="NCOF Bio-fertilizer and Green Manuring Package."
        ),
        guardrail_notice="Do not mix bio-fertilizers with chemical fungicides or synthetic chemical fertilizers during seed treatment.",
    ),

    # ── 6. GOVERNMENT SCHEMES ─────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_scheme_001",
        category="government_schemes",
        title="PM-KISAN (Pradhan Mantri Kisan Samman Nidhi) Income Support",
        sub_category="direct_benefit_transfer",
        crops_applicable=[],
        soil_types_applicable=[],
        tags=["pm_kisan", "subsidy", "dbt", "pmkisan", "income_support", "landholding"],
        content_en=(
            "PM-KISAN Operational Guidelines:\n"
            "• Benefit: Direct benefit cash transfer of Rs. 6,000 per financial year released in three equal four-monthly installments of Rs. 2,000 each.\n"
            "• Eligibility: All landholding farmer families with cultivable land parcels in their name (subject to exclusion criteria such as institutional landholders, income-tax payees, constitutional post holders, etc.).\n"
            "• Mandatory Steps: (1) Aadhaar-seeded active bank account, (2) Aadhaar e-KYC completed on pmkisan.gov.in or CSC biometric center, (3) Land record seeding verified by state revenue authority.\n"
            "• Official Portal: pmkisan.gov.in (Helpline: 155261 / 011-24300606)."
        ),
        content_hi=(
            "प्रधानमंत्री किसान सम्मान निधि (PM-KISAN) योजना:\n"
            "• लाभ: पात्र किसान परिवारों को प्रति वर्ष ₹6,000 की आर्थिक सहायता ₹2,000 की तीन समान किस्तों में सीधे बैंक खाते में।\n"
            "• अनिवार्य शर्तें: आधार सीडेड बैंक खाता, pmkisan.gov.in पर ई-केवाईसी (e-KYC) पूर्ण होना, और भूमि दस्तावेजों का सत्यापन।\n"
            "• आधिकारिक पोर्टल: pmkisan.gov.in (हेल्पलाइन: 155261)."
        ),
        content_kn=(
            "ಪ್ರಧಾನ ಮಂತ್ರಿ ಕಿಸಾನ್ ಸಮ್ಮಾನ್ ನಿಧಿ (PM-KISAN):\n"
            "• ಸೌಲಭ್ಯ: ಅರ್ಹ ರೈತ ಕುಟುಂಬಗಳಿಗೆ ವಾರ್ಷಿಕ ₹6,000 ಆರ್ಥಿಕ ನೆರವು (ತಲಾ ₹2,000 ರಂತೆ 3 ಕಂತುಗಳಲ್ಲಿ).\n"
            "• ಅಗತ್ಯ ದಾಖಲೆಗಳು: ಆಧಾರ್ ಜೋಡಿತ ಬ್ಯಾಂಕ್ ಖಾತೆ, ಇ-ಕೆವೈಸಿ (e-KYC) ಮತ್ತು ಜಮೀನಿನ ಪಹಣಿ (RTC) ದೃಢೀಕರಣ.\n"
            "• ಅಧಿಕೃತ ಪೋರ್ಟಲ್: pmkisan.gov.in."
        ),
        source=SourceAttribution(
            name="Ministry of Agriculture & Farmers Welfare — PM-KISAN Division",
            organization="Central Government Scheme Directorate",
            official_url="https://pmkisan.gov.in",
            verified_date="2026-03",
            access_note="Official PM-KISAN scheme operational guidelines."
        ),
        guardrail_notice="Eligibility and fund release is subject to state land verification. The assistant cannot approve or disburse funds.",
    ),
    KnowledgeDocument(
        doc_id="doc_scheme_002",
        category="government_schemes",
        title="PMFBY (Pradhan Mantri Fasal Bima Yojana) Comprehensive Crop Insurance",
        sub_category="crop_insurance",
        crops_applicable=["paddy", "wheat", "cotton", "maize", "soybean", "groundnut"],
        soil_types_applicable=[],
        tags=["pmfby", "crop_insurance", "fasal_bima", "premium", "loss_assessment", "drought", "flood"],
        content_en=(
            "Pradhan Mantri Fasal Bima Yojana (PMFBY):\n"
            "• Risk Coverage: Comprehensive insurance against non-preventable natural risks (drought, flood, unseasonal rain, pests, diseases, hailstorm, post-harvest cyclone damage up to 14 days).\n"
            "• Low Farmer Premium Rates: Maximum 2.0% of sum insured for Kharif food crops/oilseeds, 1.5% for Rabi crops, and 5.0% for annual commercial/horticultural crops. The remaining actuarial premium is subsidized 50:50 by Central and State Governments.\n"
            "• Enrolment: Available via Primary Agricultural Credit Societies (PACS), commercial banks, CSCs, or directly via National Crop Insurance Portal (pmfby.gov.in).\n"
            "• Claim Intimation: Must report localized loss (hailstorm, inundation) within 72 hours via the Crop Insurance App or toll-free helpline 14447."
        ),
        content_hi=(
            "प्रधानमंत्री फसल बीमा योजना (PMFBY):\n"
            "• सुरक्षा: प्राकृतिक आपदाओं (सूखा, बाढ़, कीट प्रकोप, ओलावृष्टि) से फसल नुकसान पर पूर्ण बीमा सुरक्षा।\n"
            "• प्रीमियम दरें: खरीफ फसलों के लिए मात्र 2%, रबी फसलों के लिए 1.5%, और बागवानी फसलों के लिए 5%।\n"
            "• नुकसान की सूचना: ओलावृष्टि या जलभराव होने पर 72 घंटे के भीतर टोल-फ्री नंबर 14447 या ऐप पर सूचना देना अनिवार्य है।"
        ),
        content_kn=(
            "ಪ್ರಧಾನ ಮಂತ್ರಿ ಫಸಲ್ ಬಿಮಾ ಯೋಜನೆ (PMFBY):\n"
            "• ಬೆಳೆ ವಿಮೆ: ನೈಸರ್ಗಿಕ ವಿಕೋಪಗಳು, ಅನಾವೃಷ್ಟಿ, ಪ್ರವಾಹ ಹಾಗೂ ಕೀಟಬಾಧೆಯಿಂದಾಗುವ ಬೆಳೆ ನಷ್ಟಕ್ಕೆ ರಕ್ಷಣೆ.\n"
            "• ಪ್ರೀಮಿಯಂ ದರ: ಮುಂಗಾರು ಬೆಳೆಗೆ ಶೇ. 2, ಹಿಂಗಾರು ಬೆಳೆಗೆ ಶೇ. 1.5, ತೋಟಗಾರಿಕಾ ಬೆಳೆಗೆ ಶೇ. 5.\n"
            "• ನಷ್ಟದ ಮಾಹಿತಿ: ಹಾನಿಯಾದ 72 ಗಂಟೆಗಳ ಒಳಗೆ 14447 ಸಂಖ್ಯೆಗೆ ಕರೆ ಮಾಡಿ ಮಾಹಿತಿ ನೀಡಬೇಕು."
        ),
        source=SourceAttribution(
            name="Ministry of Agriculture & Farmers Welfare — PMFBY Cell",
            organization="Central Crop Insurance Directorate",
            official_url="https://pmfby.gov.in",
            verified_date="2026-03",
            access_note="PMFBY Revised Operational Guidelines."
        ),
        guardrail_notice="Enrolment cut-off dates are strictly seasonal and notified by each state government.",
    ),
    KnowledgeDocument(
        doc_id="doc_scheme_003",
        category="government_schemes",
        title="PMKSY Micro-Irrigation (Per Drop More Crop) Capital Subsidies",
        sub_category="subsidies",
        crops_applicable=["tomato", "sugarcane", "cotton", "banana", "chili"],
        soil_types_applicable=[],
        tags=["pmksy", "drip_subsidy", "micro_irrigation", "sprinkler_subsidy", "subsidy"],
        content_en=(
            "PMKSY - Per Drop More Crop (Micro-Irrigation Subsidy):\n"
            "• Subsidy Norms: Small and Marginal Farmers (landholding up to 2 hectares / 5 acres) receive up to 55% capital cost subsidy from Central/State funds, with many states (e.g. Tamil Nadu, Karnataka, Andhra Pradesh) adding top-up subsidies reaching 70% to 100% for SC/ST and small farmers. Other farmers receive up to 45%.\n"
            "• Eligible Equipment: Drip irrigation systems, micro-sprinklers, portable sprinklers, rain-guns.\n"
            "• Documents Required: Land record (Patta/Chitta/RTC/7-12), Aadhaar, Water source verification (borewell/well certificate), Soil test report, Bank passbook copy.\n"
            "• Application: Submit via state horticulture or agriculture portal (e.g., Uzhavan in TN, Raitha Siri in Karnataka, dbt.agrimachinery in others)."
        ),
        content_hi=(
            "प्रधानमंत्री कृषि सिंचाई योजना (PMKSY - प्रति बूंद अधिक फसल):\n"
            "• सब्सिडी: छोटे व सीमांत किसानों को ड्रिप और स्प्रिंकलर लगाने पर 55% से 100% तक सरकारी अनुदान (राज्य अनुसार)।\n"
            "• आवश्यक दस्तावेज: भू-अभिलेख (खतौनी), आधार कार्ड, बैंक पासबुक, सिंचाई स्रोत (बोरवेल) प्रमाण पत्र।\n"
            "• आवेदन: राज्य के कृषि/उद्यान विभाग के ऑनलाइन पोर्टल पर आवेदन करें।"
        ),
        content_kn=(
            "ಪಿಎಂಕೆಎಸ್ ವೈ ಹನಿ ನೀರಾವರಿ ಸಬ್ಸಿಡಿ ಯೋಜನೆ:\n"
            "• ಸಣ್ಣ ಮತ್ತು ಅತಿ ಸಣ್ಣ ರೈತರಿಗೆ ಹನಿ ನೀರಾವರಿ ಅಳವಡಿಕೆಗೆ ಶೇ. 70 ರಿಂದ ಶೇ. 90 ರವರೆಗೆ ಸಹಾಯಧನ ಲಭ್ಯವಿದೆ.\n"
            "• ಅಗತ್ಯ ದಾಖಲೆಗಳು: ಪಹಣಿ (RTC), ಆಧಾರ್ ಕಾರ್ಡ್, ಬೋರ್‌ವೆಲ್ ದೃಢೀಕರಣ ಮತ್ತು ಬ್ಯಾಂಕ್ ಪಾಸ್ ಬುಕ್."
        ),
        source=SourceAttribution(
            name="Ministry of Agriculture & Farmers Welfare — PMKSY Division",
            organization="Central Irrigation Mission",
            official_url="https://pmksy.gov.in",
            verified_date="2026-02",
            access_note="Operational Guidelines for Per Drop More Crop."
        ),
        guardrail_notice="Subsidies are disbursed through approved vendor installations subject to physical field inspection.",
    ),
    KnowledgeDocument(
        doc_id="doc_scheme_004",
        category="government_schemes",
        title="Kisan Credit Card (KCC) Concessional Agricultural Credit",
        sub_category="credit",
        crops_applicable=[],
        soil_types_applicable=[],
        tags=["kcc", "kisan_credit_card", "loan", "interest_subvention", "short_term_credit"],
        content_en=(
            "Kisan Credit Card (KCC) Guidelines:\n"
            "• Purpose: Meets short-term credit requirements for cultivation, post-harvest expenses, produce marketing, working capital for farm maintenance, and allied activities (dairy, fisheries).\n"
            "• Concessional Interest Rate: Normal bank interest rate is subsidized with a 2% interest subvention and an additional 3% prompt repayment incentive, bringing the effective interest rate to just 4% per annum for prompt payers up to Rs. 3 Lakhs.\n"
            "• Collateral-Free Limit: Loans up to Rs. 1.6 Lakh are collateral-free (up to Rs. 3 Lakh under tie-up agreements).\n"
            "• How to Apply: Visit your nearest commercial bank, Regional Rural Bank (RRB), or Primary Agricultural Cooperative Society (PACS) with land record and Aadhaar."
        ),
        content_hi=(
            "किसान क्रेडिट कार्ड (KCC) रियायती कृषि ऋण:\n"
            "• ब्याज दर: समय पर ऋण चुकाने पर प्रभावी ब्याज दर मात्र 4% प्रति वर्ष (₹3 लाख तक के ऋण पर)।\n"
            "• बिना गारंटी ऋण: ₹1.60 लाख तक का ऋण बिना किसी बंधक (कोलेटरल) के मिलता है।\n"
            "• आवेदन: नजदीकी बैंक शाखा या प्राथमिक कृषि सहकारी समिति (PACS) में आवेदन करें।"
        ),
        content_kn=(
            "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್ (KCC) ಸಾಲ ಸೌಲಭ್ಯ:\n"
            "• ಬಡ್ಡಿ ದರ: ಸಕಾಲದಲ್ಲಿ ಮರುಪಾವತಿ ಮಾಡುವ ರೈತರಿಗೆ ಕೇವಲ ಶೇ. 4 ರ ಬಡ್ಡಿದರದಲ್ಲಿ ಕೃಷಿ ಸಾಲ ಲಭ್ಯ.\n"
            "• ₹1.60 ಲಕ್ಷದವರೆಗೆ ಯಾವುದೇ ಜಾಮೀನು ಇಲ್ಲದೆ ಸಾಲ ನೀಡಲಾಗುತ್ತದೆ."
        ),
        source=SourceAttribution(
            name="Reserve Bank of India & NABARD — Priority Sector Lending",
            organization="National Bank for Agriculture and Rural Development",
            official_url="https://www.nabard.org",
            verified_date="2026-03",
            access_note="RBI Master Direction on Priority Sector Lending - Kisan Credit Card."
        ),
        guardrail_notice="Sanction of credit limits is based on scale of finance fixed by the District Level Technical Committee (DLTC).",
    ),

    # ── 7. MARKET PRICES ──────────────────────────────────────────────────────
    KnowledgeDocument(
        doc_id="doc_market_001",
        category="market_prices",
        title="Agmarknet & e-NAM Mandi Price Discovery and Market Advisory",
        sub_category="market_intelligence",
        crops_applicable=["tomato", "paddy", "wheat", "cotton", "banana", "chili", "onion"],
        soil_types_applicable=[],
        tags=["market_prices", "mandi_rates", "agmarknet", "enam", "msp", "grading", "wdra", "storage"],
        content_en=(
            "Agricultural Marketing & Price Discovery Guidance:\n"
            "• Daily Price Verification: Mandi wholesale prices fluctuate daily based on arrivals, moisture level, and quality grade. Farmers must verify authentic daily modal rates on Agmarknet (agmarknet.gov.in) and e-NAM (enam.gov.in).\n"
            "• Cleaning & Grading: Clean, sort, and grade produce before transporting to the mandi. Quality-graded lots systematically secure 10% to 25% higher bids than mixed produce.\n"
            "• Avoiding Distress Sales: During peak harvest market gluts, use WDRA-accredited warehouses to store produce and access negotiable warehouse receipt (e-NWR) loan financing up to 70% of crop value.\n"
            "• Minimum Support Price (MSP): For notified crops (e.g., paddy, wheat, cotton), check active government procurement centers and Fair Average Quality (FAQ) parameters before selling below MSP."
        ),
        content_hi=(
            "कृषि विपणन और मंडी भाव मार्गदर्शन:\n"
            "• दैनिक भाव सत्यापन: मंडियों में भाव दैनिक आवक और गुणवत्ता के आधार पर तय होते हैं। सही दैनिक भाव एगमार्कनेट (agmarknet.gov.in) और ई-नाम (enam.gov.in) पर जांचें।\n"
            "• ग्रेडिंग व सफाई: फसल को मंडी ले जाने से पहले साफ और श्रेणीबद्ध (ग्रेड) करें। इससे 10-25% बेहतर मूल्य मिलता है।\n"
            "• संकटपूर्ण बिक्री से बचाव: फसल के अच्छे दाम न मिलने पर डब्ल्यूडीआरए (WDRA) मान्यता प्राप्त गोदामों में भंडारण करें और ई-एनडब्ल्यूआर (e-NWR) रसीद पर ऋण लें।"
        ),
        content_kn=(
            "ಕೃಷಿ ಮಾರುಕಟ್ಟೆ ಮತ್ತು ಮಂಡಿ ದರ ಮಾಹಿತಿ:\n"
            "• ಅಧಿಕೃತ ಮಂಡಿ ದರಗಳನ್ನು ಅಗ್ಮಾರ್ಕ್‌ನೆಟ್ (agmarknet.gov.in) ಮತ್ತು ಇ-ನ್ಯಾಮ್ (enam.gov.in) ಮೂಲಕ ಪರಿಶೀಲಿಸಿ.\n"
            "• ಉತ್ಪನ್ನಗಳನ್ನು ಸ್ವಚ್ಛಗೊಳಿಸಿ ಮತ್ತು ಗ್ರೇಡಿಂಗ್ ಮಾಡಿ ಮಾರುಕಟ್ಟೆಗೆ ತಂದರೆ ಉತ್ತಮ ಬೆಲೆ ಸಿಗುತ್ತದೆ.\n"
            "• ಕೊಯ್ಲಿನ ನಂತರ ಬೆಲೆ ಕುಸಿತವಿದ್ದಲ್ಲಿ ವೈಜ್ಞಾನಿಕ ಗೋದಾಮುಗಳಲ್ಲಿ ದಾಸ್ತಾನು ಮಾಡಿ."
        ),
        content_ta=(
            "வேளாண் சந்தை விலை மற்றும் ஒழுங்குமுறை விற்பனை வழிகாட்டல்:\n"
            "• தினசரி விலை நிலவரத்தை அக்மார்க்நெட் (agmarknet.gov.in) மற்றும் இ-நாம் (enam.gov.in) தளங்களில் சரிபார்க்கவும்.\n"
            "• விளைபொருட்களை தூய்மை செய்து தரம் பிரித்து விற்பனைக்கு கொண்டு சென்றால் கூடுதல் விலை கிடைக்கும்.\n"
            "• அறுவடை கால விலை சரிவைத் தவிர்க்க அங்கீகரிக்கப்பட்ட சேமிப்புக் கிடங்குகளில் சேமித்து வைக்கலாம்."
        ),
        source=SourceAttribution(
            name="Directorate of Marketing & Inspection (DMI) — Agmarknet & e-NAM",
            organization="Ministry of Agriculture & Farmers Welfare",
            official_url="https://agmarknet.gov.in",
            verified_date="2026-03",
            access_note="DMI Agricultural Marketing & Agmarknet portal guidelines. No live or cached prices are fabricated."
        ),
        guardrail_notice="Live mandi rates vary continuously by hour and location. Always consult local APMC mandis or official Agmarknet portal for today's authentic transactions.",
    ),
]


# Explicit mapping from user / NLP classification intents to document categories
INTENT_TO_CATEGORIES: dict[str, list[str]] = {
    "pest_control": ["pests", "diseases"],
    "irrigation": ["farming_practices", "soil"],
    "crop_advisory": ["crops", "soil", "farming_practices"],
    "government_schemes": ["government_schemes"],
    "market_prices": ["market_prices"],
    "weather": ["farming_practices", "crops"],
}


def get_categories_for_intent(intent: str) -> list[str]:
    """Map an agricultural intent to the relevant document categories."""
    return list(INTENT_TO_CATEGORIES.get(intent, [intent]))


class KnowledgeRepository:
    """Search and retrieval interface over the verified knowledge document corpus."""

    def __init__(
        self,
        documents: Optional[list[KnowledgeDocument]] = None,
        dataset_path: Optional[Path] = None,
    ) -> None:
        if documents is not None:
            self._documents = list(documents)
        else:
            self._documents = list(DOCUMENT_CORPUS)
            path = dataset_path or (Path(__file__).parent / "data" / "ingested_knowledge.json")
            if path.exists():
                self._load_from_ingested_dataset(path)

    def _load_from_ingested_dataset(self, path: Path) -> None:
        """Merge newly ingested verified documents from structured local dataset."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data.get("records", [])
                existing_ids = {doc.doc_id for doc in self._documents}
                for rec in records:
                    doc_id = rec.get("doc_id")
                    if doc_id and doc_id not in existing_ids:
                        self._documents.append(
                            KnowledgeDocument(
                                doc_id=doc_id,
                                category=rec.get("category", "farming_practices"),
                                title=rec.get("title", ""),
                                sub_category=rec.get("sub_category", ""),
                                crops_applicable=rec.get("crops_applicable", []),
                                soil_types_applicable=rec.get("soil_types_applicable", []),
                                nutrients_applicable=rec.get("nutrients_applicable", []),
                                seasons_applicable=rec.get("seasons_applicable", []),
                                tags=rec.get("tags", []),
                                content_en=rec.get("content_en", ""),
                                content_hi=rec.get("content_hi", ""),
                                content_ta=rec.get("content_ta", ""),
                                content_kn=rec.get("content_kn", ""),
                                source=SourceAttribution(
                                    name=rec.get("source_name", "ICAR / Government of India"),
                                    organization=rec.get("organization", "Agricultural Research Institute"),
                                    official_url=rec.get("official_url", "https://icar.gov.in"),
                                    verified_date=rec.get("retrieval_timestamp", "2026-03")[:7],
                                    access_note=rec.get("access_note") or f"Ingested official document ({rec.get('verification_status')}).",
                                ),
                                guardrail_notice=rec.get("guardrail_notice", ""),
                            )
                        )
                        existing_ids.add(doc_id)
        except Exception:
            pass

    def get_document(self, doc_id: str) -> Optional[KnowledgeDocument]:
        for doc in self._documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def upsert_document(self, doc: KnowledgeDocument) -> None:
        """Add or update an in-memory knowledge document."""
        for i, existing in enumerate(self._documents):
            if existing.doc_id == doc.doc_id:
                if not doc.content_hi and existing.content_hi:
                    doc.content_hi = existing.content_hi
                if not doc.content_kn and existing.content_kn:
                    doc.content_kn = existing.content_kn
                if not doc.content_ta and existing.content_ta:
                    doc.content_ta = existing.content_ta
                self._documents[i] = doc
                return
        self._documents.append(doc)

    def delete_document(self, doc_id: str) -> bool:
        """Remove a document from in-memory corpus."""
        initial_len = len(self._documents)
        self._documents = [d for d in self._documents if d.doc_id != doc_id]
        return len(self._documents) < initial_len

    def list_documents(self, category: Optional[str] = None) -> list[KnowledgeDocument]:
        if not category:
            return list(self._documents)
        return [doc for doc in self._documents if doc.category == category]

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        crop: Optional[str] = None,
        soil: Optional[str] = None,
        season: Optional[str] = None,
        nutrient: Optional[str] = None,
        language_code: str = "en",
        top_k: int = 3,
        intent: Optional[str] = None,
    ) -> list[KnowledgeDocument]:
        """Search retrieval-ready documents by matching terms, categories, and entities.

        Supports direct category filtering ('crops', 'soil', etc.) and intent-to-category
        routing ('pest_control', 'irrigation', 'crop_advisory', 'government_schemes', 'market_prices').
        """
        # Determine allowed categories
        target_categories: Optional[list[str]] = None
        if intent:
            target_categories = get_categories_for_intent(intent)
        elif category:
            if category in INTENT_TO_CATEGORIES:
                target_categories = get_categories_for_intent(category)
            else:
                target_categories = [category]

        raw_words = query.lower().split()
        clean_words = [w.strip("?,.:;!'\"()[]{}") for w in raw_words]
        query_words = {w for w in clean_words if len(w) > 2}

        scored: list[tuple[float, KnowledgeDocument]] = []

        for doc in self._documents:
            if target_categories and doc.category not in target_categories:
                continue

            score = 0.0

            # Intent/Category alignment baseline score
            if target_categories and doc.category in target_categories:
                score += 1.0

            # Crop match boost
            if crop and crop in doc.crops_applicable:
                score += 20.0

            # Soil match boost
            if soil and soil in doc.soil_types_applicable:
                score += 15.0

            # Season match boost
            if season and (season in doc.seasons_applicable or season in doc.tags):
                score += 10.0

            # Nutrient match boost
            if nutrient and (nutrient in doc.nutrients_applicable or nutrient in doc.tags):
                score += 10.0

            # Content & title matching across English and Indic fields
            doc_text = (
                f"{doc.title} {' '.join(doc.tags)} {doc.content_en} "
                f"{doc.content_hi} {doc.content_ta} {doc.content_kn} {doc.sub_category}"
            ).lower()
            matched_words = sum(1 for w in query_words if w in doc_text)
            score += matched_words * 3.0

            # Title direct match boost
            for w in query_words:
                if w in doc.title.lower():
                    score += 5.0

            # Tag match boost
            for tag in doc.tags:
                tag_lower = tag.lower()
                if tag_lower in query.lower() or any(w in tag_lower for w in query_words):
                    score += 5.0

            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def get_localized_content(self, doc: KnowledgeDocument, language_code: str = "en") -> str:
        """Return content in the requested language if available, falling back to English."""
        if language_code == "hi" and doc.content_hi:
            return doc.content_hi
        if language_code == "kn" and doc.content_kn:
            return doc.content_kn
        if language_code == "ta" and doc.content_ta:
            return doc.content_ta
        return doc.content_en


# Module-level singleton
knowledge_repository = KnowledgeRepository()

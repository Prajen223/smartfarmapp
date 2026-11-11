"""Agricultural Named Entity Recognition (NER) for Smart Farming Assistant.

Extracts domain-specific agricultural entities across English, Hindi, Kannada,
Tamil, and Telugu:
  • Crops (e.g. tomato, paddy, wheat, cotton, chili, banana, ragi, jowar, bajra)
  • Pests (e.g. aphid, whitefly, stem borer, pink bollworm, fall armyworm, leaf curl)
  • Diseases (e.g. early blight, late blight, blast, powdery mildew, rust, wilt)
  • Soil types (e.g. alluvial, black cotton, red, laterite, sandy, clay, loamy)
  • Nutrients (e.g. nitrogen, phosphorus, potassium, zinc, boron, sulfur, calcium, iron, magnesium)
  • Seasons (e.g. kharif, rabi, zaid, mungaru, hingaru, summer, monsoon, winter)
  • Locations (Indian states, agro-climatic zones, and regions)
  • Schemes (e.g. PM-KISAN, PMFBY, PMKSY, Soil Health Card, KCC, PKVY, Raitha Siri)
  • Fertilizers & Soil amendments (e.g. urea, DAP, NPK, zinc sulphate, FYM, SSP)

Combines:
  1. Multilingual agricultural lexicon with native scripts and transliterations.
  2. Hugging Face Named Entity Recognition pipeline for general entity discovery
     (locations, organizations, geopolitical entities).
"""

from __future__ import annotations

import logging
import os
import re
from typing import TypedDict, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity dictionaries
# Each entry: canonical_label -> list[match_strings]
# ---------------------------------------------------------------------------

CROP_ENTITIES: dict[str, list[str]] = {
    "tomato":       ["tomato", "tamatar", "தக்காளி", "టమాట", "ಟೊಮೆಟೊ", "ಟೊಮೇಟೊ", "टमाटर"],
    "paddy":        ["paddy", "rice", "dhan", "நெல்", "அரிசி", "వరి", "ಭತ್ತ", "ಅಕ್ಕಿ", "धान", "चावल"],
    "cotton":       ["cotton", "kapas", "பருத்தி", "పత్తి", "ಹತ್ತಿ", "कपास"],
    "wheat":        ["wheat", "gehu", "gehun", "கோதுமை", "గోధుమ", "ಗೋಧಿ", "गेहूं", "गेहूँ"],
    "banana":       ["banana", "kela", "வாழை", "అరటి", "ಬಾಳೆ", "ಬಾಳೆಹಣ್ಣು", "केला"],
    "chili":        ["chili", "chilli", "mirch", "மிளகாய்", "మిరప", "ಮೆಣಸಿನಕಾಯಿ", "मिर्च"],
    "onion":        ["onion", "pyaz", "வெங்காயம்", "ఉల్లి", "ಈರುಳ್ಳಿ", "प्याज"],
    "maize":        ["maize", "corn", "makka", "மக்காச்சோளம்", "మొక్కజొన్న", "ಮೆಕ್ಕೆಜೋಳ", "मक्का"],
    "sugarcane":    ["sugarcane", "sugar cane", "ganna", "கரும்பு", "చెరకు", "ಕಬ್ಬು", "गन्ना"],
    "groundnut":    ["groundnut", "peanut", "moongphali", "நிலக்கடலை", "వేరుశనగ", "ಕಡಲೆಕಾಯಿ", "ನೆಲಗಡಲೆ", "मूंगफली"],
    "soybean":      ["soybean", "soya", "soyabean", "பயறு", "సోయా", "ಸೋಯಾ", "ಸೋಯಾಬೀನ್", "सोयाबीन"],
    "mustard":      ["mustard", "sarson", "கடுகு", "ఆవాలు", "ಸಾಸಿವೆ", "सरसों"],
    "potato":       ["potato", "aloo", "உருளைக்கிழங்கு", "బంగాళాదుంప", "ಆಲೂಗಡ್ಡೆ", "ಆಲೂ", "आलू"],
    "brinjal":      ["brinjal", "eggplant", "baingan", "கத்தரிக்காய்", "వంకాయ", "ಬದನೆ", "ಬದನೆಕಾಯಿ", "बैंगन"],
    "okra":         ["okra", "ladyfinger", "lady finger", "bhindi", "வெண்டை", "బెండకాయ", "ಬೆಂಡೆ", "ಬೆಂಡೆಕಾಯಿ", "भिंडी"],
    "mango":        ["mango", "aam", "மாங்காய்", "மாம்பழம்", "మామిడి", "ಮಾವು", "ಮಾವಿನಹಣ್ಣು", "आम"],
    "coconut":      ["coconut", "nariyal", "தேங்காய்", "కొబ్బరి", "ತೆಂಗಿನಕಾಯಿ", "ತೆಂಗು", "नारियल"],
    "turmeric":     ["turmeric", "haldi", "மஞ்சள்", "పసుపు", "ಅರಿಶಿನ", "हल्दी"],
    "ginger":       ["ginger", "adrak", "இஞ்சி", "అల్లం", "ಶುಂಠಿ", "अदरक"],
    "garlic":       ["garlic", "lahsun", "பூண்டு", "వెల్లుల్లి", "ಬೆಳ್ಳುಳ್ಳಿ", "लहसुन"],
    "cauliflower":  ["cauliflower", "gobi", "फूलगोभी", "பூக்கோசு", "కాలీఫ్లవర్", "ಹೂಕೋಸು", "गोभी"],
    "cabbage":      ["cabbage", "bandgobi", "முட்டைகோஸ்", "క్యాಬೇಜೀ", "ಎಲೆಕೋಸು", "पत्ता गोभी", "बंद गोभी"],
    "lentil":       ["lentil", "dal", "daal", "masoor", "பருப்பு", "పప్పు", "ಬೇಳೆ", "ದಾಲ", "दाल", "मसूर"],
    "chickpea":     ["chickpea", "chana", "chick pea", "gram", "கொண்டைக்கடலை", "శనగలు", "ಕಡಲೆ", "चना", "छोले"],
    "ragi":         ["ragi", "finger millet", "mandua", "ರಾಗಿ", "ರಾ ಗಿ", "रागी", "கேழ்வரகு", "ராகி"],
    "jowar":        ["jowar", "sorghum", "jola", "ಜೋಳ", "ज्वार", "சோளம்"],
    "bajra":        ["bajra", "pearl millet", "sajje", "ಸಜ್ಜೆ", "बाजरा", "கம்பு"],
    "pomegranate":  ["pomegranate", "anar", "dalimbe", "ದಾಳಿಂಬೆ", "अनार", "மாதுளை"],
}

PEST_ENTITIES: dict[str, list[str]] = {
    "aphid":            ["aphid", "aphis", "அசுவினி", "అఫిడ్", "ಮಿಡ್ತೆ", "ಗಿಡಹೇನು", "माहू", "माहि"],
    "whitefly":         ["whitefly", "white fly", "வெள்ளை ஈ", "తెల్ల దోమ", "ಬಿಳಿ ನೊಣ", "सफेद मक्खी"],
    "thrips":           ["thrip", "thrips", "இலைப்பேன்", "థ్రిప్స్", "ಥ್ರಿಪ್ಸ್", "ನುಸಿ", "थ्रिप्स"],
    "mealybug":         ["mealybug", "mealy bug", "மாவுப்பூச்சி", "పిండి పురుగు", "ಹಿಟ್ಟು ಹುಳ", "मिली बग"],
    "stem_borer":       ["stem borer", "stemborer", "தண்டுத்துளைப்பான்", "కాండం తొలిచే పురుగు", "ಕಾಂಡ ಕೊರೆಯುವ ಹುಳ", "तना छेदक"],
    "pink_bollworm":    ["bollworm", "boll worm", "pink bollworm", "காய்ப்புழு", "గులాబీ పురుగు", "ಗುಲಾಬಿ ಕಾಯಿಕೊರಕ", "गुलाबी इल्ली"],
    "fruit_borer":      ["fruit borer", "fruitborer", "helicoverpa", "காய்ப்புழு", "పండు తొలిచే పురుగు", "ಹಣ್ಣಿನ ಕೊರಕ", "फल छेदक"],
    "leaf_minor":       ["leaf minor", "leaf miner", "leafminer", "இலைச்சுரங்கப் புழு", "ఆకు తొలిచే పురుగు", "ಸುರುಳಿ ಹುಳು", "पत्ती खनक"],
    "leaf_curl":        ["leaf curl", "leafcurl", "पत्ती मरोड़", "ಎಲೆ ಮುದುರು", "ಎಲೆ ಸುರುಟು", "சுருட்டுப் பூச்சி", "curl virus"],
    "red_spider_mite":  ["spider mite", "red mite", "சிலந்திப்பூச்சி", "సాలె పురుగు", "ಜೇಡ ಹುಳ", "ಕೆಂಪು ನುಸಿ", "लाल मकड़ी", "ನುಸಿ"],
    "cutworm":          ["cutworm", "cut worm", "அறுவடைப்புழு", "కట్ వర్మ్", "ಕಟುಕಾ ಹುಳು", "कटुआ कीड़ा"],
    "grasshopper":      ["grasshopper", "locust", "வெட்டுக்கிளி", "మిడత", "ಮಿಡತೆ", "टिड्डी"],
    "brown_plant_hopper": ["bph", "brown planthopper", "plant hopper", "கிளர்த்தி", "గోధుమ రంగు తెగులు", "ಕಂದು ಜಿಗಿಹುಳು", "भूरा माहो"],
    "scale_insect":     ["scale insect", "scale", "செதில் பூச்சி", "స్కేల్ పురుగు", "ಚಿಪ್ಪು ಹುಳ"],
    "fall_armyworm":    ["fall armyworm", "armyworm", "लश्करी इल्ली", "ಸೈನಿಕ ಕೀಟ", "सैनिक कीड़ा", "படைப்புழு"],
}

DISEASE_ENTITIES: dict[str, list[str]] = {
    "blight":           ["blight", "early blight", "late blight", "கருகல்", "வாடு తెగులు", "ಅಂಗಮಾರಿ", "ಅಂಗಮಾರಿ ರೋಗ", "झुलसा"],
    "rust":             ["rust", "leaf rust", "துரு", "తుప్పు తెగులు", "ಕಿರ್ಮೀರ", "ತುಕ್ಕು ರೋಗ", "रतुआ"],
    "smut":             ["smut", "loose smut", "கரிப்பூஞ்சை", "నల్ల తెగులు", "ಕಂದು ರೋಗ", "ಮಸಿ ರೋಗ", "काला कवक"],
    "powdery_mildew":   ["powdery mildew", "mildew", "வெண்பூஞ்சை", "తెల్ల బూడిద తెగులు", "ಬೂದು ರೋಗ", "चूर्णिल आसिता", "powdery"],
    "downy_mildew":     ["downy mildew", "downy", "கீழ்ப்பூஞ்சை", "తడి బూడిద తెగులు", "ಶಿಲೀಂಧ್ರ ರೋಗ"],
    "wilt":             ["wilt", "wilting", "வாடல்", "వాడు", "ಬಾಡು", "ಬಾಡು ರೋಗ", "उकठा"],
    "root_rot":         ["root rot", "collar rot", "வேர் அழுகல்", "వేరు కుళ్ళు", "ಬೇರು ಕೊಳೆ", "जड़ सड़न"],
    "leaf_spot":        ["leaf spot", "leaf blight", "இலைப்புள்ளி", "ఆకు మచ్చ తెగులు", "ಎಲೆ ಚುಕ್ಕೆ", "पत्ती धब्बा"],
    "mosaic_virus":     ["mosaic", "mosaic virus", "மொசைக் வைரஸ்", "మొజాయిక్ వైరస్", "ಮೊಸಾಯಿಕ್", "मोजेक"],
    "yellow_mosaic":    ["yellow mosaic", "yellowing", "மஞ்சள் மொசைக்", "పసుపు మొజాయిక్", "ಹಳದಿ ಮೊಸಾಯಿಕ್", "पीला मोजेक"],
    "bacterial_wilt":   ["bacterial wilt", "bacterial blight", "பாக்டீரியா வாடல்", "బ్యాక్టీరియల్ వాడు", "ಬ್ಯಾಕ್ಟೀರಿಯಲ್ ವಿಲ್ಟ್"],
    "anthracnose":      ["anthracnose", "அந்த்ராக்னோஸ்", "ఆంత్రాక్నోస్", "ಆಂಥ್ರಾಕ್ನೋಸ್", "एंथ्रेक्नोज"],
    "blast":            ["blast", "neck blast", "rice blast", "கதிர் காய்ச்சல்", "బ్లాస్ట్ తెగులు", "ಬ್ಲಾಸ್ಟ್", "झोंका"],
    "damping_off":      ["damping off", "damping-off", "seedling rot", "நாற்று அழுகல்", "నారు కుళ్ళు", "ಮಿಡಿ ಕೊಳೆ"],
}

SOIL_ENTITIES: dict[str, list[str]] = {
    "alluvial":         ["alluvial", "alluvial soil", "जलोढ़", "जलोढ़ मिट्टी", "காப்", "வண்டல்", "வண்டல் மண்", "ಮೆಕ್ಕಲು ಮಣ್ಣು", "ಮೆಕ್ಕಲು"],
    "black":            ["black soil", "regur", "black cotton soil", "काली मिट्टी", "काली", "रेगुर", "ಕಪ್ಪು ಮಣ್ಣು", "ಕಪ್ಪು ಮಣ್ಣ", "ಕಪ್ಪು ಮಣ್ಣಿನಲ್ಲಿ", "ಕಪ್ಪು", "ರೆಗೂರ್", "கரிசல் மண்", "கரிசல்"],
    "red":              ["red soil", "लाल मिट्टी", "लाल", "ಕೆಂಪು ಮಣ್ಣು", "ಕೆಂಪು", "செம்மண்", "ఎర్ర నేలలు", "ఎర్ర మట్టి"],
    "laterite":         ["laterite", "laterite soil", "लेटराइट मिट्टी", "ಲ್ಯಾಟರೈಟ್ ಮಣ್ಣು", "ಲ್ಯಾಟರೈಟ್", "லேட்டரைட் மண்"],
    "sandy":            ["sandy soil", "sand", "बलुई मिट्टी", "रेतीली मिट्टी", "ಮರಳು ಮಣ್ಣು", "மணல் மண்", "ఇసుక నేలలు"],
    "clay":             ["clay soil", "clay", "चिकनी मिट्टी", "ಜೇಡಿ ಮಣ್ಣು", "ಜೇಡಿ", "களிமண்", "బంకమట్టి"],
    "loamy":            ["loamy", "loam", "दोमट", "दोमट मिट्टी", "ಗೋಡು ಮಣ್ಣು", "ಗೋಡು", "வண்டல் கலந்த மண்"],
    "saline_alkaline":  ["saline", "alkaline", "salinity", "खारी मिट्टी", "लवणीय", "ಉಪ್ಪು ಮಣ್ಣು", "உவர் மண்", "களர் நிலம்"],
}

SCHEME_ENTITIES: dict[str, list[str]] = {
    "pm_kisan":         ["pm kisan", "pm-kisan", "pmkisan", "kisan samman", "पीएम किसान", "ಪಿಎಂ ಕಿಸಾನ್", "பி.எம். கிசான்"],
    "pmfby":            ["pmfby", "crop insurance", "fasal bima", "fasal bima yojana", "फसल बीमा", "ಬೆಳೆ ವಿಮೆ", "பயிர் காப்பீடு"],
    "pmksy":            ["pmksy", "per drop more crop", "micro irrigation subsidy", "drip subsidy", "ಸೂಕ್ಷ್ಮ ನೀರಾವರಿ", "நுண்ணீர்ப் பாசனம்"],
    "soil_health_card": ["soil health card", "soil card", "मृदा स्वास्थ्य कार्ड", "ಮಣ್ಣು ಆರೋಗ್ಯ ಕಾರ್ಡ್", "மண் வள அட்டை"],
    "kcc":              ["kcc", "kisan credit card", "किसान क्रेडिट कार्ड", "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್", "கிசான் கிரெடிட் கார்டு"],
    "pkvy":             ["pkvy", "paramparagat krishi", "organic farming scheme", "जैविक खेती योजना", "ಪರಂಪರಾಗತ್ ಕೃಷಿ"],
    "enam":             ["enam", "e-nam", "national agriculture market", "राष्ट्रीय कृषि बाजार", "ಇ-ನಾಮ್"],
    "smam":             ["smam", "farm mechanization", "tractor subsidy", "कृषि यंत्रीकरण", "ಕೃಷಿ ಯಂತ್ರೋಪಕರಣ ಸಬ್ಸಿಡಿ"],
    "raitha_siri":      ["raitha siri", "raitasiri", "ರೈತ ಸಿರಿ", "ಮಿಲೆಟ್ ಪ್ರೋತ್ಸಾಹಧನ"],
    "krishi_bhagya":    ["krishi bhagya", "ಕೃಷಿ ಭಾಗ್ಯ", "ಕೃಷಿ ಹೊಂಡ"],
}

FERTILIZER_ENTITIES: dict[str, list[str]] = {
    "urea":             ["urea", "யூரியா", "యూరియా", "ಯೂರಿಯಾ", "यूरिया"],
    "dap":              ["dap", "diammonium phosphate", "di ammonium phosphate", "ಡಿಎಪಿ"],
    "mop":              ["mop", "muriate of potash", "potash", "potassium"],
    "npk":              ["npk", "n-p-k", "balanced fertilizer", "compound fertilizer", "ಎನ್ ಪಿ ಕೆ", "என்பிகே"],
    "ssp":              ["ssp", "single super phosphate", "ಸಿಂಗಲ್ ಸೂಪರ್ ಫಾಸ್ಫೇಟ್"],
    "zinc_sulphate":    ["zinc sulphate", "zinc sulfate", "zinc", "tutt", "துத்தநாகம்", "జింక్", "ಸತು", "जिंक"],
    "boron":            ["boron", "borax", "போரான்", "బోరాన్", "ಬೋರಾನ್", "बोरोन"],
    "fym":              ["fym", "farmyard manure", "compost", "vermicompost", "organic manure", "தொழுவுரம்", "పశువుల ఎరువు", "ಕೊಟ್ಟಿಗೆ ಗೊಬ್ಬರ", "ಸಾವಯವ ಗೊಬ್ಬರ", "गोबर खाद", "गोबर"],
    "neem_cake":        ["neem cake", "neemseed cake", "வேப்பிலை கட்டி", "ವೇಪ పిండి", "ಬೇವಿನ ಹಿಂಡಿ", "नीम केक"],
    "bio_fertilizer":   ["biofertilizer", "bio-fertilizer", "bio fertilizer", "azospirillum", "rhizobium",
                         "phosphobacteria", "psb", "azotobacter", "உயிர் உரம்", "జీవ ఎరువు", "ಜೈವಿಕ ಗೊಬ್ಬರ", "जैव उर्वरक"],
    "sulphur":          ["sulphur", "sulfur", "கந்தகம்", "గంధకం", "ಗಂಧಕ", "सल्फर"],
    "calcium":          ["calcium", "lime", "limestone", "calcium nitrate", "கல்சியம்", "కాల్షియం", "ಕ್ಯಾಲ್ಸಿಯಂ", "कैल्सियम"],
    "micronutrient":    ["micronutrient", "micro nutrient", "trace element", "நுண்ணூட்டம்", "సూక్ష్మ పోషకాలు", "ಸೂಕ್ಷ್ಮ ಪೋಷಕ", "सूक्ष्म पोषक"],
    "nske":             ["nske", "neem seed kernel extract", "neem oil", "வேப்பெண்ணெய்", "ವೇಪ ನೂನೆ", "ಬೇವಿನ ಎಣ್ಣೆ", "नीम तेल"],
}

NUTRIENT_ENTITIES: dict[str, list[str]] = {
    "nitrogen":         ["nitrogen", "नाइट्रोजन", "ಸಾರಜನಕ", "தழைச்சத்து", "urea nitrogen", "nitrate"],
    "phosphorus":       ["phosphorus", "फॉस्फोरस", "ರಂಜಕ", "மணிச்சத்து", "phosphate"],
    "potassium":        ["potassium", "potash", "पोटाश", "पोटैशियम", "ಪೊಟ್ಯಾಶ್", "சாம்பல் சத்து"],
    "zinc":             ["zinc", "जिंक", "जस्ता", "ಸತು", "துத்தநாகம்", "zinc sulphate", "zinc sulfate"],
    "boron":            ["boron", "बोरोन", "ಬೋರಾನ್", "போரான்"],
    "sulfur":           ["sulfur", "sulphur", "सल्फर", "गंधक", "ಗಂಧಕ", "கந்தகம்"],
    "calcium":          ["calcium", "कैल्शियम", "ಕ್ಯಾಲ್ಸಿಯಂ", "சுண்ணாம்பு சத்து"],
    "iron":             ["iron", "लोहा", "आयरन", "ಕಬ್ಬಿಣ", "இரும்புச்சத்து"],
    "magnesium":        ["magnesium", "मैग्नीशियम", "ಮೆಗ್ನೀಸಿಯಂ", "மெக்னீசியம்"],
    "organic_carbon":   ["organic carbon", "ऑर्गेनिक कार्बन", "ಜೈವಿಕ ಇಂಗಾಲ", "கரிம கார்பன்"],
}

SEASON_ENTITIES: dict[str, list[str]] = {
    "kharif":           ["kharif", "kharif season", "खरीफ", "खरीफ फसल", "ಮುಂಗಾರು", "ಮುಂಗಾರು ಬೆಳೆ", "முங்கಾರು", "காரீப்", "monsoon season", "rainy season"],
    "rabi":             ["rabi", "rabi season", "रबी", "रबी फसल", "ಹಿಂಗಾರು", "ಹಿಂಗಾರು ಬೆಳೆ", "ஹிங்காரு", "ரபி", "winter season", "winter crop"],
    "zaid":             ["zaid", "zaid season", "summer season", "summer crop", "जायद", "जायद फसल", "ಬೇಸಿಗೆ", "ಬೇಸಿಗೆ ಬೆಳೆ", "கோடை பருவம்", "கோடை"],
}

LOCATION_ENTITIES: dict[str, list[str]] = {
    "andhra pradesh":   ["andhra", "andhra pradesh", "ఆంధ్రప్రదేశ్"],
    "assam":            ["assam", "असम"],
    "bihar":            ["bihar", "बिहार"],
    "chhattisgarh":     ["chhattisgarh", "छत्तीसगढ़"],
    "gujarat":          ["gujarat", "गुजरात"],
    "haryana":          ["haryana", "हरियाणा"],
    "himachal pradesh": ["himachal", "himachal pradesh", "हिमाचल"],
    "jharkhand":        ["jharkhand", "झारखंड"],
    "karnataka":        ["karnataka", "ಕರ್ನಾಟಕ", "bangalore", "bengaluru", "mysore", "dharwad", "belgaum", "mandya", "raichur"],
    "kerala":           ["kerala", "கேரளா", "കേരളം"],
    "madhya pradesh":   ["madhya pradesh", "मध्य प्रदेश"],
    "maharashtra":      ["maharashtra", "vidarbha", "marathwada", "महाराष्ट्र", "पुणे", "नागपुर"],
    "manipur":          ["manipur"],
    "odisha":           ["odisha", "orissa", "ओडिशा"],
    "punjab":           ["punjab", "पंजाब"],
    "rajasthan":        ["rajasthan", "राजस्थान"],
    "tamil nadu":       ["tamil nadu", "tamilnadu", "தமிழ்நாடு"],
    "telangana":        ["telangana", "telengana", "తెలంగాణ"],
    "uttar pradesh":    ["uttar pradesh", "bundelkhand", "उत्तर प्रदेश"],
    "uttarakhand":      ["uttarakhand", "uttaranchal", "उत्तराखंड"],
    "west bengal":      ["west bengal", "पश्चिम बंगाल"],
    # Major agricultural districts and regional research centers
    "salem":            ["salem", "சேலம்"],
    "varanasi":         ["varanasi", "banaras", "kashi", "वाराणसी", "बनारस"],
    "coimbatore":       ["coimbatore", "kovai", "கோயம்புத்தூர்", "கோவை"],
    "delhi":            ["delhi", "new delhi", "दिल्ली"],
    "karnal":           ["karnal", "करनाल"],
    "ludhiana":         ["ludhiana", "लुधियाना"],
    "nagpur":           ["nagpur", "नागपुर"],
    "pune":             ["pune", "पुणे"],
    "nashik":           ["nashik", "nasik", "नासिक"],
    "kolar":            ["kolar", "ಕೋಲಾರ"],
    "bengaluru":        ["bengaluru", "bangalore", "ಬೆಂಗಳೂರು"],
    "chennai":          ["chennai", "madras", "சென்னை"],
    "hyderabad":        ["hyderabad", "హైదరాబాద్"],
    "guntur":           ["guntur", "గుంటూరు"],
    "patna":            ["patna", "पटना"],
    "lucknow":          ["lucknow", "लखनऊ"],
    "jaipur":           ["jaipur", "जयपुर"],
    "indore":           ["indore", "इंदौर"],
}

# ---------------------------------------------------------------------------
# Public typed result
# ---------------------------------------------------------------------------

class NERResult(TypedDict):
    crops: list[str]
    pests: list[str]
    diseases: list[str]
    soil: list[str]
    locations: list[str]
    schemes: list[str]
    fertilizers: list[str]
    nutrients: list[str]
    seasons: list[str]


# ---------------------------------------------------------------------------
# Hugging Face NER pipeline lazy loader
# ---------------------------------------------------------------------------

_hf_ner_pipeline: Optional[Any] = None


def get_hf_ner():
    """Lazily load Hugging Face token-classification / NER pipeline."""
    global _hf_ner_pipeline
    if _hf_ner_pipeline is None:
        model_name = os.getenv("HF_NER_MODEL", "dslim/bert-base-NER")
        try:
            # pyrefly: ignore [missing-import]
            from transformers import pipeline
            _hf_ner_pipeline = pipeline(
                "ner",
                model=model_name,
                aggregation_strategy="simple",
            )
        except Exception as exc:
            logger.info("HF NER model not loaded (%s). Using dictionary matching.", exc)
            _hf_ner_pipeline = False
    return _hf_ner_pipeline if _hf_ner_pipeline is not False else None


# ---------------------------------------------------------------------------
# Core matching helper
# ---------------------------------------------------------------------------

def _match_entities(
    text_lower: str,
    raw_text: str,
    entity_dict: dict[str, list[str]],
) -> list[str]:
    """Return sorted list of canonical labels whose aliases appear in text."""
    found: set[str] = set()
    for label, aliases in entity_dict.items():
        for alias in aliases:
            alias_lower = alias.lower()
            # If alias contains alphanumeric ASCII characters, enforce word boundaries
            # to prevent substring collisions (e.g. 'dal' matching inside 'modal',
            # 'rice' matching inside 'price').
            if any(c.isascii() and c.isalnum() for c in alias_lower):
                pattern = r'(?<![a-zA-Z0-9_])' + re.escape(alias_lower) + r'(?:s|es)?(?![a-zA-Z0-9_])'
                if re.search(pattern, text_lower):
                    found.add(label)
                    break
            else:
                if alias_lower in text_lower or alias in raw_text:
                    found.add(label)
                    break
    return sorted(found)


def extract_primary_commodity(text: str, entities: Optional[dict[str, list[str]]] = None) -> Optional[str]:
    """Extract the primary commodity explicitly mentioned in this query."""
    text_lower = text.lower()
    # 1. Exact word-boundary match across crop lexicon
    for label, aliases in CROP_ENTITIES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if any(c.isascii() and c.isalnum() for c in alias_lower):
                pat = r'(?<![a-zA-Z0-9_])' + re.escape(alias_lower) + r'(?![a-zA-Z0-9_])'
                if re.search(pat, text_lower):
                    return label
            elif alias_lower in text_lower or alias in text:
                return label

    # 2. Check entities dictionary if provided
    if entities and entities.get("crops"):
        return entities["crops"][0]

    return None


def extract_primary_location(text: str, entities: Optional[dict[str, list[str]]] = None) -> Optional[str]:
    """Extract the target agricultural location (district, city, or state) from query."""
    # 1. Check for prepositional location syntax: 'in <Place>', 'at <Place>', 'for <Place>'
    m = re.search(r'\b(?:in|at|around|near|for)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b', text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        candidate_lower = candidate.lower()
        stop_words = {
            "the", "this", "today", "tomorrow", "market", "mandi", "my", "our",
            "field", "farm", "prices", "price", "rate", "rates", "weather", "forecast",
        }
        if candidate_lower not in stop_words and len(candidate) > 2:
            return candidate.title()

    # 2. Check location entities
    if entities and entities.get("locations"):
        return entities["locations"][0].title()

    # 3. Direct lexicon search against known locations
    text_lower = text.lower()
    for loc, aliases in LOCATION_ENTITIES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if any(c.isascii() and c.isalnum() for c in alias_lower):
                pat = r'(?<![a-zA-Z0-9_])' + re.escape(alias_lower) + r'(?![a-zA-Z0-9_])'
                if re.search(pat, text_lower):
                    return loc.title()
            elif alias_lower in text_lower or alias in text:
                return loc.title()

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_agricultural_entities(text: str, use_hf: bool = False) -> NERResult:
    """Extract agricultural named entities from a farmer query.

    Args:
        text: Query string in English, Hindi, Kannada, Tamil, etc.
        use_hf: If True, optionally run Hugging Face NER to enrich locations.

    Returns:
        NERResult dictionary containing detected canonical entity labels.
    """
    text_lower = text.lower()

    crops = _match_entities(text_lower, text, CROP_ENTITIES)
    pests = _match_entities(text_lower, text, PEST_ENTITIES)
    diseases = _match_entities(text_lower, text, DISEASE_ENTITIES)
    soil = _match_entities(text_lower, text, SOIL_ENTITIES)
    schemes = _match_entities(text_lower, text, SCHEME_ENTITIES)
    fertilizers = _match_entities(text_lower, text, FERTILIZER_ENTITIES)
    nutrients = _match_entities(text_lower, text, NUTRIENT_ENTITIES)
    seasons = _match_entities(text_lower, text, SEASON_ENTITIES)
    locations = _match_entities(text_lower, text, LOCATION_ENTITIES)

    # If HF NER is requested and available, enrich locations from model predictions
    if use_hf:
        hf_ner = get_hf_ner()
        if hf_ner:
            try:
                preds = hf_ner(text)
                loc_set = set(locations)
                for ent in preds:
                    if ent.get("entity_group") == "LOC":
                        loc_word = ent.get("word", "").strip().lower()
                        if loc_word and len(loc_word) > 2:
                            loc_set.add(loc_word)
                locations = sorted(loc_set)
            except Exception as exc:
                logger.debug("HF NER extraction skipped: %s", exc)

    return NERResult(
        crops=crops,
        pests=pests,
        diseases=diseases,
        soil=soil,
        locations=locations,
        schemes=schemes,
        fertilizers=fertilizers,
        nutrients=nutrients,
        seasons=seasons,
    )

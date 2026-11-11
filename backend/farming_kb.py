"""Local agricultural knowledge base for Smart Farming Assistant.

Provides structured, cautious farming guidance in English and Tamil without
calling external APIs.
"""

from typing import Dict, List, Optional
import json
from pathlib import Path

# Common crop keywords for contextual guidance
CROP_KEYWORDS = {
    "tomato": ["tomato", "தக்காளி", "tamatar", "టమాట"],
    "paddy": ["paddy", "rice", "நெல்", "அரிசி", "dhan", "వరి"],
    "cotton": ["cotton", "பருத்தி", "kapas", "పత్తి"],
    "wheat": ["wheat", "கோதுமை", "gehu"],
    "banana": ["banana", "வாழை", "kela", "అరటి"],
    "chili": ["chili", "chilli", "மிளகாய்", "mirch", "మిరప"],
    "onion": ["onion", "வெங்காயம்", "pyaz", "ఉల్లి"],
}


def _detect_crop(text: str) -> Optional[str]:
    lowered = text.casefold()
    for crop_name, aliases in CROP_KEYWORDS.items():
        if any(alias in lowered for alias in aliases):
            return crop_name
    return None


# Knowledge base responses organized by intent and language
KB_ENTRIES: Dict[str, Dict[str, Dict[str, str]]] = {
    "irrigation": {
        "en": {
            "title": "Irrigation & Water Management Advisory",
            "general": (
                "• Watering Timing: Irrigate during early morning or late afternoon to minimize evaporation loss.\n"
                "• Soil Moisture Check: Test moisture by feeling soil 2 inches below the surface; water only when the top layer is moderately dry.\n"
                "• Drip Irrigation: Highly recommended for row crops and orchards. Saves 40-60% water and delivers moisture directly to the root zone.\n"
                "• Critical Stages: Crops require adequate moisture during flowering, pollination, and fruit/grain setting. Avoid waterlogging.\n"
                "• Conservation: Apply organic mulch (straw or dried leaves) around plant bases to retain soil moisture and suppress weeds."
            ),
            "crops": {
                "tomato": "Crop Tip (Tomato): Avoid wetting foliage directly to prevent fungal blight. Ensure steady, deep watering to prevent blossom end rot and fruit cracking.",
                "paddy": "Crop Tip (Paddy/Rice): Practice Alternate Wetting and Drying (AWD) rather than continuous flooding to conserve water while maintaining root aeration.",
                "cotton": "Crop Tip (Cotton): Critical water requirement is during flowering and square formation. Avoid over-irrigation during late vegetative stage.",
                "banana": "Crop Tip (Banana): Banana requires consistent moisture throughout vegetative growth. Drip irrigation with fertigation gives optimal bunch development.",
            },
            "disclaimer": "Local Note: Adjust irrigation frequency based on current soil texture (sandy vs. clay), seasonal rainfall, and temperature.",
        },
        "ta": {
            "title": "நீர்ப்பாசனம் மற்றும் நீர் மேலாண்மை வழிகாட்டல்",
            "general": (
                "• பாசன நேரம்: நீர் ஆவியாவதைத் தடுக்க அதிகாலை அல்லது மாலை வேளையில் மட்டுமே பாசனம் செய்யவும்.\n"
                "• மண் ஈரப்பதம்: மேல்மண் 2 அங்குல ஆழம் வரை உலர்ந்திருக்கும் போது மட்டுமே அடுத்த பாசனம் தரவும். வேர் அழுகலைத் தவிர்க்க தேங்கி நிற்கும் தண்ணீரை வடிக்கவும்.\n"
                "• சொட்டு நீர்ப்பாசனம்: 40% முதல் 60% வரை நீரைச் சேமிக்க சொட்டு நீர்ப்பாசன முறையைப் பயன்படுத்தவும். இது வேர் பகுதிக்கு நேரடியாக நீர் மற்றும் சத்துக்களைச் சேர்க்கும்.\n"
                "• முக்கியமான பாசன நிலைகள்: பூக்கும் பருவம் மற்றும் காய்/தானியம் பிடிக்கும் பருவங்களில் நீர் பற்றாக்குறை ஏற்படாமல் கவனமாகப் பாசனம் செய்யவும்.\n"
                "• மூடாக்கு முறை: மண்ணின் ஈரப்பதத்தைப் பாதுகாக்க காய்ந்த இலைகள் அல்லது வைக்கோல் கொண்டு பயிரின் அடிப்பகுதியில் மூடாக்கு அமைக்கவும்."
            ),
            "crops": {
                "tomato": "பயிர் குறிப்பு (தக்காளி): இலைகளில் தண்ணீர் தேங்காமல் தரைவழியாக நீர் பாய்ச்சவும். சீரான நீர் வழங்கல் காய் வெடிப்பு மற்றும் பூ உதிர்வதைத் தடுக்கும்.",
                "paddy": "பயிர் குறிப்பு (நெல்): தொடர்ந்து தண்ணீர் தேக்கி வைப்பதற்குப் பதிலாக மாற்று ஈர உலர்த்தல் (AWD) முறையைக் கடைப்பிடித்து நீரைச் சேமிக்கவும்.",
                "cotton": "பயிர் குறிப்பு (பருத்தி): பூக்கும் மற்றும் காய் பிடிக்கும் பருவத்தில் போதிய பாசனம் தேவை. அதிகப்படியான நீர் தேங்குவதைத் தவிர்க்கவும்.",
                "banana": "பயிர் குறிப்பு (வாழை): வாழைக்கு நிலையான மிதமான ஈரப்பதம் அவசியம். சொட்டு நீர் பாசனம் மூலம் உரமிடுதல் தார் வளர்ச்சியை அதிகரிக்கும்.",
            },
            "disclaimer": "உள்ளூர் குறிப்பு: உங்கள் மண்ணின் தன்மை (செம்மண்/கரிசல்) மற்றும் தற்போதைய மழைப்பொழிவுக்கு ஏற்ப பாசன இடைவெளியை மாற்றியமைக்கவும்.",
        },
    },
    "pest_control": {
        "en": {
            "title": "Integrated Pest Management (IPM) Advisory",
            "general": (
                "• Monitoring: Inspect crops early in the morning, focusing on the undersides of leaves and growing tips.\n"
                "• Cultural & Mechanical Control: Install yellow and blue sticky traps (10-12 per acre) to catch sucking pests like whiteflies, thrips, and aphids.\n"
                "• Biological & Organic Methods: Spray 5% Neem Seed Kernel Extract (NSKE) or 10,000 ppm Neem Oil formulation during early infestation stages as an effective bio-repellent.\n"
                "• Pheromone Traps: Set up species-specific pheromone traps to monitor and disrupt moth and borer populations.\n"
                "• Field Sanitation: Remove weed hosts and infected plant debris promptly from the field perimeter."
            ),
            "crops": {
                "tomato": "Crop Tip (Tomato): Watch for Fruit Borer (Helicoverpa) and Leaf Minor. Hand-pick infested fruits and destroy them. Plant marigold as a trap crop along borders.",
                "paddy": "Crop Tip (Paddy/Rice): For Yellow Stem Borer, install Trichogramma egg parasitoid cards. Clip seedling leaf tips before transplanting.",
                "cotton": "Crop Tip (Cotton): Monitor for Pink Bollworm using pheromone traps. Practice timely picking and destroy residual stalks after harvest.",
            },
            "disclaimer": "Safety & Dosage Warning: Never apply synthetic chemical pesticides without verifying the approved Central Insecticides Board (CIB) label. Exact dosages depend on pest severity and formulation. Consult your local Agricultural Extension Officer (KVK/Kisan Call Centre 1800-180-1551) before spraying.",
        },
        "ta": {
            "title": "ஒருங்கிணைந்த பயிர் பூச்சி மற்றும் நோய் மேலாண்மை",
            "general": (
                "• கள ஆய்வு: இலைகளின் அடிப்பகுதி மற்றும் குருத்துப் பகுதிகளை அதிகாலையில் கண்காணித்து பூச்சித் தாக்குதலைத் தொடக்கத்திலேயே கண்டறியவும்.\n"
                "• பொறிகள் அமைத்தல்: அசுவினி, வெள்ளை ஈ மற்றும் இலைப்பேன் போன்ற சாறு உறிஞ்சும் பூச்சிகளைக் கட்டுப்படுத்த ஏக்கருக்கு 10-12 மஞ்சள்/நீல நிற ஒட்டும் பொறிகளை அமைக்கவும்.\n"
                "• இயற்கை தடுப்பு முறைகள்: பூச்சித் தாக்குதலின் தொடக்க நிலையில் 5% வேப்பங்கொட்டை கரைசல் (NSKE) அல்லது தரமான வேப்பெண்ணெய் கரைசல் தெளிப்பது நல்ல பலன் தரும்.\n"
                "• இனக்கவர்ச்சி பொறிகள்: காய்ப்புழு மற்றும் தண்டுப்புழுக்களின் தாய் அந்துப்பூச்சிகளைக் கட்டுப்படுத்த ஏக்கருக்கு 4-5 இனக்கவர்ச்சி பொறிகளை நிறுவவும்.\n"
                "• வயல் தூய்மை: வயல் வரப்புகளில் உள்ள களைகள் மற்றும் பாதிக்கப்பட்ட பயிர் எச்சங்களை உடனுக்குடன் அப்புறப்படுத்தவும்."
            ),
            "crops": {
                "tomato": "பயிர் குறிப்பு (தக்காளி): காய்ப்புழு மற்றும் இலைச்சுரங்கப் புழுவை கண்காணிக்கவும். வயல் வரப்புகளில் கவர்ச்சிப் பயிராக செண்டுமல்லி நடவு செய்யவும்.",
                "paddy": "பயிர் குறிப்பு (நெல்): தண்டுத்துளைப்பானைக் கட்டுப்படுத்த டிரைக்கோடெர்மா அல்லது டிரைக்கோகிரம்மா ஒட்டுண்ணி அட்டைகளைப் பயன்படுத்தவும்.",
                "cotton": "பயிர் குறிப்பு (பருத்தி): இளஞ்சிவப்பு காய்ப்புழு கண்காணிப்புக்கு இனக்கவர்ச்சி பொறி வைக்கவும். அறுவடைக்குப் பின் பருத்தி குச்சிகளை அகற்றவும்.",
            },
            "disclaimer": "பாதுகாப்பு மற்றும் மருந்து அளவு எச்சரிக்கை: ரசாயன பூச்சிக்கொல்லிகளைப் பயன்படுத்தும் முன் அங்கீகரிக்கப்பட்ட தயாரிப்பு அட்டவணையை (Product Label) கவனமாகப் படிக்கவும். தன்னிச்சையாக மருந்தளவை கூட்டவோ குறைக்கவோ கூடாது. உங்கள் வட்டார வேளாண்மை உதவி இயக்குநர் அலுவலகம் அல்லது உழவர் உதவி மையம் (1800-180-1551) ஆலோசனை பெற்றே தெளிக்கவும்.",
        },
    },
    "crop_advisory": {
        "en": {
            "title": "Crop Advisory & Soil Health Guidance",
            "general": (
                "• Soil Testing: Base all fertilizer applications on a recent Soil Health Card. Avoid applying nitrogen indiscriminately.\n"
                "• Organic Matter: Incorporate 5 tons of well-decomposed Farmyard Manure (FYM) or vermicompost per acre during land preparation to improve soil structure and microbial activity.\n"
                "• Balanced Nutrition: Balance primary nutrients (N-P-K) with essential secondary nutrients (Sulfur, Calcium) and micronutrients (Zinc, Boron).\n"
                "• Bio-fertilizers: Seed treatment with Azospirillum / Rhizobium and Phosphobacteria fixes atmospheric nitrogen and solubilizes phosphate naturally.\n"
                "• Crop Rotation: Rotate cereal crops with leguminous pulses to break pest cycles and replenish nitrogen naturally."
            ),
            "crops": {
                "paddy": "Crop Tip (Paddy): Apply nitrogen in three split doses (basal, tillering, and panicle initiation) rather than a single heavy application.",
                "wheat": "Crop Tip (Wheat): Crown Root Initiation (CRI) stage at 20-25 days after sowing is critical for first fertilizer top-dressing and light irrigation.",
                "banana": "Crop Tip (Banana): Potash requirement is very high from 5th month onwards for bunch filling and fruit quality.",
            },
            "disclaimer": "Dosage & Application Notice: Exact fertilizer quantities must match your regional soil test values and crop variety. Do not apply chemical fertilizers without consulting local agricultural extension guidelines.",
        },
        "ta": {
            "title": "பயிர் சாகுபடி மற்றும் மண் வள வழிகாட்டல்",
            "general": (
                "• மண் பரிசோதனை: மண் வள அட்டை (Soil Health Card) பரிந்துரைப்படி மட்டுமே உரமிடவும். கண்மூடித்தனமாக யூரியா இடுவதைத் தவிர்க்கவும்.\n"
                "• இயற்கை உரம்: நிலத் தயாரிப்பின் போது ஏக்கருக்கு 4-5 டன் மக்கிய தொழுவுரம் அல்லது 2 டன் மண்புழு உரம் இட்டு உழவு செய்யவும்.\n"
                "• சமச்சீர் உர மேலாண்மை: தழை, மணி, சாம்பல் (N-P-K) சத்துக்களுடன் துத்தநாகம் (Zinc) மற்றும் போரான் போன்ற நுண்ணூட்டச் சத்துக்களையும் தகுந்த அளவில் வழங்கவும்.\n"
                "• உயிர் உரங்கள்: அசோஸ்பைரில்லம் மற்றும் பாஸ்போபாக்டீரியா கொண்டு விதை நேர்த்தி அல்லது வேர் நேர்த்தி செய்வது வேர் வளர்ச்சியைத் தூண்டும்.\n"
                "• பயிர் சுழற்சி: தானியப் பயிர்களுக்குப் பிறகு உளுந்து, பாசிப்பயறு போன்ற பயறு வகை பயிர்களைப் பயிரிடுவது நிலத்தின் தழைச்சத்தை இயற்கையாக உயர்த்தும்."
            ),
            "crops": {
                "paddy": "பயிர் குறிப்பு (நெல்): தழைச்சத்தை ஒரே நேரத்தில் இடாமல் அடி உரம், தூர்கட்டும் பருவம், கதிர் உருவாகும் பருவம் என பிரித்து இடவும்.",
                "wheat": "பயிர் குறிப்பு (கோதுமை): விதைத்த 20-25 நாட்களில் முதல் மேலுரமிடுதலும் லேசான நீர்ப்பாசனமும் வேர் வளர்ச்சிக்கு மிக அவசியம்.",
                "banana": "பயிர் குறிப்பு (வாழை): 5-ஆம் மாதத்திற்குப் பிறகு பொட்டாஷ் (சாம்பல் சத்து) தேவையை சீராக வழங்குவது வாழைத்தார் எடையை உயர்த்தும்.",
            },
            "disclaimer": "உர அளவு எச்சரிக்கை: பரிந்துரைக்கப்பட்ட உர அளவுகள் உங்கள் நிலத்தின் மண் தன்மை மற்றும் பயிர் ரகத்தைப் பொறுத்து மாறுபடும். வட்டார வேளாண்மை அலுவலர் வழிகாட்டுதல்படி மட்டுமே ரசாயன உரங்களைப் பயன்படுத்தவும்.",
        },
    },
    "market_prices": {
        "en": {
            "title": "Agricultural Market & Price Information Advisory",
            "general": (
                "• Daily Price Fluctuations: Agricultural mandi prices fluctuate daily based on local arrivals, moisture content, grading, and transportation costs.\n"
                "• Official Live Portals: Never rely on unofficial rumors. Always check live, verified daily wholesale prices on:\n"
                "  1. Agmarknet (Ministry of Agriculture): agmarknet.gov.in\n"
                "  2. e-NAM (National Agriculture Market): enam.gov.in\n"
                "  3. State APMC / Agricultural Marketing Board websites and state farmer mobile apps.\n"
                "• Post-Harvest Value Addition: Clean, sort, and grade produce before transporting to market. Graded produce commands a 10-25% higher price in mandis.\n"
                "• Storage Advice: Where prices are temporarily depressed due to peak harvest glut, consider scientific warehouse storage (WDRA accredited) to access warehouse receipt financing."
            ),
            "crops": {},
            "disclaimer": "Important Price Notice: This assistant does not display live prices because mandi rates vary continuously by hour and location. Please consult your local APMC Mandi, e-NAM portal, or state Uzhavan/Kisan app for today's authentic prices.",
        },
        "ta": {
            "title": "வேளாண் விளைபொருள் சந்தை விலை வழிகாட்டல்",
            "general": (
                "• தினசரி விலை மாற்றம்: உழவர் சந்தை மற்றும் ஒழுங்குமுறை விற்பனைக் கூடங்களில் வரத்து, தரம் மற்றும் ஈரப்பதத்தைப் பொறுத்து விளைபொருட்களின் விலை தினமும் மாறுகிறது.\n"
                "• அதிகாரப்பூர்வ நேரடி விலை தளங்கள்: தவறான வதந்திகளைத் தவிர்த்து, உண்மையான தினசரி விலைகளை அறிய பின்வரும் தளங்களைப் பார்வையிடவும்:\n"
                "  1. அக்மார்க்நெட் (Agmarknet): agmarknet.gov.in\n"
                "  2. இ-நாம் தேசிய வேளாண் சந்தை (e-NAM): enam.gov.in\n"
                "  3. தமிழ்நாடு அரசின் 'உழவன்' (Uzhavan) செயலி மற்றும் உள்ளூர் ஒழுங்குமுறை விற்பனைக் கூட அறிவிப்புப் பலகை.\n"
                "• தரம் பிரித்தல்: விளைபொருட்களைச் சந்தைக்கு எடுத்துச் செல்லும் முன் தூய்மை செய்து தரம் பிரிக்கவும். தரம் பிரிக்கப்பட்ட விளைபொருளுக்கு 15% கூடுதல் விலை கிடைக்கும்.\n"
                "• சேமிப்பு கிடங்கு: அறுவடை காலத்தில் வரத்து அதிகமாகி விலை குறையும் போது ஒழுங்குமுறை விற்பனைக் கூட சேமிப்புக் கிடங்குகளில் பாதுகாத்து வைத்து விலை உயரும்போது விற்கலாம்."
            ),
            "crops": {},
            "disclaimer": "முக்கிய விலை அறிவிப்பு: சந்தை விலைகள் மணிநேரத்திற்கு மணிநேரம் மாறும் என்பதால், நேரடி விலைகளை நாங்கள் கணித்துக் கூற மாட்டோம். இன்றைய சரியான விலையை அறிய உழவன் செயலி அல்லது அருகிலுள்ள ஒழுங்குமுறை விற்பனைக் கூடத்தை நேரடியாக அணுகவும்.",
        },
    },
    "government_schemes": {
        "en": {
            "title": "Agricultural Schemes & Farmer Support Advisory",
            "general": (
                "• PM-KISAN (Pradhan Mantri Kisan Samman Nidhi): Provides income support of Rs. 6,000/year in three equal installments to eligible landholding farmer families. Apply & verify Aadhaar e-KYC on pmkisan.gov.in.\n"
                "• PMFBY (Pradhan Mantri Fasal Bima Yojana): Comprehensive crop insurance against non-preventable natural risks from pre-sowing to post-harvest. Enroll via your bank or pmfby.gov.in within seasonal cut-off dates.\n"
                "• Micro Irrigation Scheme (PMKSY - Per Drop More Crop): Provides 70% to 100% subsidies (varies by state/category: small, marginal, SC/ST farmers) for installing drip and sprinkler systems.\n"
                "• Soil Health Card Scheme: Periodic soil testing across 12 parameters provided free or at nominal cost through state labs.\n"
                "• Kisan Credit Card (KCC): Concessional institutional credit at low interest rates for seasonal crop production and allied activities.\n"
                "• Required Documents: Keep Aadhaar card, Land Record (Patta/Chitta/7-12), active Bank Passbook, and passport photo ready for all applications."
            ),
            "crops": {},
            "disclaimer": "Eligibility Notice: Exact subsidy percentages, eligibility criteria, and application windows depend on your state and landholding size. Please verify your eligibility at your local Block Agricultural Office, e-Sevai/CSC Centre, or official government portal.",
        },
        "ta": {
            "title": "அரசு வேளாண் திட்டங்கள் மற்றும் மானிய வழிகாட்டல்",
            "general": (
                "• பி.எம். கிசான் (PM-KISAN): நிலமுள்ள விவசாயக் குடும்பங்களுக்கு ஆண்டுக்கு ரூ. 6,000 நிதியுதவி மூன்று தவணைகளாக வழங்கப்படுகிறது. ஆதார் e-KYC சரிபார்ப்பை pmkisan.gov.in தளத்தில் செய்யவும்.\n"
                "• பிரதம மந்திரி பயிர் காப்பீட்டுத் திட்டம் (PMFBY): இயற்கை இடர்பாடுகளால் ஏற்படும் பயிர் இழப்பிற்கு விரிவான காப்பீடு வழங்கப்படுகிறது. உரிய பருவ காலக்கெடுவுக்குள் தொடக்க வேளாண் கூட்டுறவு சங்கம் அல்லது வங்கிகள் மூலம் பதிவு செய்யவும்.\n"
                "• நுண்ணீர்ப் பாசன மானியத் திட்டம்: சிறு, குறு விவசாயிகளுக்கு 100% மானியத்திலும், இதர விவசாயிகளுக்கு 75% மானியத்திலும் சொட்டு நீர் மற்றும் தெளிப்பு நீர்ப் பாசன கருவிகள் வழங்கப்படுகின்றன.\n"
                "• வேளாண் இயந்திரமயமாக்கல் திட்டம்: டிராக்டர்கள், பவர்டில்லர்கள் மற்றும் அறுவடை இயந்திரங்கள் வாங்க அரசு மானியம் வழங்குகிறது.\n"
                "• தேவையான ஆவணங்கள்: ஆதார் அட்டை, நில ஆவணங்கள் (பட்டா, சிட்டா, அடங்கல்), வங்கி கணக்குப் புத்தக நகல் மற்றும் புகைப்படம்."
            ),
            "crops": {},
            "disclaimer": "மானிய விவர அறிவிப்பு: திட்டங்களின் தகுதி மற்றும் தற்போதைய நிதி ஒதுக்கீடு மாவட்டத்திற்கு மாவட்டம் மாறுபடும். துல்லியமான விவரங்களை அறிய உங்கள் வட்டார வேளாண்மை விரிவாக்க மையம் (Block Agriculture Office) அல்லது 'உழவன்' செயலி மூலம் விண்ணப்பித்து பயன்பெறவும்.",
        },
    },
}


def get_farming_answer(
    intent: str,
    text: str = "",
    language_code: str = "en",
) -> Dict[str, str]:
    """Generates localized agricultural advice based on intent and language.

    Args:
        intent: One of irrigation, pest_control, crop_advisory,
                market_prices, government_schemes.
        text: Original farmer question for crop identification.
        language_code: Detected language code (e.g. 'en', 'ta', 'hi', etc.).

    Returns:
        Dict with 'answer', 'language_code', 'language_label', and 'source'.
    """
    valid_intent = intent if intent in KB_ENTRIES else "crop_advisory"

    is_tamil = language_code == "ta"
    selected_lang = "ta" if is_tamil else "en"
    entry = KB_ENTRIES[valid_intent][selected_lang]

    sections = [f"【{entry['title']}】", entry["general"]]

    # Add crop specific contextual tip if detected
    detected_crop = _detect_crop(text)
    if detected_crop and detected_crop in entry.get("crops", {}):
        crop_tip = entry["crops"][detected_crop]
        sections.append(f"\n🌱 {crop_tip}")

    # Add strict official disclaimer
    if entry.get("disclaimer"):
        sections.append(f"\n⚠️ {entry['disclaimer']}")

    raw_answer = "\n\n".join(sections)

    # For languages other than English and Tamil, provide English with clear label
    if not is_tamil and language_code != "en":
        labeled_answer = (
            f"[Language Note: Response provided in English as reliable local guidance is currently available in English and Tamil.]\n\n"
            f"{raw_answer}"
        )
        return {
            "answer": labeled_answer,
            "response_language": "English",
            "detected_language_code": language_code,
            "source": "local_knowledge_base",
        }

    return {
        "answer": raw_answer,
        "response_language": "Tamil" if is_tamil else "English",
        "detected_language_code": language_code,
        "source": "local_knowledge_base",
    }


# ---------------------------------------------------------------------------
# Knowledge source provenance helpers (Stage B)
# ---------------------------------------------------------------------------

_SOURCES_PATH = Path(__file__).parent / "knowledge_sources.json"


def load_sources() -> dict:
    """Load and return the full knowledge_sources.json document.

    Returns an empty dict with an error key if the file is missing or invalid
    JSON so callers never crash.
    """
    try:
        with _SOURCES_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"error": "knowledge_sources.json not found", "sources": []}
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in knowledge_sources.json: {exc}", "sources": []}


def get_sources_for_intent(intent: str) -> List[dict]:
    """Return a list of source records relevant to the given intent.

    Args:
        intent: One of irrigation, pest_control, crop_advisory,
                market_prices, government_schemes.

    Returns:
        List of source dicts from knowledge_sources.json, or [] on error.
    """
    data = load_sources()
    if "error" in data:
        return []

    mapping: dict = data.get("intent_source_mapping", {})
    source_ids: List[str] = mapping.get(intent, [])
    all_sources: List[dict] = data.get("sources", [])
    id_to_source = {s["id"]: s for s in all_sources}

    return [id_to_source[sid] for sid in source_ids if sid in id_to_source]

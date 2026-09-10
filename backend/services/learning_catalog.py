"""
Catalog boundary for iGOT Karmayogi and NSSTA/TPAC recommendations.

No public partner API exists for either provider today (see
docs/SIH26101_FEASIBILITY_AND_ROADMAP.md, section 3.4) -- this module is
deliberately honest about that rather than fabricating a course ID,
enrolment, or completion record. Every recommendation either points at this
app's own adaptive practice quests (verifiable, real) or at the provider's
public catalog page (real, but not a confirmed live sync). integration_status()
is what routes/learning.py's GET /learning/integrations/status and the
Academy UI's "iGOT mode: ..." line read from -- flip a provider to
"configured" only once a real adapter exists behind these functions.
"""
from __future__ import annotations

import os

from integrations.provider import LiveHTTPProviderAdapter, SimulatedIGOTAdapter

IGOT_CATALOG_URL = "https://igotkarmayogi.gov.in/"
NSSTA_CATALOG_URL = "https://nssta.gov.in/document"

# Read once at import, same as before -- but no longer the whole story. An
# env var being *set* only selects which adapter integration_status() below
# asks; whether that adapter's health_check() actually succeeds is what
# decides the reported mode now, per docs/contracts/provider-adapter.md's own
# rule that "an environment variable alone must never imply LIVE". Kept under
# these names for backward compatibility with anything importing them
# directly (e.g. tests/test_learning_platform.py's importlib.reload seam).
IGOT_CONFIGURED = bool(os.getenv("IGOT_API_BASE_URL"))
NSSTA_CONFIGURED = bool(os.getenv("NSSTA_API_BASE_URL"))

# `mode` values use the fixed, documented vocabulary (CODEX.md/CLAUDE.md
# architectural invariants: SIMULATED, CATALOGUE, LIVE, PROVISIONAL,
# NO EVIDENCE -- see tests/test_competency_status_vocabulary.py) instead of
# this module's old "configured"/"catalog-fallback" pair, which matched
# nothing else in the codebase's vocabulary. `CATALOGUE` covers both "never
# configured" and "configured but the health check failed" -- either way,
# recommendations fall back to the real public catalog link, which is
# genuinely what CATALOGUE means here; the *why* goes in `detail`, not in a
# sixth ad hoc mode value. The frontend compares `mode` by equality, so this
# is a breaking rename for any consumer still checking "configured" --
# frontend/lib/api and frontend/components were updated in the same change.
_DETAIL = {
    "en": {
        "igot_live": "Live iGOT Karmayogi API reachable (health check succeeded).",
        "igot_error": (
            "IGOT_API_BASE_URL is set but the health check failed -- falling back to the "
            "authoritative public catalog instead of reporting a live sync that isn't real."
        ),
        "igot_fallback": (
            "No public iGOT Karmayogi partner API exists today. Recommendations link to "
            "the authoritative public catalog instead of a fabricated enrolment record."
        ),
        "nssta_live": "Live NSSTA/TPAC programme feed reachable (health check succeeded).",
        "nssta_error": (
            "NSSTA_API_BASE_URL is set but the health check failed -- falling back to the "
            "published training-calendar documents instead of reporting a live sync that isn't real."
        ),
        "nssta_fallback": (
            "No public NSSTA/TPAC programme API exists today. Recommendations link to "
            "the published NSSTA training-calendar documents instead."
        ),
    },
    "hi": {
        "igot_live": "लाइव iGOT कर्मयोगी API पहुंच योग्य है (हेल्थ चेक सफल रहा)।",
        "igot_error": (
            "IGOT_API_BASE_URL सेट है लेकिन हेल्थ चेक विफल रहा -- एक झूठा लाइव सिंक बताने के "
            "बजाय आधिकारिक सार्वजनिक सूची पर वापस जा रहे हैं।"
        ),
        "igot_fallback": (
            "आज कोई सार्वजनिक iGOT कर्मयोगी पार्टनर API मौजूद नहीं है। अनुशंसाएं एक काल्पनिक "
            "नामांकन रिकॉर्ड के बजाय आधिकारिक सार्वजनिक सूची से जुड़ी हैं।"
        ),
        "nssta_live": "लाइव NSSTA/TPAC कार्यक्रम फ़ीड पहुंच योग्य है (हेल्थ चेक सफल रहा)।",
        "nssta_error": (
            "NSSTA_API_BASE_URL सेट है लेकिन हेल्थ चेक विफल रहा -- एक झूठा लाइव सिंक बताने के "
            "बजाय प्रकाशित प्रशिक्षण-कैलेंडर दस्तावेज़ों पर वापस जा रहे हैं।"
        ),
        "nssta_fallback": (
            "आज कोई सार्वजनिक NSSTA/TPAC कार्यक्रम API मौजूद नहीं है। अनुशंसाएं प्रकाशित "
            "NSSTA प्रशिक्षण-कैलेंडर दस्तावेज़ों से जुड़ी हैं।"
        ),
    },
    "bn": {
        "igot_live": "লাইভ iGOT কর্মযোগী API পৌঁছানো যায় (স্বাস্থ্য পরীক্ষা সফল)।",
        "igot_error": "IGOT_API_BASE_URL সেট করা হয়েছে কিন্তু স্বাস্থ্য পরীক্ষা ব্যর্থ হয়েছে -- একটি মিথ্যা লাইভ সিঙ্ক রিপোর্ট করার পরিবর্তে অফিসিয়াল পাবলিক ক্যাটালগে ফিরে যাচ্ছে।",
        "igot_fallback": "কোনো পাবলিক iGOT কর্মযোগী অংশীদার API আজ বিদ্যমান নেই৷ সুপারিশগুলি একটি সিমুলেটেড তালিকাভুক্তির রেকর্ডের পরিবর্তে সরকারী পাবলিক ক্যাটালগের সাথে লিঙ্ক করে।",
        "nssta_live": "লাইভ NSSTA/TPAC প্রোগ্রাম ফিড পৌঁছানো যায় (স্বাস্থ্য পরীক্ষা সফল)।",
        "nssta_error": "NSSTA_API_BASE_URL সেট করা হয়েছে কিন্তু স্বাস্থ্য পরীক্ষা ব্যর্থ হয়েছে -- একটি লাইভ সিঙ্ক রিপোর্ট করার পরিবর্তে প্রকাশিত প্রশিক্ষণ-ক্যালেন্ডার নথিতে ফিরে যাওয়া যা বাস্তব নয়।",
        "nssta_fallback": "কোনো পাবলিক NSSTA/TPAC প্রোগ্রাম API আজ বিদ্যমান নেই। পরিবর্তে প্রকাশিত NSSTA প্রশিক্ষণ-ক্যালেন্ডার নথির সাথে সুপারিশের লিঙ্ক।",
    },
    "mr": {
        "igot_live": "थेट iGOT कर्मयोगी API पोहोचण्यायोग्य (आरोग्य तपासणी यशस्वी).",
        "igot_error": "IGOT_API_BASE_URL सेट केले आहे परंतु आरोग्य तपासणी अयशस्वी झाली -- खोट्या थेट समक्रमणाची तक्रार करण्याऐवजी अधिकृत सार्वजनिक कॅटलॉगवर परत येणे.",
        "igot_fallback": "आज कोणतेही सार्वजनिक iGOT कर्मयोगी भागीदार API अस्तित्वात नाही. सिम्युलेटेड नावनोंदणी रेकॉर्डऐवजी शिफारशी अधिकृत सार्वजनिक कॅटलॉगशी जोडल्या जातात.",
        "nssta_live": "थेट NSSTA/TPAC प्रोग्राम फीड पोहोचण्यायोग्य (आरोग्य तपासणी यशस्वी).",
        "nssta_error": "NSSTA_API_BASE_URL सेट केले आहे परंतु आरोग्य तपासणी अयशस्वी झाली -- वास्तविक नसलेल्या थेट समक्रमणाची तक्रार करण्याऐवजी प्रकाशित प्रशिक्षण-कॅलेंडर दस्तऐवजांवर परत येणे.",
        "nssta_fallback": "आज कोणतेही सार्वजनिक NSSTA/TPAC प्रोग्राम API अस्तित्वात नाही. त्याऐवजी शिफारशी प्रकाशित NSSTA प्रशिक्षण-कॅलेंडर दस्तऐवजांशी लिंक करतात.",
    },
    "te": {
        "igot_live": "ప్రత్యక్ష iGOT కర్మయోగి API అందుబాటులో ఉంది (ఆరోగ్య తనిఖీ విజయవంతమైంది).",
        "igot_error": "IGOT_API_BASE_URL సెట్ చేయబడింది కానీ ఆరోగ్య తనిఖీ విఫలమైంది -- తప్పుడు ప్రత్యక్ష సమకాలీకరణను నివేదించడానికి బదులుగా అధికారిక పబ్లిక్ కేటలాగ్‌కి తిరిగి వస్తుంది.",
        "igot_fallback": "ఈ రోజు పబ్లిక్ iGOT కర్మయోగి భాగస్వామి API ఏదీ లేదు. సిఫార్సులు అనుకరణ నమోదు రికార్డుకు బదులుగా అధికారిక పబ్లిక్ కేటలాగ్‌కు లింక్ చేస్తాయి.",
        "nssta_live": "ప్రత్యక్ష ప్రసార NSSTA/TPAC ప్రోగ్రామ్ ఫీడ్ చేరుకోదగినది (ఆరోగ్య తనిఖీ విజయవంతమైంది).",
        "nssta_error": "NSSTA_API_BASE_URL సెట్ చేయబడింది కానీ ఆరోగ్య తనిఖీ విఫలమైంది -- నిజమైనది కాని ప్రత్యక్ష సమకాలీకరణను నివేదించడానికి బదులుగా ప్రచురించిన శిక్షణ-క్యాలెండర్ పత్రాలకు తిరిగి వస్తుంది.",
        "nssta_fallback": "ఈ రోజు పబ్లిక్ NSSTA/TPAC ప్రోగ్రామ్ API ఏదీ లేదు. బదులుగా ప్రచురించబడిన NSSTA శిక్షణ-క్యాలెండర్ డాక్యుమెంట్‌లకు సిఫార్సులు లింక్ చేయబడ్డాయి.",
    },
    "ta": {
        "igot_live": "நேரடி iGOT Karmayogi API அணுகக்கூடியது (சுகாதார சோதனை வெற்றி பெற்றது).",
        "igot_error": "IGOT_API_BASE_URL அமைக்கப்பட்டது, ஆனால் சுகாதார சோதனை தோல்வியடைந்தது -- தவறான நேரலை ஒத்திசைவைப் புகாரளிப்பதற்குப் பதிலாக அதிகாரப்பூர்வ பொது அட்டவணைக்கு திரும்புகிறது.",
        "igot_fallback": "பொது iGOT கர்மயோகி பார்ட்னர் API இன்று இல்லை. சிமுலேட்டட் பதிவு பதிவுக்குப் பதிலாக அதிகாரப்பூர்வ பொது அட்டவணையில் பரிந்துரைகள் இணைக்கப்பட்டுள்ளன.",
        "nssta_live": "நேரடி NSSTA/TPAC நிரல் ஊட்டத்தை அணுகலாம் (சுகாதார சோதனை வெற்றி பெற்றது).",
        "nssta_error": "NSSTA_API_BASE_URL அமைக்கப்பட்டது, ஆனால் சுகாதார சோதனை தோல்வியடைந்தது -- உண்மையானது அல்லாத நேரடி ஒத்திசைவைப் புகாரளிப்பதற்குப் பதிலாக வெளியிடப்பட்ட பயிற்சி-காலண்டர் ஆவணங்களுக்குத் திரும்புகிறது.",
        "nssta_fallback": "பொது NSSTA/TPAC நிரல் API இன்று இல்லை. அதற்குப் பதிலாக வெளியிடப்பட்ட NSSTA பயிற்சி-காலண்டர் ஆவணங்களுடன் பரிந்துரைகள் இணைக்கப்பட்டுள்ளன.",
    },
    "gu": {
        "igot_live": "લાઇવ iGOT કર્મયોગી API પહોંચી શકાય તેવું (સ્વાસ્થ્ય તપાસ સફળ).",
        "igot_error": "IGOT_API_BASE_URL સેટ કરેલ છે પરંતુ આરોગ્ય તપાસ નિષ્ફળ ગઈ -- ખોટા લાઇવ સમન્વયનની જાણ કરવાને બદલે અધિકૃત સાર્વજનિક સૂચિ પર પાછા ફરવું.",
        "igot_fallback": "આજે કોઈ સાર્વજનિક iGOT કર્મયોગી ભાગીદાર API અસ્તિત્વમાં નથી. ભલામણો સિમ્યુલેટેડ નોંધણી રેકોર્ડને બદલે સત્તાવાર જાહેર સૂચિ સાથે લિંક કરે છે.",
        "nssta_live": "લાઇવ NSSTA/TPAC પ્રોગ્રામ ફીડ પહોંચી શકાય તેવું (સ્વાસ્થ્ય તપાસ સફળ).",
        "nssta_error": "NSSTA_API_BASE_URL સેટ કરેલ છે પરંતુ આરોગ્ય તપાસ નિષ્ફળ ગઈ -- લાઈવ સિંકની જાણ કરવાને બદલે પ્રકાશિત તાલીમ-કેલેન્ડર દસ્તાવેજો પર પાછા ફરવું જે વાસ્તવિક નથી.",
        "nssta_fallback": "આજે કોઈ સાર્વજનિક NSSTA/TPAC પ્રોગ્રામ API અસ્તિત્વમાં નથી. ભલામણો તેના બદલે પ્રકાશિત NSSTA તાલીમ-કેલેન્ડર દસ્તાવેજો સાથે લિંક કરે છે.",
    },
    "ur": {
        "igot_live": "لائیو iGOT Karmayogi API قابل رسائی (صحت کی جانچ کامیاب)۔",
        "igot_error": "IGOT_API_BASE_URL سیٹ ہے لیکن صحت کی جانچ ناکام ہوگئی -- غلط لائیو مطابقت پذیری کی اطلاع دینے کے بجائے سرکاری عوامی کیٹلاگ میں واپس جانا۔",
        "igot_fallback": "آج کوئی عوامی iGOT Karmayogi پارٹنر API موجود نہیں ہے۔ سفارشات نقلی اندراج کے ریکارڈ کے بجائے سرکاری عوامی کیٹلاگ سے منسلک ہوتی ہیں۔",
        "nssta_live": "لائیو NSSTA/TPAC پروگرام فیڈ قابل رسائی (صحت کی جانچ کامیاب)۔",
        "nssta_error": "NSSTA_API_BASE_URL سیٹ ہے لیکن صحت کی جانچ ناکام رہی -- ایک لائیو مطابقت پذیری کی اطلاع دینے کے بجائے شائع شدہ تربیتی-کیلنڈر دستاویزات پر واپس جانا جو حقیقی نہیں ہے۔",
        "nssta_fallback": "آج کوئی عوامی NSSTA/TPAC پروگرام API موجود نہیں ہے۔ اس کے بجائے سفارشات شائع شدہ NSSTA تربیتی کیلنڈر دستاویزات سے منسلک ہیں۔",
    },
    "kn": {
        "igot_live": "ಲೈವ್ iGOT ಕರ್ಮಯೋಗಿ API ತಲುಪಬಹುದು (ಆರೋಗ್ಯ ತಪಾಸಣೆ ಯಶಸ್ವಿಯಾಗಿದೆ).",
        "igot_error": "IGOT_API_BASE_URL ಅನ್ನು ಹೊಂದಿಸಲಾಗಿದೆ ಆದರೆ ಆರೋಗ್ಯ ತಪಾಸಣೆ ವಿಫಲವಾಗಿದೆ -- ತಪ್ಪಾದ ಲೈವ್ ಸಿಂಕ್ ಅನ್ನು ವರದಿ ಮಾಡುವ ಬದಲು ಅಧಿಕೃತ ಸಾರ್ವಜನಿಕ ಕ್ಯಾಟಲಾಗ್‌ಗೆ ಹಿಂತಿರುಗಿದೆ.",
        "igot_fallback": "ಯಾವುದೇ ಸಾರ್ವಜನಿಕ iGOT ಕರ್ಮಯೋಗಿ ಪಾಲುದಾರ API ಇಂದು ಅಸ್ತಿತ್ವದಲ್ಲಿಲ್ಲ. ಸಿಮ್ಯುಲೇಟೆಡ್ ದಾಖಲಾತಿ ದಾಖಲೆಯ ಬದಲಿಗೆ ಅಧಿಕೃತ ಸಾರ್ವಜನಿಕ ಕ್ಯಾಟಲಾಗ್‌ಗೆ ಶಿಫಾರಸುಗಳು ಲಿಂಕ್ ಮಾಡುತ್ತವೆ.",
        "nssta_live": "ಲೈವ್ NSSTA/TPAC ಪ್ರೋಗ್ರಾಂ ಫೀಡ್ ತಲುಪಬಹುದು (ಆರೋಗ್ಯ ತಪಾಸಣೆ ಯಶಸ್ವಿಯಾಗಿದೆ).",
        "nssta_error": "NSSTA_API_BASE_URL ಅನ್ನು ಹೊಂದಿಸಲಾಗಿದೆ ಆದರೆ ಆರೋಗ್ಯ ತಪಾಸಣೆ ವಿಫಲವಾಗಿದೆ -- ನೈಜವಲ್ಲದ ಲೈವ್ ಸಿಂಕ್ ಅನ್ನು ವರದಿ ಮಾಡುವ ಬದಲು ಪ್ರಕಟಿಸಿದ ತರಬೇತಿ-ಕ್ಯಾಲೆಂಡರ್ ಡಾಕ್ಯುಮೆಂಟ್‌ಗಳಿಗೆ ಹಿಂತಿರುಗಿ.",
        "nssta_fallback": "ಯಾವುದೇ ಸಾರ್ವಜನಿಕ NSSTA/TPAC ಪ್ರೋಗ್ರಾಂ API ಇಂದು ಅಸ್ತಿತ್ವದಲ್ಲಿಲ್ಲ. ಬದಲಿಗೆ ಪ್ರಕಟಿತ NSSTA ತರಬೇತಿ-ಕ್ಯಾಲೆಂಡರ್ ದಾಖಲೆಗಳಿಗೆ ಶಿಫಾರಸುಗಳು ಲಿಂಕ್.",
    },
    "or": {
        "igot_live": "ଲାଇଭ୍ iGOT କରମାୟୋଗୀ API ଉପଲବ୍ଧ (ସ୍ୱାସ୍ଥ୍ୟ ଯାଞ୍ଚ ସଫଳ ହେଲା) |",
        "igot_error": "IGOT_API_BASE_URL ସେଟ୍ ହୋଇଛି କିନ୍ତୁ ସ୍ୱାସ୍ଥ୍ୟ ଯାଞ୍ଚ ବିଫଳ ହୋଇଛି - ଏକ ମିଥ୍ୟା ଲାଇଭ୍ ସିଙ୍କ ରିପୋର୍ଟ କରିବା ପରିବର୍ତ୍ତେ ଅଫିସିଆଲ୍ ପବ୍ଲିକ୍ କାଟାଲଗ୍ କୁ ଖସିଯିବା |",
        "igot_fallback": "ଆଜି କ public ଣସି ସାର୍ବଜନୀନ iGOT କରମାୟୋଗୀ ଅଂଶୀଦାର API ବିଦ୍ୟମାନ ନାହିଁ | ସୁପାରିଶଗୁଡିକ ଏକ ଅନୁକରଣ କରାଯାଇଥିବା ନାମଲେଖା ରେକର୍ଡ ପରିବର୍ତ୍ତେ ସରକାରୀ ସାର୍ବଜନୀନ କାଟାଲଗ୍ ସହିତ ଲିଙ୍କ୍ |",
        "nssta_live": "ଲାଇଭ୍ NSSTA / TPAC ପ୍ରୋଗ୍ରାମ ଫିଡ୍ ଉପଲବ୍ଧ (ସ୍ୱାସ୍ଥ୍ୟ ଯାଞ୍ଚ ସଫଳ ହେଲା) |",
        "nssta_error": "NSSTA_API_BASE_URL ସେଟ୍ ହୋଇଛି କିନ୍ତୁ ସ୍ୱାସ୍ଥ୍ୟ ଯାଞ୍ଚ ବିଫଳ ହୋଇଛି - ଜୀବନ୍ତ ସିଙ୍କ ରିପୋର୍ଟ କରିବା ପରିବର୍ତ୍ତେ ପ୍ରକାଶିତ ତାଲିମ-କ୍ୟାଲେଣ୍ଡର ଡକ୍ୟୁମେଣ୍ଟକୁ ଫେରିବା |",
        "nssta_fallback": "ଆଜି କ public ଣସି ସାର୍ବଜନୀନ NSSTA / TPAC ପ୍ରୋଗ୍ରାମ API ବିଦ୍ୟମାନ ନାହିଁ | ଏହା ପରିବର୍ତ୍ତେ ପ୍ରକାଶିତ NSSTA ତାଲିମ-କ୍ୟାଲେଣ୍ଡର ଡକ୍ୟୁମେଣ୍ଟଗୁଡିକ ସହିତ ସୁପାରିଶ ଲିଙ୍କ୍ |",
    },
    "ml": {
        "igot_live": "തത്സമയ iGOT കർമ്മയോഗി API എത്തിച്ചേരാനാകും (ആരോഗ്യ പരിശോധന വിജയിച്ചു).",
        "igot_error": "IGOT_API_BASE_URL സജ്ജീകരിച്ചു, പക്ഷേ ആരോഗ്യ പരിശോധന പരാജയപ്പെട്ടു -- തെറ്റായ തത്സമയ സമന്വയം റിപ്പോർട്ടുചെയ്യുന്നതിന് പകരം ഔദ്യോഗിക പൊതു കാറ്റലോഗിലേക്ക് മടങ്ങുന്നു.",
        "igot_fallback": "പൊതു iGOT കർമ്മയോഗി പങ്കാളി API ഇന്ന് നിലവിലില്ല. ഒരു സിമുലേറ്റഡ് എൻറോൾമെൻ്റ് റെക്കോർഡിന് പകരം ഔദ്യോഗിക പൊതു കാറ്റലോഗിലേക്ക് ശുപാർശകൾ ലിങ്ക് ചെയ്യുന്നു.",
        "nssta_live": "തത്സമയ NSSTA/TPAC പ്രോഗ്രാം ഫീഡ് എത്തിച്ചേരാവുന്നതാണ് (ആരോഗ്യ പരിശോധന വിജയിച്ചു).",
        "nssta_error": "NSSTA_API_BASE_URL സജ്ജീകരിച്ചു, പക്ഷേ ആരോഗ്യ പരിശോധന പരാജയപ്പെട്ടു -- യഥാർത്ഥമല്ലാത്ത ഒരു തത്സമയ സമന്വയം റിപ്പോർട്ടുചെയ്യുന്നതിന് പകരം പ്രസിദ്ധീകരിച്ച പരിശീലന കലണ്ടർ ഡോക്യുമെൻ്റുകളിലേക്ക് മടങ്ങുന്നു.",
        "nssta_fallback": "പൊതു NSSTA/TPAC പ്രോഗ്രാം API ഇന്ന് നിലവിലില്ല. പകരം പ്രസിദ്ധീകരിച്ച NSSTA പരിശീലന കലണ്ടർ ഡോക്യുമെൻ്റുകളിലേക്ക് ശുപാർശകൾ ലിങ്ക് ചെയ്യുന്നു.",
    },
}

_PROVIDER_NAME = {
    "en": {"internal-practice": "Internal Practice", "igot": "iGOT Karmayogi", "nssta": "NSSTA / TPAC"},
    "hi": {"internal-practice": "आंतरिक अभ्यास", "igot": "iGOT कर्मयोगी", "nssta": "NSSTA / TPAC"},
    "bn": {"internal-practice": "অভ্যন্তরীণ অনুশীলন", "igot": "iGOT কর্মযোগী", "nssta": "NSSTA / TPAC"},
    "mr": {"internal-practice": "अंतर्गत सराव", "igot": "iGOT कर्मयोगी", "nssta": "NSSTA / TPAC"},
    "te": {"internal-practice": "అంతర్గత అభ్యాసం", "igot": "iGOT కర్మయోగి", "nssta": "NSSTA / TPAC"},
    "ta": {"internal-practice": "உள் பயிற்சி", "igot": "iGOT கர்மயோகி", "nssta": "NSSTA / TPAC"},
    "gu": {"internal-practice": "આંતરિક પ્રેક્ટિસ", "igot": "iGOT કર્મયોગી", "nssta": "NSSTA / TPAC"},
    "ur": {"internal-practice": "اندرونی مشق", "igot": "iGOT کرمایوگی", "nssta": "NSSTA / TPAC"},
    "kn": {"internal-practice": "ಆಂತರಿಕ ಅಭ್ಯಾಸ", "igot": "iGOT ಕರ್ಮಯೋಗಿ", "nssta": "NSSTA / TPAC"},
    "or": {"internal-practice": "ଆଭ୍ୟନ୍ତରୀଣ ଅଭ୍ୟାସ |", "igot": "iGOT କରମାୟୋଗୀ |", "nssta": "NSSTA / TPAC"},
    "ml": {"internal-practice": "ആന്തരിക പ്രാക്ടീസ്", "igot": "iGOT കർമ്മയോഗി", "nssta": "NSSTA / TPAC"},
}

_TITLE_TEMPLATE = {
    "en": {
        "internal-practice": "Adaptive practice: {label}",
        "igot": "Search iGOT Karmayogi for: {label}",
        "nssta": "Check the NSSTA training calendar for: {label}",
    },
    "hi": {
        "internal-practice": "अनुकूली अभ्यास: {label}",
        "igot": "iGOT कर्मयोगी में खोजें: {label}",
        "nssta": "NSSTA प्रशिक्षण कैलेंडर देखें: {label}",
    },
    "bn": {
        "internal-practice": "অভিযোজিত অনুশীলন: {label}",
        "igot": "এর জন্য iGOT কর্মযোগী অনুসন্ধান করুন: {label}৷",
        "nssta": "এর জন্য NSSTA প্রশিক্ষণ ক্যালেন্ডার দেখুন: {label}৷",
    },
    "mr": {
        "internal-practice": "अनुकूली सराव: {label}",
        "igot": "यासाठी iGOT कर्मयोगी शोधा: {label}",
        "nssta": "यासाठी NSSTA प्रशिक्षण दिनदर्शिका तपासा: {label}",
    },
    "te": {
        "internal-practice": "అనుకూల అభ్యాసం: {label}",
        "igot": "దీని కోసం iGOT కర్మయోగిని శోధించండి: {label}",
        "nssta": "దీని కోసం NSSTA శిక్షణ క్యాలెండర్‌ను తనిఖీ చేయండి: {label}",
    },
    "ta": {
        "internal-practice": "தழுவல் நடைமுறை: {label}",
        "igot": "iGOT Karmayogi ஐ தேடவும்: {label}",
        "nssta": "NSSTA பயிற்சி காலெண்டரைச் சரிபார்க்கவும்: {label}",
    },
    "gu": {
        "internal-practice": "અનુકૂલનશીલ પ્રેક્ટિસ: {label}",
        "igot": "આ માટે iGOT કર્મયોગી શોધો: {label}",
        "nssta": "આ માટે NSSTA તાલીમ કેલેન્ડર તપાસો: {label}",
    },
    "ur": {
        "internal-practice": "انکولی مشق: {label}",
        "igot": "iGOT Karmayogi کو تلاش کریں: {label}",
        "nssta": "{label} کے لیے NSSTA ٹریننگ کیلنڈر چیک کریں۔",
    },
    "kn": {
        "internal-practice": "ಅಡಾಪ್ಟಿವ್ ಅಭ್ಯಾಸ: {label}",
        "igot": "ಇದಕ್ಕಾಗಿ iGOT ಕರ್ಮಯೋಗಿಯನ್ನು ಹುಡುಕಿ: {label}",
        "nssta": "ಇದಕ್ಕಾಗಿ NSSTA ತರಬೇತಿ ಕ್ಯಾಲೆಂಡರ್ ಅನ್ನು ಪರಿಶೀಲಿಸಿ: {label}",
    },
    "or": {
        "internal-practice": "ଆଡାପ୍ଟିଭ୍ ଅଭ୍ୟାସ: {label} |",
        "igot": "{label} ପାଇଁ iGOT କରମାୟୋଗୀ ସନ୍ଧାନ କରନ୍ତୁ |",
        "nssta": "NSSTA ତାଲିମ କ୍ୟାଲେଣ୍ଡର ଯାଞ୍ଚ କରନ୍ତୁ: {label} |",
    },
    "ml": {
        "internal-practice": "അഡാപ്റ്റീവ് പ്രാക്ടീസ്: {label}",
        "igot": "ഇതിനായി iGOT Karmayogi തിരയുക: {label}",
        "nssta": "ഇതിനായി NSSTA പരിശീലന കലണ്ടർ പരിശോധിക്കുക: {label}",
    },
}

_INTERNAL_PRACTICE_NOTE = {
    "en": "Generated on demand by this app's own adaptive question engine.",
    "hi": "इस ऐप के अपने अनुकूली प्रश्न इंजन द्वारा मांग पर उत्पन्न।",
    "bn": "এই অ্যাপের নিজস্ব অভিযোজিত প্রশ্ন ইঞ্জিনের চাহিদা অনুযায়ী তৈরি করা হয়েছে।",
    "mr": "या ॲपच्या स्वतःच्या अडॅप्टिव्ह प्रश्न इंजिनद्वारे मागणीनुसार व्युत्पन्न केले.",
    "te": "ఈ యాప్ యొక్క స్వంత అడాప్టివ్ క్వశ్చన్ ఇంజిన్ ద్వారా డిమాండ్‌పై రూపొందించబడింది.",
    "ta": "இந்த பயன்பாட்டின் சொந்த அடாப்டிவ் கேள்வி இயந்திரத்தால் தேவைக்கேற்ப உருவாக்கப்பட்டது.",
    "gu": "આ એપ્લિકેશનના પોતાના અનુકૂલનશીલ પ્રશ્ન એન્જિન દ્વારા માંગ પર જનરેટ કરવામાં આવે છે.",
    "ur": "اس ایپ کے اپنے انکولی سوال انجن کے ذریعہ مانگ پر تیار کیا گیا ہے۔",
    "kn": "ಈ ಅಪ್ಲಿಕೇಶನ್‌ನ ಸ್ವಂತ ಹೊಂದಾಣಿಕೆಯ ಪ್ರಶ್ನೆ ಎಂಜಿನ್‌ನಿಂದ ಬೇಡಿಕೆಯ ಮೇರೆಗೆ ರಚಿಸಲಾಗಿದೆ.",
    "or": "ଏହି ଆପର ନିଜସ୍ୱ ଆଡାପ୍ଟିଭ୍ ପ୍ରଶ୍ନ ଇଞ୍ଜିନ୍ ଦ୍ୱାରା ଚାହିଦା ଅନୁଯାୟୀ ଉତ୍ପନ୍ନ |",
    "ml": "ഈ ആപ്പിൻ്റെ സ്വന്തം അഡാപ്റ്റീവ് ക്വസ്റ്റ്യൻ എഞ്ചിൻ വഴി ആവശ്യാനുസരണം സൃഷ്ടിച്ചത്.",
}


def _provider_status(env_var: str, detail: dict, live_key: str, error_key: str, fallback_key: str) -> dict:
    base_url = os.getenv(env_var)
    if not base_url:
        return {"mode": "CATALOGUE", "detail": detail[fallback_key]}
    result = LiveHTTPProviderAdapter(base_url).health_check()
    if result.status == "LIVE":
        return {"mode": "LIVE", "detail": detail[live_key]}
    return {"mode": "CATALOGUE", "detail": detail[error_key]}


def integration_status(lang: str = "en") -> dict:
    """Report each provider's real status -- never `LIVE` from an env var's
    mere presence (docs/contracts/provider-adapter.md's own rule). Setting
    `IGOT_API_BASE_URL`/`NSSTA_API_BASE_URL` selects a real
    `LiveHTTPProviderAdapter` and this function reports whatever its
    `health_check()` actually returns; unset (today's default -- no approved
    endpoint contract exists yet) reports `CATALOGUE`, same as a configured
    but unreachable URL."""
    detail = _DETAIL.get(lang, _DETAIL["en"])
    return {
        "igot": _provider_status("IGOT_API_BASE_URL", detail, "igot_live", "igot_error", "igot_fallback"),
        "nssta": _provider_status("NSSTA_API_BASE_URL", detail, "nssta_live", "nssta_error", "nssta_fallback"),
    }


# SimulatedIGOTAdapter is exercised directly by tests/test_api_integration_lane5.py's
# contract tests (search_catalogue/get_course/request_enrolment/import_completions/
# health_check/reconcile all report status="SIMULATED"). Re-exported here so a
# caller that already imports this module for IGOT/NSSTA status doesn't need a
# second import path just to construct one for a demo-mode code path.
__all__ = [
    "IGOT_CATALOG_URL",
    "NSSTA_CATALOG_URL",
    "IGOT_CONFIGURED",
    "NSSTA_CONFIGURED",
    "SimulatedIGOTAdapter",
    "integration_status",
    "recommend_courses",
]


def recommend_courses(skill_gaps: list[dict], lang: str = "en") -> list[dict]:
    """Return provider-tagged recommendations for the given gaps.

    Every gap gets one internal-practice entry (this app's own adaptive
    quest, always real and clickable) plus one iGOT and one NSSTA
    catalog-fallback entry. Capped at the 5 highest-priority gaps so the
    list stays scannable; skill_gaps is expected pre-sorted by severity
    (see learning_engine.analyse_competencies).
    """
    status = integration_status(lang)
    provider_name = _PROVIDER_NAME.get(lang, _PROVIDER_NAME["en"])
    title_template = _TITLE_TEMPLATE.get(lang, _TITLE_TEMPLATE["en"])
    courses: list[dict] = []
    for gap in skill_gaps[:5]:
        competency_id = gap["competency_id"]
        label = gap["label"]
        relevance = round(min(5.0, gap.get("gap", 0.0) + 1.0), 2)

        courses.append({
            "course_id": f"practice::{competency_id}",
            "provider": provider_name["internal-practice"],
            "provider_type": "internal-practice",
            "title": title_template["internal-practice"].format(label=label),
            "url": f"/dungeon#{competency_id}",
            "relevance_score": relevance,
            "verification_note": _INTERNAL_PRACTICE_NOTE.get(lang, _INTERNAL_PRACTICE_NOTE["en"]),
        })
        courses.append({
            "course_id": f"igot::{competency_id}",
            "provider": provider_name["igot"],
            "provider_type": "igot",
            "title": title_template["igot"].format(label=label),
            "url": IGOT_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["igot"]["detail"],
        })
        courses.append({
            "course_id": f"nssta::{competency_id}",
            "provider": provider_name["nssta"],
            "provider_type": "nssta",
            "title": title_template["nssta"].format(label=label),
            "url": NSSTA_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["nssta"]["detail"],
        })
    return courses

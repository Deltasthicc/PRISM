"""Deterministic, explainable competency-gap and pathway calculation."""

from services.behavioral_anchors import DEFAULT_SOURCE, DEFAULT_STATUS, get_anchor
from services.curricula import get_curriculum
from services.learning_catalog import recommend_courses
from services.role_targets import FRAMEWORK_VERSION, experience_cap, resolve_role_target

# Versions the 65/35 blend itself (CLAUDE.md architectural invariant #4: "the
# 65/35 blend ... remain versioned prototype policies until validated").
# Distinct from role_targets.FRAMEWORK_VERSION, which versions target
# selection -- these are two independently-changeable policies.
ASSESSMENT_POLICY_VERSION = "prototype-v1"

# The one documented status term that applies to a Lane 3 competency result
# (CODEX.md architectural invariants: use SIMULATED, CATALOGUE, LIVE,
# PROVISIONAL and NO EVIDENCE "precisely"; docs/internal/SIH26101_TEAM_ORCHESTRATION.md
# section 5 has Lane 1 render exactly these). The vocabulary defines no
# positive counterpart, so evidence_state is this string or None -- the
# present case is described by evidence_sources instead of an invented term.
NO_EVIDENCE = "NO EVIDENCE"

# Evidence types this engine understands, in Lane 2's storage vocabulary
# (models/governance.py's EVIDENCE_TYPES). Ordered strongest-corroboration
# first purely for stable display; the order is NOT a weighting.
EVIDENCE_TYPE_ORDER = (
    "reviewer",
    "diagnostic",
    "observed_practice",
    "provider_imported",
    "self_report",
)

# Only these two contribute to observed_level, at the 65/35 weights this
# policy version has always used. docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 5
# asks Lane 3 to *separate* the five evidence types -- not to blend them --
# and no validated weights exist for the other three, so they are recorded,
# separated and displayed while deliberately not moving the score. Giving
# them invented weights would be exactly the fabricated psychometric
# precision CLAUDE.md invariant #4 forbids, and would require a contract
# version bump plus approval under competency-evidence.md section 10.
SCORING_EVIDENCE_TYPES = ("observed_practice", "self_report")

# Types recorded for transparency but not yet scored. Weighting them needs
# domain-reviewer-validated weights, which SIH26101_MASTER_CHECKLIST.md
# section 4.1 marks BLOCKED-EXTERNAL.
UNSCORED_EVIDENCE_TYPES = ("reviewer", "diagnostic", "provider_imported")

# Qualitative uncertainty band -- SIH26101_MASTER_CHECKLIST.md section 4.1:
# "Display evidence coverage and uncertainty." Deliberately qualitative: a
# numeric confidence interval would imply psychometric validation this policy
# does not have (CLAUDE.md invariant #4). "high" is intentionally unreachable
# until a validated instrument exists -- do not add it without one.
def _confidence(evidence_sources: list[str]) -> str:
    if not evidence_sources:
        return "none"
    if set(evidence_sources) == {"self_report"}:
        return "low"
    return "moderate"


# Bounded, hand-translated template strings for this engine's own generated
# prose (never AI output -- these are plain Python f-strings). Curriculum
# label/description translation lives in services/curricula.py's
# curricula_hi.json instead, since it's a different, much larger dataset with
# its own review process.
_LEVEL_LABEL = {
    "en": {
        "not_yet_evidenced": "not yet evidenced",
        "foundation": "foundation",
        "working_knowledge": "working knowledge",
        "practitioner": "practitioner",
        "advanced": "advanced",
        "expert": "expert",
    },
    "hi": {
        "not_yet_evidenced": "अभी तक कोई प्रमाण नहीं",
        "foundation": "आधारभूत",
        "working_knowledge": "कार्यसाधक ज्ञान",
        "practitioner": "अभ्यासी",
        "advanced": "उन्नत",
        "expert": "विशेषज्ञ",
    },
    "bn": {
        "not_yet_evidenced": "এখনো প্রমাণিত হয়নি",
        "foundation": "ভিত্তি",
        "working_knowledge": "কাজের জ্ঞান",
        "practitioner": "অনুশীলনকারী",
        "advanced": "উন্নত",
        "expert": "বিশেষজ্ঞ",
    },
    "mr": {
        "not_yet_evidenced": "अद्याप पुरावा नाही",
        "foundation": "पाया",
        "working_knowledge": "कार्यरत ज्ञान",
        "practitioner": "व्यवसायी",
        "advanced": "प्रगत",
        "expert": "तज्ञ",
    },
    "te": {
        "not_yet_evidenced": "ఇంకా రుజువు కాలేదు",
        "foundation": "పునాది",
        "working_knowledge": "పని జ్ఞానం",
        "practitioner": "అభ్యాసకుడు",
        "advanced": "అభివృద్ధి చెందింది",
        "expert": "నిపుణుడు",
    },
    "ta": {
        "not_yet_evidenced": "இன்னும் ஆதாரம் இல்லை",
        "foundation": "அடித்தளம்",
        "working_knowledge": "வேலை அறிவு",
        "practitioner": "பயிற்சியாளர்",
        "advanced": "முன்னேறியது",
        "expert": "நிபுணர்",
    },
    "gu": {
        "not_yet_evidenced": "હજુ પુરાવા નથી",
        "foundation": "પાયો",
        "working_knowledge": "કાર્યકારી જ્ઞાન",
        "practitioner": "વ્યવસાયી",
        "advanced": "અદ્યતન",
        "expert": "નિષ્ણાત",
    },
    "ur": {
        "not_yet_evidenced": "ابھی تک ثبوت نہیں ہے",
        "foundation": "بنیاد",
        "working_knowledge": "کام کرنے کا علم",
        "practitioner": "پریکٹیشنر",
        "advanced": "ترقی یافتہ",
        "expert": "ماہر",
    },
    "kn": {
        "not_yet_evidenced": "ಇನ್ನೂ ಸಾಕ್ಷಿಯಾಗಿಲ್ಲ",
        "foundation": "ಅಡಿಪಾಯ",
        "working_knowledge": "ಕೆಲಸದ ಜ್ಞಾನ",
        "practitioner": "ಅಭ್ಯಾಸಿ",
        "advanced": "ಮುಂದುವರಿದ",
        "expert": "ತಜ್ಞ",
    },
    "or": {
        "not_yet_evidenced": "ଏପର୍ଯ୍ୟନ୍ତ ପ୍ରମାଣିତ ହୋଇନାହିଁ |",
        "foundation": "ଭିତ୍ତିପ୍ରସ୍ତର",
        "working_knowledge": "କାର୍ଯ୍ୟ ଜ୍ଞାନ",
        "practitioner": "ଅଭ୍ୟାସକାରୀ",
        "advanced": "ଉନ୍ନତ",
        "expert": "ବିଶେଷଜ୍ଞ",
    },
    "ml": {
        "not_yet_evidenced": "ഇതുവരെ തെളിവായിട്ടില്ല",
        "foundation": "അടിസ്ഥാനം",
        "working_knowledge": "ജോലി അറിവ്",
        "practitioner": "പ്രാക്ടീഷണർ",
        "advanced": "മുന്നേറി",
        "expert": "വിദഗ്ധൻ",
    },
}

_EVIDENCE_TYPE_LABEL = {
    "en": {
        "reviewer": "reviewer",
        "diagnostic": "diagnostic",
        "observed_practice": "observed practice",
        "provider_imported": "provider-imported",
        "self_report": "self-report",
    },
    "hi": {
        "reviewer": "समीक्षक",
        "diagnostic": "निदान",
        "observed_practice": "देखा गया अभ्यास",
        "provider_imported": "प्रदाता-आयातित",
        "self_report": "स्व-रिपोर्ट",
    },
    "bn": {
        "reviewer": "পর্যালোচক",
        "diagnostic": "ডায়গনিস্টিক",
        "observed_practice": "পর্যবেক্ষণ করা অনুশীলন",
        "provider_imported": "সরবরাহকারী-আমদানি করা",
        "self_report": "স্ব-প্রতিবেদন",
    },
    "mr": {
        "reviewer": "समीक्षक",
        "diagnostic": "निदान",
        "observed_practice": "निरीक्षण सराव",
        "provider_imported": "प्रदाता-आयात",
        "self_report": "स्वत:चा अहवाल",
    },
    "te": {
        "reviewer": "సమీక్షకుడు",
        "diagnostic": "రోగనిర్ధారణ",
        "observed_practice": "ఆచరణను గమనించారు",
        "provider_imported": "ప్రొవైడర్-దిగుమతి",
        "self_report": "స్వీయ నివేదిక",
    },
    "ta": {
        "reviewer": "விமர்சகர்",
        "diagnostic": "நோய் கண்டறிதல்",
        "observed_practice": "கடைபிடிக்கப்பட்ட நடைமுறை",
        "provider_imported": "வழங்குபவர்-இறக்குமதி",
        "self_report": "சுய அறிக்கை",
    },
    "gu": {
        "reviewer": "સમીક્ષક",
        "diagnostic": "ડાયગ્નોસ્ટિક",
        "observed_practice": "અવલોકન પ્રેક્ટિસ",
        "provider_imported": "પ્રદાતા દ્વારા આયાત કરેલ",
        "self_report": "સ્વ-અહેવાલ",
    },
    "ur": {
        "reviewer": "جائزہ لینے والا",
        "diagnostic": "تشخیصی",
        "observed_practice": "مشاہدہ مشق",
        "provider_imported": "فراہم کنندہ سے درآمد شدہ",
        "self_report": "خود رپورٹ",
    },
    "kn": {
        "reviewer": "ವಿಮರ್ಶಕ",
        "diagnostic": "ರೋಗನಿರ್ಣಯ",
        "observed_practice": "ಅಭ್ಯಾಸವನ್ನು ಗಮನಿಸಿದರು",
        "provider_imported": "ಒದಗಿಸುವವರು-ಆಮದು ಮಾಡಿಕೊಂಡಿದ್ದಾರೆ",
        "self_report": "ಸ್ವಯಂ ವರದಿ",
    },
    "or": {
        "reviewer": "ସମୀକ୍ଷକ",
        "diagnostic": "ନିଦାନ",
        "observed_practice": "ପାଳନ ଅଭ୍ୟାସ |",
        "provider_imported": "ପ୍ରଦାନକାରୀ-ଆମଦାନୀ |",
        "self_report": "ଆତ୍ମ ରିପୋର୍ଟ",
    },
    "ml": {
        "reviewer": "നിരൂപകൻ",
        "diagnostic": "രോഗനിർണയം",
        "observed_practice": "നിരീക്ഷിച്ച പ്രാക്ടീസ്",
        "provider_imported": "ദാതാവ്-ഇറക്കുമതി ചെയ്തത്",
        "self_report": "സ്വയം റിപ്പോർട്ട്",
    },
}

_EVIDENCE_SENTENCE = {
    "en": {
        "both": "65% demonstrated performance + 35% self-assessment",
        "measured_only": "demonstrated performance",
        "self_only": "self-assessment only; diagnostic evidence still required",
        "unscored": "{types} evidence recorded but not scored under policy {version}; no rated evidence yet",
        "none": "no evidence yet",
    },
    "hi": {
        "both": "65% प्रदर्शित प्रदर्शन + 35% स्व-मूल्यांकन",
        "measured_only": "प्रदर्शित प्रदर्शन",
        "self_only": "केवल स्व-मूल्यांकन; अभी भी निदान प्रमाण आवश्यक है",
        "unscored": "{types} प्रमाण दर्ज है लेकिन नीति {version} के तहत स्कोर नहीं किया गया; अभी कोई रेटेड प्रमाण नहीं",
        "none": "अभी तक कोई प्रमाण नहीं",
    },
    "bn": {
        "both": "65% প্রদর্শিত কর্মক্ষমতা + 35% স্ব-মূল্যায়ন",
        "measured_only": "কর্মক্ষমতা প্রদর্শন",
        "self_only": "শুধুমাত্র স্ব-মূল্যায়ন; ডায়গনিস্টিক প্রমাণ এখনও প্রয়োজন",
        "unscored": "{types} প্রমাণ রেকর্ড করা হয়েছে কিন্তু {version} নীতির অধীনে স্কোর করা হয়নি; কোন রেট প্রমাণ এখনও",
        "none": "এখনও কোন প্রমাণ",
    },
    "mr": {
        "both": "65% प्रात्यक्षिक कामगिरी + 35% स्व-मूल्यांकन",
        "measured_only": "कामगिरी दाखवली",
        "self_only": "केवळ स्व-मूल्यांकन; निदान पुरावे अद्याप आवश्यक आहेत",
        "unscored": "{types} पुरावा रेकॉर्ड केला आहे परंतु पॉलिसी {version} अंतर्गत स्कोअर केलेला नाही; अद्याप कोणतेही रेट केलेले पुरावे नाहीत",
        "none": "अद्याप पुरावा नाही",
    },
    "te": {
        "both": "65% పనితీరును ప్రదర్శించారు + 35% స్వీయ-అంచనా",
        "measured_only": "పనితీరును ప్రదర్శించారు",
        "self_only": "స్వీయ-అంచనా మాత్రమే; రోగనిర్ధారణ సాక్ష్యం ఇంకా అవసరం",
        "unscored": "{types} సాక్ష్యం రికార్డ్ చేయబడింది కానీ విధానం {version} కింద స్కోర్ చేయలేదు; ఇంకా రేట్ చేయబడిన సాక్ష్యం లేదు",
        "none": "ఇంకా ఆధారాలు లేవు",
    },
    "ta": {
        "both": "65% செயல்திறன் + 35% சுய மதிப்பீடு",
        "measured_only": "செயல்திறனை வெளிப்படுத்தினார்",
        "self_only": "சுய மதிப்பீடு மட்டுமே; கண்டறியும் சான்றுகள் இன்னும் தேவை",
        "unscored": "{version} கொள்கையின் கீழ் {types} சான்றுகள் பதிவு செய்யப்பட்டன ஆனால் மதிப்பெண் பெறவில்லை; இன்னும் மதிப்பிடப்பட்ட சான்றுகள் இல்லை",
        "none": "இன்னும் ஆதாரம் இல்லை",
    },
    "gu": {
        "both": "65% પ્રદર્શન પ્રદર્શન + 35% સ્વ-મૂલ્યાંકન",
        "measured_only": "પ્રદર્શન દર્શાવ્યું",
        "self_only": "માત્ર સ્વ-મૂલ્યાંકન; ડાયગ્નોસ્ટિક પુરાવા હજુ પણ જરૂરી છે",
        "unscored": "{types} પુરાવા રેકોર્ડ કર્યા છે પરંતુ {version} નીતિ હેઠળ સ્કોર કર્યા નથી; હજુ સુધી કોઈ રેટેડ પુરાવા નથી",
        "none": "હજુ સુધી કોઈ પુરાવા નથી",
    },
    "ur": {
        "both": "65% نے کارکردگی کا مظاہرہ کیا + 35% خود تشخیص",
        "measured_only": "کارکردگی کا مظاہرہ کیا",
        "self_only": "صرف خود تشخیص؛ تشخیصی ثبوت اب بھی درکار ہیں۔",
        "unscored": "{types} ثبوت ریکارڈ کیے گئے لیکن پالیسی {version} کے تحت اسکور نہیں کیے گئے؛ ابھی تک کوئی درجہ بندی کا ثبوت نہیں ہے۔",
        "none": "ابھی تک کوئی ثبوت نہیں",
    },
    "kn": {
        "both": "65% ಪ್ರದರ್ಶನ + 35% ಸ್ವಯಂ ಮೌಲ್ಯಮಾಪನ",
        "measured_only": "ಕಾರ್ಯಕ್ಷಮತೆಯನ್ನು ಪ್ರದರ್ಶಿಸಿದರು",
        "self_only": "ಸ್ವಯಂ ಮೌಲ್ಯಮಾಪನ ಮಾತ್ರ; ರೋಗನಿರ್ಣಯದ ಪುರಾವೆಗಳು ಇನ್ನೂ ಅಗತ್ಯವಿದೆ",
        "unscored": "{types} ಸಾಕ್ಷ್ಯವನ್ನು ದಾಖಲಿಸಲಾಗಿದೆ ಆದರೆ {version} ನೀತಿ ಅಡಿಯಲ್ಲಿ ಸ್ಕೋರ್ ಮಾಡಲಾಗಿಲ್ಲ; ಇನ್ನೂ ರೇಟ್ ಮಾಡಲಾದ ಪುರಾವೆಗಳಿಲ್ಲ",
        "none": "ಇನ್ನೂ ಯಾವುದೇ ಪುರಾವೆಗಳಿಲ್ಲ",
    },
    "or": {
        "both": "65% ପ୍ରଦର୍ଶନ ପ୍ରଦର୍ଶନ + 35% ଆତ୍ମ-ମୂଲ୍ୟାଙ୍କନ ପ୍ରଦର୍ଶନ କରିଛି |",
        "measured_only": "ପ୍ରଦର୍ଶନ ପ୍ରଦର୍ଶନ",
        "self_only": "କେବଳ ଆତ୍ମ-ମୂଲ୍ୟାଙ୍କନ; ନିଦାନ ପ୍ରମାଣ ତଥାପି ଆବଶ୍ୟକ |",
        "unscored": "{types} ପ୍ରମାଣ ରେକର୍ଡ ହୋଇଛି କିନ୍ତୁ {version} ନୀତି ଅନୁଯାୟୀ ସ୍କୋର କରାଯାଇ ନାହିଁ; ଏପର୍ଯ୍ୟନ୍ତ କ rated ଣସି ମୂଲ୍ୟାୟନ ପ୍ରମାଣ ନାହିଁ |",
        "none": "ଏପର୍ଯ୍ୟନ୍ତ କ evidence ଣସି ପ୍ରମାଣ ନାହିଁ |",
    },
    "ml": {
        "both": "65% പ്രകടനം പ്രകടനം + 35% സ്വയം വിലയിരുത്തൽ",
        "measured_only": "പ്രകടനം നടത്തി",
        "self_only": "സ്വയം വിലയിരുത്തൽ മാത്രം; ഡയഗ്നോസ്റ്റിക് തെളിവുകൾ ഇപ്പോഴും ആവശ്യമാണ്",
        "unscored": "{version} എന്ന നയത്തിന് കീഴിൽ {types} തെളിവുകൾ രേഖപ്പെടുത്തിയിട്ടുണ്ടെങ്കിലും സ്‌കോർ ചെയ്തിട്ടില്ല; ഇതുവരെ റേറ്റുചെയ്ത തെളിവുകളൊന്നുമില്ല",
        "none": "ഇതുവരെ തെളിവില്ല",
    },
}

_RECOMMENDED_ACTION = {
    "en": {
        "unassessed": "Complete a diagnostic to establish a baseline -- no evidence recorded yet",
        "foundation": "Complete a diagnostic and foundation module",
        "targeted": "Complete targeted learning, then re-assess with applied questions",
    },
    "hi": {
        "unassessed": "आधाररेखा स्थापित करने के लिए एक निदान पूरा करें -- अभी तक कोई प्रमाण दर्ज नहीं है",
        "foundation": "एक निदान और आधारभूत मॉड्यूल पूरा करें",
        "targeted": "लक्षित शिक्षण पूरा करें, फिर लागू प्रश्नों के साथ पुनः मूल्यांकन करें",
    },
    "bn": {
        "unassessed": "একটি বেসলাইন স্থাপন করার জন্য একটি ডায়াগনস্টিক সম্পূর্ণ করুন -- এখনো কোনো প্রমাণ রেকর্ড করা হয়নি",
        "foundation": "একটি ডায়াগনস্টিক এবং ফাউন্ডেশন মডিউল সম্পূর্ণ করুন",
        "targeted": "টার্গেটেড লার্নিং সম্পূর্ণ করুন, তারপর ফলিত প্রশ্ন দিয়ে পুনরায় মূল্যায়ন করুন",
    },
    "mr": {
        "unassessed": "बेसलाइन स्थापित करण्यासाठी निदान पूर्ण करा -- अद्याप कोणताही पुरावा रेकॉर्ड केलेला नाही",
        "foundation": "डायग्नोस्टिक आणि फाउंडेशन मॉड्यूल पूर्ण करा",
        "targeted": "लक्ष्यित शिक्षण पूर्ण करा, नंतर लागू केलेल्या प्रश्नांसह पुन्हा मूल्यांकन करा",
    },
    "te": {
        "unassessed": "బేస్‌లైన్‌ను ఏర్పాటు చేయడానికి డయాగ్నస్టిక్‌ను పూర్తి చేయండి -- ఇంకా ఎటువంటి సాక్ష్యం నమోదు చేయబడలేదు",
        "foundation": "డయాగ్నస్టిక్ మరియు ఫౌండేషన్ మాడ్యూల్‌ను పూర్తి చేయండి",
        "targeted": "లక్ష్య అభ్యాసాన్ని పూర్తి చేయండి, ఆపై అనువర్తిత ప్రశ్నలతో మళ్లీ అంచనా వేయండి",
    },
    "ta": {
        "unassessed": "ஒரு அடிப்படையை நிறுவுவதற்கு ஒரு கண்டறிதலை முடிக்கவும் -- இதுவரை எந்த ஆதாரமும் பதிவு செய்யப்படவில்லை",
        "foundation": "நோயறிதல் மற்றும் அடித்தள தொகுதியை முடிக்கவும்",
        "targeted": "இலக்குக் கற்றலை முடிக்கவும், பின்னர் பயன்படுத்தப்பட்ட கேள்விகளுடன் மறு மதிப்பீடு செய்யவும்",
    },
    "gu": {
        "unassessed": "આધારરેખા સ્થાપિત કરવા માટે ડાયગ્નોસ્ટિક પૂર્ણ કરો -- હજુ સુધી કોઈ પુરાવા નોંધાયા નથી",
        "foundation": "ડાયગ્નોસ્ટિક અને ફાઉન્ડેશન મોડ્યુલ પૂર્ણ કરો",
        "targeted": "લક્ષિત શિક્ષણ પૂર્ણ કરો, પછી લાગુ પ્રશ્નો સાથે ફરીથી મૂલ્યાંકન કરો",
    },
    "ur": {
        "unassessed": "بیس لائن قائم کرنے کے لیے ایک تشخیصی مکمل کریں -- ابھی تک کوئی ثبوت ریکارڈ نہیں کیا گیا ہے۔",
        "foundation": "ایک تشخیصی اور فاؤنڈیشن ماڈیول مکمل کریں۔",
        "targeted": "ٹارگٹڈ سیکھنے کو مکمل کریں، پھر لاگو کردہ سوالات کے ساتھ دوبارہ جائزہ لیں۔",
    },
    "kn": {
        "unassessed": "ಬೇಸ್‌ಲೈನ್ ಅನ್ನು ಸ್ಥಾಪಿಸಲು ರೋಗನಿರ್ಣಯವನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ -- ಇನ್ನೂ ಯಾವುದೇ ಪುರಾವೆಗಳನ್ನು ದಾಖಲಿಸಲಾಗಿಲ್ಲ",
        "foundation": "ರೋಗನಿರ್ಣಯ ಮತ್ತು ಅಡಿಪಾಯ ಮಾಡ್ಯೂಲ್ ಅನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ",
        "targeted": "ಉದ್ದೇಶಿತ ಕಲಿಕೆಯನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ, ನಂತರ ಅನ್ವಯಿಕ ಪ್ರಶ್ನೆಗಳೊಂದಿಗೆ ಮರು-ಮೌಲ್ಯಮಾಪನ ಮಾಡಿ",
    },
    "or": {
        "unassessed": "ଏକ ବେସ୍ ଲାଇନ୍ ପ୍ରତିଷ୍ଠା କରିବାକୁ ଏକ ଡାଇଗ୍ନୋଷ୍ଟିକ୍ ସଂପୂର୍ଣ୍ଣ କରନ୍ତୁ - ଏପର୍ଯ୍ୟନ୍ତ କ evidence ଣସି ପ୍ରମାଣ ଲିପିବଦ୍ଧ ହୋଇନାହିଁ |",
        "foundation": "ଏକ ଡାଇଗ୍ନୋଷ୍ଟିକ୍ ଏବଂ ଫାଉଣ୍ଡେସନ୍ ମଡ୍ୟୁଲ୍ ସଂପୂର୍ଣ୍ଣ କରନ୍ତୁ |",
        "targeted": "ସଂପୂର୍ଣ୍ଣ ଲକ୍ଷ୍ୟ ଧାର୍ଯ୍ୟ ଶିକ୍ଷା, ତାପରେ ପ୍ରୟୋଗ ହୋଇଥିବା ପ୍ରଶ୍ନଗୁଡ଼ିକ ସହିତ ପୁନ assess ମୂଲ୍ୟାଙ୍କନ କର |",
    },
    "ml": {
        "unassessed": "അടിസ്ഥാനരേഖ സ്ഥാപിക്കാൻ ഒരു ഡയഗ്നോസ്റ്റിക് പൂർത്തിയാക്കുക -- ഇതുവരെ തെളിവുകളൊന്നും രേഖപ്പെടുത്തിയിട്ടില്ല",
        "foundation": "ഒരു ഡയഗ്നോസ്റ്റിക്, ഫൗണ്ടേഷൻ മൊഡ്യൂൾ പൂർത്തിയാക്കുക",
        "targeted": "ടാർഗെറ്റുചെയ്‌ത പഠനം പൂർത്തിയാക്കുക, തുടർന്ന് പ്രയോഗിച്ച ചോദ്യങ്ങൾ ഉപയോഗിച്ച് വീണ്ടും വിലയിരുത്തുക",
    },
}

_METHOD_NOTE = {
    "en": "Self-ratings never override demonstrated performance; missing evidence is surfaced explicitly.",
    "hi": "स्व-रेटिंग कभी भी प्रदर्शित प्रदर्शन को अधिलेखित नहीं करती; अनुपस्थित प्रमाण को स्पष्ट रूप से दिखाया जाता है।",
    "bn": "স্ব-রেটিং কখনই প্রদর্শিত কর্মক্ষমতাকে অগ্রাহ্য করে না; অনুপস্থিত প্রমাণ স্পষ্টভাবে প্রদর্শিত হয়.",
    "mr": "स्व-रेटिंग कधीही प्रात्यक्षिक कामगिरी ओव्हरराइड करत नाही; गहाळ पुरावे स्पष्टपणे समोर आले आहेत.",
    "te": "స్వీయ-రేటింగ్‌లు ప్రదర్శించిన పనితీరును ఎప్పుడూ భర్తీ చేయవు; తప్పిపోయిన సాక్ష్యం స్పష్టంగా బయటపడింది.",
    "ta": "சுய மதிப்பீடுகள் ஒருபோதும் நிரூபிக்கப்பட்ட செயல்திறனை மீறுவதில்லை; காணாமல் போன சான்றுகள் வெளிப்படையாக வெளிப்படுகின்றன.",
    "gu": "સ્વ-રેટિંગ્સ ક્યારેય પ્રદર્શિત પ્રદર્શનને ઓવરરાઇડ કરતા નથી; ખૂટતા પુરાવા સ્પષ્ટપણે સામે આવ્યા છે.",
    "ur": "خود کی درجہ بندی کبھی بھی مظاہرے کی کارکردگی کو اوور رائیڈ نہیں کرتی۔ لاپتہ ثبوت واضح طور پر سامنے آئے ہیں۔",
    "kn": "ಸ್ವಯಂ-ರೇಟಿಂಗ್‌ಗಳು ಎಂದಿಗೂ ಪ್ರದರ್ಶಿಸಿದ ಕಾರ್ಯಕ್ಷಮತೆಯನ್ನು ಅತಿಕ್ರಮಿಸುವುದಿಲ್ಲ; ಕಾಣೆಯಾದ ಪುರಾವೆಗಳು ಸ್ಪಷ್ಟವಾಗಿ ಗೋಚರಿಸುತ್ತವೆ.",
    "or": "ଆତ୍ମ-ମୂଲ୍ୟାୟନ କଦାପି ପ୍ରଦର୍ଶନ ପ୍ରଦର୍ଶନକୁ ଅତିକ୍ରମ କରେ ନାହିଁ; ନିଖୋଜ ପ୍ରମାଣ ସ୍ପଷ୍ଟ ଭାବରେ ସାମ୍ନାକୁ ଆସିଛି |",
    "ml": "സ്വയം റേറ്റിംഗുകൾ ഒരിക്കലും പ്രകടമായ പ്രകടനത്തെ മറികടക്കുന്നില്ല; കാണാതായ തെളിവുകൾ വ്യക്തമായി പുറത്തുവന്നിട്ടുണ്ട്.",
}


def _level_label(score: float, lang: str = "en") -> str:
    labels = _LEVEL_LABEL.get(lang, _LEVEL_LABEL["en"])
    if score < 1.0:
        return labels["not_yet_evidenced"]
    if score < 2.0:
        return labels["foundation"]
    if score < 3.0:
        return labels["working_knowledge"]
    if score < 4.0:
        return labels["practitioner"]
    if score < 4.75:
        return labels["advanced"]
    return labels["expert"]


def analyse_competencies(
    curriculum_slug: str,
    self_ratings: dict[str, float],
    measured_scores: dict[str, float],
    experience_level: str = "beginner",
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
    evidence: dict[str, dict[str, dict]] | None = None,
    role_targets: dict[str, dict] | None = None,
    lang: str = "en",
) -> dict:
    """Compute an explainable competency gap and ordered pathway.

    `evidence` is the optional separated-evidence map from
    services/evidence_resolver.py -- `{competency_id: {evidence_type: {value,
    recorded_at, detail}}}` in Lane 2's storage vocabulary. When a competency
    carries `self_report` or `observed_practice` there, those authoritative
    rows take precedence over the legacy `self_ratings`/`measured_scores`
    arguments for that competency. The other three types are recorded and
    reported per SCORING_EVIDENCE_TYPES' note, but never move the score.

    This function stays pure: no database, no HTTP, no clock. That is what
    lets the golden fixtures pin its output exactly.
    """
    curriculum = get_curriculum(curriculum_slug, lang)
    if not curriculum:
        raise ValueError(f"Unknown curriculum: {curriculum_slug}")

    evidence_sentences = _EVIDENCE_SENTENCE.get(lang, _EVIDENCE_SENTENCE["en"])
    evidence_type_labels = _EVIDENCE_TYPE_LABEL.get(lang, _EVIDENCE_TYPE_LABEL["en"])

    allowed = {item["id"] for item in curriculum["competencies"]}
    unknown = sorted(set(self_ratings) - allowed)
    if unknown:
        raise ValueError(f"Ratings contain competencies outside this curriculum: {', '.join(unknown)}")

    # measured_scores deliberately gets no such check, unlike self_ratings/
    # evidence: routes/learning_common.py's measured_scores() returns a
    # player's FULL cross-curriculum AccuracyHistory snapshot (DSA rooms,
    # every other domain's topics, "boss::<slug>" entries, all of it) and
    # every call site hands that same full dict to analyse_competencies()
    # regardless of which curriculum_slug is being analysed -- silently
    # ignoring a key outside `allowed` (via the plain .get() below) is that
    # filtering step, not a defect to close. Validating it here would 422 any
    # player who has practiced more than one domain, on every pathway/
    # assessment call for either one.

    # Bound to its own name: `evidence` is reused below as the per-competency
    # explanation string, and rebinding the parameter would corrupt it on the
    # next loop iteration.
    evidence_map = evidence or {}
    unknown_evidence = sorted(set(evidence_map) - allowed)
    if unknown_evidence:
        raise ValueError(
            f"Evidence contains competencies outside this curriculum: {', '.join(unknown_evidence)}"
        )

    target_cap = experience_cap(experience_level)
    competency_results = []
    for item in curriculum["competencies"]:
        competency_id = item["id"]
        recorded = evidence_map.get(competency_id, {})

        # A stored EvidenceRecord outranks the legacy argument for the same
        # type: it is the auditable row, the argument is a loose input.
        # `value=None` (Lane 2 allows qualitative reviewer notes) counts as
        # present-but-unscored, never as zero.
        self_score = self_ratings.get(competency_id)
        if "self_report" in recorded and recorded["self_report"].get("value") is not None:
            self_score = float(recorded["self_report"]["value"])
        measured = measured_scores.get(competency_id)
        if "observed_practice" in recorded and recorded["observed_practice"].get("value") is not None:
            measured = float(recorded["observed_practice"]["value"])

        # evidence_sources uses Lane 2's EVIDENCE_TYPES vocabulary
        # (backend/models/governance.py) so nothing needs relabeling as more
        # evidence moves into EvidenceRecord rows.
        present = set(recorded)
        if measured is not None:
            present.add("observed_practice")
        if self_score is not None:
            present.add("self_report")
        evidence_sources = [t for t in EVIDENCE_TYPE_ORDER if t in present]

        # Each type kept separate and individually inspectable -- the literal
        # "separate ... evidence" deliverable, rather than a single collapsed
        # number a reviewer cannot take apart.
        evidence_records = [
            {
                "evidence_type": evidence_type,
                "value": recorded[evidence_type].get("value"),
                "recorded_at": recorded[evidence_type].get("recorded_at"),
                "detail": recorded[evidence_type].get("detail", ""),
                "scored": evidence_type in SCORING_EVIDENCE_TYPES,
            }
            for evidence_type in EVIDENCE_TYPE_ORDER
            if evidence_type in recorded
        ]
        unscored_present = [t for t in UNSCORED_EVIDENCE_TYPES if t in present]

        if measured is not None and self_score is not None:
            observed = measured * 0.65 + self_score * 0.35
            evidence = evidence_sentences["both"]
        elif measured is not None:
            observed = measured
            evidence = evidence_sentences["measured_only"]
        elif self_score is not None:
            observed = self_score
            evidence = evidence_sentences["self_only"]
        elif unscored_present:
            # Evidence exists, but none of it is scored under this policy
            # version -- so there is still no defensible number. Say that,
            # rather than letting 0.0 read as a measured floor.
            observed = 0.0
            evidence = evidence_sentences["unscored"].format(
                types=", ".join(evidence_type_labels.get(t, t) for t in unscored_present),
                version=ASSESSMENT_POLICY_VERSION,
            )
        else:
            observed = 0.0
            evidence = evidence_sentences["none"]

        # A resolved map (from services/role_target_resolver.py, backed by
        # Lane 2's role_targets table) is authoritative and complete when
        # supplied; otherwise fall back to the in-memory demonstration set.
        # Both produce the identical record shape.
        if role_targets is not None and competency_id in role_targets:
            role_target_info = role_targets[competency_id]
        else:
            role_target_info = resolve_role_target(
                competency_id,
                item.get("target_level", 3),
                job_role,
                designation,
                current_assignment,
                department,
            )
        role_target = role_target_info["target_level"]
        pathway_target = min(role_target, float(target_cap))
        gap = max(0.0, pathway_target - observed)
        has_evidence = bool(evidence_sources)
        # Only *scored* evidence yields a defensible observed_level. A learner
        # carrying just a qualitative reviewer note has evidence but no rating,
        # so the gap-derived tiers below would turn a 0.0 placeholder into
        # "critical" -- the exact unsupported low-ability judgment CLAUDE.md
        # architectural invariant #3 forbids.
        has_scored_evidence = measured is not None or self_score is not None
        if not has_scored_evidence:
            # The gap number itself is unchanged and still drives sort order.
            priority = "unassessed"
        elif gap >= 2.5:
            priority = "critical"
        elif gap >= 1.5:
            priority = "high"
        elif gap >= 0.5:
            priority = "medium"
        else:
            priority = "maintain"

        competency_results.append(
            {
                "competency_id": competency_id,
                "label": item["label"],
                "description": item["description"],
                "prerequisites": item.get("prerequisites", []),
                "observed_level": round(observed, 2),
                "observed_label": _level_label(observed, lang),
                "observed_anchor": get_anchor(competency_id, observed),
                "target_anchor": get_anchor(competency_id, pathway_target),
                "pathway_target": pathway_target,
                "role_target": role_target,
                "role_target_source": role_target_info["source"],
                "role_target_assurance": role_target_info["assurance"],
                "matched_role": role_target_info["matched_role"],
                "matched_field": role_target_info["matched_field"],
                "gap": round(gap, 2),
                "priority": priority,
                "has_evidence": has_evidence,
                "has_scored_evidence": has_scored_evidence,
                "evidence_sources": evidence_sources,
                "evidence_records": evidence_records,
                # NO EVIDENCE is reserved for genuinely nothing on file. A
                # recorded-but-unscored type is evidence, so it does not carry
                # that label -- has_scored_evidence is what says the level is
                # not yet derivable.
                "evidence_state": None if has_evidence else NO_EVIDENCE,
                "confidence": _confidence(evidence_sources),
                "evidence": evidence,
            }
        )

    skill_gaps = [item for item in competency_results if item["gap"] >= 0.5]
    order = {item["id"]: index for index, item in enumerate(curriculum["competencies"])}
    skill_gaps.sort(key=lambda item: (-item["gap"], order[item["competency_id"]]))

    # Build a teachable order: prerequisites first, then the largest remaining
    # gaps. This keeps the output interpretable and lets a judge change a
    # prerequisite live without retraining a model.
    pending = {item["competency_id"]: item for item in skill_gaps}
    pathway = []
    while pending:
        ready = [
            item for item in pending.values()
            if all(prerequisite not in pending for prerequisite in item["prerequisites"])
        ]
        if not ready:  # Defensive fallback for malformed/cyclic seed data.
            ready = list(pending.values())
        ready.sort(key=lambda item: (-item["gap"], order[item["competency_id"]]))
        for item in ready:
            pathway.append(
                {
                    "step": len(pathway) + 1,
                    **item,
                    "recommended_action": (
                        _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["unassessed"]
                        if item["priority"] == "unassessed"
                        else _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["foundation"]
                        if item["observed_level"] < 1
                        else _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["targeted"]
                    ),
                }
            )
            pending.pop(item["competency_id"], None)

    courses = recommend_courses(skill_gaps, lang)
    return {
        "curriculum_slug": curriculum_slug,
        "curriculum_name": curriculum["name"],
        "domain": curriculum["domain"],
        "experience_level": experience_level,
        "job_role": job_role,
        "designation": designation,
        "current_assignment": current_assignment,
        "department": department,
        "method": {
            "scale": "0-5 proficiency",
            "demonstrated_weight": 0.65,
            "self_assessment_weight": 0.35,
            "note": _METHOD_NOTE.get(lang, _METHOD_NOTE["en"]),
            "policy_version": ASSESSMENT_POLICY_VERSION,
            "scored_evidence_types": list(SCORING_EVIDENCE_TYPES),
            "recorded_unscored_evidence_types": list(UNSCORED_EVIDENCE_TYPES),
            "unscored_note": (
                "Reviewer, diagnostic and provider-imported evidence is recorded and shown "
                "separately but does not move observed_level: no domain-reviewer-validated "
                "weights exist for it yet."
            ),
            "role_target_framework_version": FRAMEWORK_VERSION,
            # Per-anchor source/status live inside each observed_anchor/
            # target_anchor record; these two are just the module-wide
            # starting defaults, for a consumer that wants one summary value
            # without inspecting every anchor individually.
            "behavioral_anchor_default_source": DEFAULT_SOURCE,
            "behavioral_anchor_default_status": DEFAULT_STATUS,
        },
        "competencies": competency_results,
        "skill_gaps": skill_gaps,
        "pathway": pathway,
        "courses": courses,
    }

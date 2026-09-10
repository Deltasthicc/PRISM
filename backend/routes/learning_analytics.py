"""Privacy-safe aggregate analytics routes."""

from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import CompetencyAssessment, GeneratedQuiz, LearnerProfile
from models.player import Player
from routes.authorization import require_permission_dependency
from security.rbac import BoundPrincipal, Permission
from services.learning_catalog import integration_status

router = APIRouter(prefix="/learning", tags=["Learning Analytics"])

_PRIVACY_NOTE = {
    "en": "This endpoint intentionally exposes latest-distinct-learner aggregates only.",
    "hi": "यह एंडपॉइंट जानबूझकर केवल नवीनतम-विशिष्ट-शिक्षार्थी समुच्चय ही प्रकट करता है।",
    "bn": "এই শেষপয়েন্ট ইচ্ছাকৃতভাবে শুধুমাত্র সাম্প্রতিক-স্বতন্ত্র-শিক্ষক সমষ্টিকে প্রকাশ করে।",
    "mr": "हा एंडपॉईंट जाणूनबुजून केवळ नवीनतम-वेगवेगळ्या-शिक्षणा-यांच्या एकत्रिततेचा पर्दाफाश करतो.",
    "te": "ఈ ఎండ్‌పాయింట్ ఉద్దేశపూర్వకంగా తాజా-విశిష్ట-అభ్యాసకుల సముదాయాలను మాత్రమే బహిర్గతం చేస్తుంది.",
    "ta": "இந்த இறுதிப்புள்ளி வேண்டுமென்றே சமீபத்திய-தனித்துவ-கற்றல் திரட்டுகளை மட்டுமே வெளிப்படுத்துகிறது.",
    "gu": "આ એન્ડપોઇન્ટ ઇરાદાપૂર્વક ફક્ત નવીનતમ-વિશિષ્ટ-શિખનાર એકંદરને પ્રગટ કરે છે.",
    "ur": "یہ اختتامی نقطہ جان بوجھ کر صرف تازہ ترین الگ الگ سیکھنے والے مجموعوں کو ظاہر کرتا ہے۔",
    "kn": "ಈ ಅಂತಿಮ ಬಿಂದುವು ಉದ್ದೇಶಪೂರ್ವಕವಾಗಿ ಇತ್ತೀಚಿನ-ವಿಶಿಷ್ಟ-ಕಲಿಕಾ ಸಮುಚ್ಚಯಗಳನ್ನು ಮಾತ್ರ ಬಹಿರಂಗಪಡಿಸುತ್ತದೆ.",
    "or": "ଏହି ଶେଷ ପଏଣ୍ଟ ଉଦ୍ଦେଶ୍ୟମୂଳକ ଭାବରେ କେବଳ ସର୍ବଶେଷ-ପୃଥକ-ଶିକ୍ଷାର୍ଥୀ ଏଗ୍ରିଗେଟ୍ଗୁଡ଼ିକୁ ପ୍ରକାଶ କରେ |",
    "ml": "ഈ എൻഡ്‌പോയിൻ്റ് ഏറ്റവും പുതിയ-വ്യത്യസ്‌ത-പഠിതാക്കളുടെ സംഗ്രഹങ്ങളെ മാത്രം മനഃപൂർവം തുറന്നുകാട്ടുന്നു.",
}


@router.get("/admin/overview")
async def admin_overview(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)
    ),
    lang: str = Query("en", pattern="^(en|hi|bn|mr|te|ta|gu|ur|kn|or|ml)$"),
):
    """Aggregate-only dashboard using the latest assessment per learner stream."""
    assessments_by_stream = {}
    for assessment in db.query(CompetencyAssessment).all():
        key = (assessment.player_id, assessment.curriculum_slug)
        current = assessments_by_stream.get(key)
        if current is None or (
            assessment.created_at, assessment.assessment_id
        ) > (current.created_at, current.assessment_id):
            assessments_by_stream[key] = assessment
    assessments = list(assessments_by_stream.values())
    gap_counter = Counter()
    priority_counter = Counter()
    for assessment in assessments:
        for gap in assessment.skill_gaps or []:
            gap_counter[gap.get("label") or gap.get("competency_id", "Unknown")] += 1
            priority_counter[gap.get("priority", "unknown")] += 1
    return {
        "learners": db.query(Player).count(),
        "profiles_completed": db.query(LearnerProfile).count(),
        "assessments_completed": len(assessments),
        "quizzes_generated": db.query(GeneratedQuiz).count(),
        "top_skill_gaps": [
            {"competency": competency, "learner_count": count}
            for competency, count in gap_counter.most_common(8)
        ],
        "gap_priorities": dict(priority_counter),
        "integration_status": integration_status(lang),
        "privacy_note": _PRIVACY_NOTE.get(lang, _PRIVACY_NOTE["en"]),
    }
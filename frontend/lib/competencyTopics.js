// Mirrors backend/routes/competency_quiz.py's TOPICS dict -- keep the
// topic_id keys and curriculum_slug values in sync if that file changes.
// This is the single source of truth both CreateProfilePage (specialization
// picker) and CompetencyQuizPage (question fetch/scoring) use, so a chosen
// specialization always maps to a real backend topic with real questions --
// never a label the quiz has no content for.
export const COMPETENCY_TOPICS = [
  {
    id: 'statistical_foundations',
    label: 'Statistical Foundations & Sampling Design',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'data_quality',
    label: 'Data Quality & Metadata Standards',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'national_accounts',
    label: 'National Accounts & Price Statistics',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'digital_governance',
    label: 'Digital Governance & Data Privacy',
    curriculumSlug: 'digital-literacy',
  },
  {
    id: 'ai_technology',
    label: 'AI & Responsible Technology',
    curriculumSlug: 'digital-literacy',
  },
];

export const TOPIC_BY_ID = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.id, topic]));
export const TOPIC_BY_LABEL = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.label, topic]));

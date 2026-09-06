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
    label: 'Quality Control & Data Quality',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'price_statistics',
    label: 'Price Statistics & CPI',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'data_privacy',
    label: 'Digital Governance: Data Privacy',
    curriculumSlug: 'digital-literacy',
  },
  {
    id: 'ai_policy',
    label: 'AI Policy & Literacy',
    curriculumSlug: 'digital-literacy',
  },
];

export const TOPIC_BY_ID = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.id, topic]));
export const TOPIC_BY_LABEL = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.label, topic]));

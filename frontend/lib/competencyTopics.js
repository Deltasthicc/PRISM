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
  {
    id: 'linear_structures',
    label: 'Arrays, Linked Lists & Stacks/Queues',
    curriculumSlug: 'dsa-fundamentals',
  },
  {
    id: 'recursion_and_sorting',
    label: 'Recursion & Sorting Algorithms',
    curriculumSlug: 'dsa-fundamentals',
  },
  {
    id: 'trees_and_heaps',
    label: 'Trees, Binary Search Trees & Heaps',
    curriculumSlug: 'dsa-fundamentals',
  },
  {
    id: 'graphs_and_dp',
    label: 'Graphs & Dynamic Programming',
    curriculumSlug: 'dsa-fundamentals',
  },
  {
    id: 'data_collection_and_surveys',
    label: 'Data Collection & Official Statistics',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'data_technology',
    label: 'Visualization, GIS, Big Data & Statistical Programming',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'national_accounts_and_sectoral',
    label: 'National Accounts, Labour & Industrial Statistics',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'open_data_and_standards',
    label: 'SDG Indicators, Metadata & Open Data Standards',
    curriculumSlug: 'official-statistics',
  },
  {
    id: 'governance_and_policy',
    label: 'Governance Foundations & Policy Design',
    curriculumSlug: 'public-policy',
  },
  {
    id: 'public_finance',
    label: 'Public Finance',
    curriculumSlug: 'public-policy',
  },
  {
    id: 'program_delivery',
    label: 'Program Management, Monitoring & Impact Evaluation',
    curriculumSlug: 'public-policy',
  },
  {
    id: 'ethics_and_conduct',
    label: 'Ethics & Decision-Making',
    curriculumSlug: 'public-policy',
  },
  {
    id: 'leadership_and_change',
    label: 'Leadership, Change Management & Communication',
    curriculumSlug: 'public-policy',
  },
  {
    id: 'cyber_hygiene_and_signatures',
    label: 'Cyber Hygiene & Digital Signatures',
    curriculumSlug: 'digital-literacy',
  },
  {
    id: 'responsible_ai_and_dpi',
    label: 'Responsible AI & Digital Public Infrastructure',
    curriculumSlug: 'digital-literacy',
  },
  {
    id: 'digital_office_skills',
    label: 'Digital Foundations, Collaboration & Spreadsheets',
    curriculumSlug: 'digital-literacy',
  },
  {
    id: 'government_cloud',
    label: 'Government Cloud (GI Cloud / MeghRaj)',
    curriculumSlug: 'digital-literacy',
  },
];

export const TOPIC_BY_ID = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.id, topic]));
export const TOPIC_BY_LABEL = Object.fromEntries(COMPETENCY_TOPICS.map((topic) => [topic.label, topic]));

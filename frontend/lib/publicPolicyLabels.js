// Friendly labels for the public-policy competency_ids used by the
// Judgment Simulation scenarios (services/curricula.py owns the
// authoritative competency list). Falls back to a titleized competency_id
// for anything not listed here, rather than a hardcoded default that could
// silently mislabel a future scenario.
const COMPETENCY_LABELS = {
  pa_decision_making: 'Decision Making',
  pa_ethics: 'Ethics & Integrity',
  pa_change_management: 'Change Management',
  pa_governance_foundations: 'Governance Foundations',
};

export function competencyLabel(competencyId) {
  if (!competencyId) return 'this competency';
  return (
    COMPETENCY_LABELS[competencyId] ||
    competencyId
      .replace(/^pa_/, '')
      .split('_')
      .map((word) => word[0]?.toUpperCase() + word.slice(1))
      .join(' ')
  );
}

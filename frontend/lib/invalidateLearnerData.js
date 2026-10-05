// Several screens cache the same learner's profile-derived data under
// different React Query keys (Stats / NavBar / Dungeon / DSA share
// 'learning-profile'; the Academy hub, pathway and dashboard have their own).
// Anything that changes that data -- saving the profile, finishing a graded
// quiz and its assessment snapshot -- calls this so every screen re-reads it
// instead of showing the pre-change value until its staleTime lapses.
const LEARNER_QUERY_KEYS = ['learning-profile', 'academy', 'pathway', 'dashboard'];

export function invalidateLearnerData(queryClient, playerId) {
  if (!playerId) return Promise.resolve();
  return Promise.all(
    LEARNER_QUERY_KEYS.map((key) => queryClient.invalidateQueries({ queryKey: [key, playerId] }))
  );
}

// Role-aware work areas for the three SIH26075 experiences (Trainee, Trainer,
// Admin). This only decides which links to SHOW; it is not authorization. The
// backend checks every permission, so a link to a page the caller may not use
// just ends in that page's own "not allowed" message.
//
// `roles` are the realm roles carried by the verified OIDC token (see
// store/useAuthStore.js). In the hosted demo, which runs with authentication
// bypassed, the browser has no roles at all and the backend treats the caller
// as holding every role, so an empty list shows every area rather than
// pretending to know who the user is.

const LEARNING = {
  id: 'learning',
  label: 'Learning',
  links: [
    { href: '/courses', label: 'Courses' },
    { href: '/questionnaires', label: 'Questionnaires' },
    { href: '/library', label: 'Library' },
    { href: '/certificates', label: 'Certificates' },
  ],
};

const TEACHING = {
  id: 'teaching',
  label: 'Teaching',
  links: [
    { href: '/trainer/courses', label: 'My courses' },
    { href: '/trainer/cohorts', label: 'Cohorts' },
    { href: '/trainer/questionnaires', label: 'Questionnaires' },
    { href: '/trainer/library', label: 'Content library' },
    { href: '/trainer/expertise', label: 'Expertise' },
    { href: '/trainer-review', label: 'Quiz review' },
  ],
};

const ADMINISTRATION = {
  id: 'administration',
  label: 'Administration',
  links: [
    { href: '/admin', label: 'Dashboard' },
    { href: '/admin/approvals', label: 'Approvals' },
    { href: '/admin/announcements', label: 'Announcements' },
    { href: '/admin/cohorts', label: 'Cohorts' },
    { href: '/admin/trainer-matching', label: 'Trainer matching' },
  ],
};

export function navGroupsForRoles(roles) {
  const held = new Set(roles || []);
  if (held.size === 0) return [LEARNING, TEACHING, ADMINISTRATION];

  const groups = [];
  if (held.has('learner')) groups.push(LEARNING);
  if (held.has('trainer')) groups.push(TEACHING);
  // Only organization_admin holds the admin permissions today; department_admin
  // is deliberately empty until a department scope exists (security/rbac.py).
  if (held.has('organization_admin')) groups.push(ADMINISTRATION);
  return groups;
}

// The link whose href is the longest prefix of the path, so /admin/approvals
// lights up "Approvals" rather than also "Dashboard".
export function activeHref(groups, pathname) {
  let best = null;
  for (const group of groups) {
    for (const link of group.links) {
      const matches = pathname === link.href || pathname.startsWith(`${link.href}/`);
      if (matches && (best === null || link.href.length > best.length)) best = link.href;
    }
  }
  return best;
}

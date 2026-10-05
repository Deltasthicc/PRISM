import { describe, expect, it } from 'vitest';
import { activeHref, navGroupsForRoles } from '@/lib/navigation';

const ids = (roles) => navGroupsForRoles(roles).map((group) => group.id);

describe('navGroupsForRoles', () => {
  it('shows every area when there are no roles (demo mode has no identity to go on)', () => {
    expect(ids([])).toEqual(['learning', 'teaching', 'administration']);
    expect(ids(undefined)).toEqual(['learning', 'teaching', 'administration']);
  });

  it('shows only the learner area to a trainee', () => {
    expect(ids(['learner'])).toEqual(['learning']);
  });

  it('shows only the teaching area to a trainer', () => {
    expect(ids(['trainer'])).toEqual(['teaching']);
  });

  it('shows administration to an organization admin and nothing for a role-less department admin', () => {
    expect(ids(['organization_admin'])).toEqual(['administration']);
    expect(ids(['department_admin'])).toEqual([]);
  });

  it('combines areas for a user with several roles, in a stable order', () => {
    expect(ids(['organization_admin', 'learner', 'trainer'])).toEqual(['learning', 'teaching', 'administration']);
  });

  it('ignores roles it does not know about', () => {
    expect(ids(['learner', 'auditor'])).toEqual(['learning']);
  });
});

describe('activeHref', () => {
  const groups = navGroupsForRoles([]);

  it('prefers the most specific matching link', () => {
    expect(activeHref(groups, '/admin/approvals')).toBe('/admin/approvals');
    expect(activeHref(groups, '/admin')).toBe('/admin');
  });

  it('matches nested paths', () => {
    expect(activeHref(groups, '/courses/abc')).toBe('/courses');
    expect(activeHref(groups, '/questionnaires/q-1')).toBe('/questionnaires');
  });

  it('does not treat a longer sibling as a prefix match', () => {
    expect(activeHref(groups, '/trainer-review')).toBe('/trainer-review');
    expect(activeHref(groups, '/coursesX')).toBeNull();
  });

  it('is null for pages outside the work areas', () => {
    expect(activeHref(groups, '/stats')).toBeNull();
  });
});

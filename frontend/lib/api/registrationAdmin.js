import { request } from './client';

// Admin side of self-service registration (backend/routes/registration.py).
// Both calls need organization_admin; the server enforces it.
export const registrationAdmin = {
  listPending: () => request('/auth/pending-registrations'),

  decide: (bindingId, decision, notes = '') =>
    request(`/auth/pending-registrations/${encodeURIComponent(bindingId)}/decide`, {
      method: 'POST',
      body: { decision, notes },
    }),
};

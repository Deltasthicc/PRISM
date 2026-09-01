"""Lane 2 security, identity, data-rights and policy primitives.

This package contains the implemented OIDC verifier, issuer/subject binding and RBAC boundary,
bootstrap/audit/data-rights/retention services, and a versioned encryption primitive for future
reviewed sensitive fields. Product routes do not yet compose these primitives, and the encryption
module is not wired to persistence; neither fact may be described as production authorization or
key-management evidence. See ``docs/contracts/identity-authorization.md`` and the Lane 2 contracts.
"""

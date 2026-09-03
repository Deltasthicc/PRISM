# Encryption and key-ownership contract

Owner: Lane 2 (primitive and data semantics)

Operational consumers/approvers: Lane 6, the deployment owner, privacy owner and security owner

Status: **versioned application-level encryption primitive implemented for future reviewed fields;
no current model field uses it and no production key-management claim exists.**

## 1. Current data reality

The current SQLAlchemy models do not persist application passwords, OAuth client secrets, provider
API keys or encryption keys. Synthetic learner/profile/evidence data is still personal-data-shaped,
but no field has an approved requirement to be encrypted separately from the database/storage
layer. Adding ciphertext columns without a field-level threat model, query/index impact, migration,
backfill and key owner would create theatre rather than a usable control.

Therefore `backend/security/encryption.py` is intentionally **not wired into any model or route**.
It is a reusable boundary for a future field only after its owning lane proposes a reviewed contract
change.

The local development Compose stack is also not encrypted in transit:

- PostgreSQL is published from container port 5432 to `localhost:55432` without TLS configuration.
- Keycloak runs `start-dev` and publishes HTTP on `localhost:8180`.
- The local PostgreSQL volume and SQLite `app.db` have no repository-configured encryption at rest.

These settings are acceptable only for synthetic local development. They are not a deployment
template and must not carry real credentials or personnel data.

## 2. Implemented primitive

`EncryptionKeyring` provides a versioned AES-256-GCM encrypted envelope with:

- a 32-byte key selected by a non-secret `key_id`;
- a fresh operating-system-generated 96-bit nonce for every encryption;
- ciphertext with the library-managed 128-bit authentication tag;
- required caller-supplied associated context built by
  `build_encryption_context("table", "immutable-record-id", "field-name")`, authenticated but not
  encrypted;
- strict version/algorithm/field parsing and one generic authentication failure for wrong keys,
  wrong context or tampering; and
- active-key rotation: new values use the active key while retained old keys can decrypt old
  envelopes.

The cleartext `key_id` is included in authenticated associated data. The context builder uses
length-prefixed UTF-8 components rather than delimiter concatenation, so component values containing
colons or other punctuation cannot produce the same encoded context. The primitive rejects raw or
malformed context bytes. Callers must use a stable, immutable record identifier and field name so
ciphertext cannot be moved between records or fields. Context must not contain secrets because
associated data is not encrypted.

The implementation follows the upstream `cryptography` AESGCM contract: AES-256 keys, a 12-byte
nonce and **no nonce reuse with the same key**. See
[Authenticated encryption — cryptography documentation](https://cryptography.io/en/stable/hazmat/primitives/aead/).

## 3. Key lifecycle boundary

The repository implements no key store. In particular:

- keys must never be committed, accepted from browser/request data, printed or placed in an
  encrypted envelope;
- `generate_aes256_key()` only returns random key bytes in memory; it does not persist or authorize
  a key;
- Python immutable key bytes cannot be reliably zeroized and remain in process memory until their
  objects are reclaimed; the in-process keyring is not a substitute for non-exportable KMS/HSM
  operations;
- removing an old key makes its existing envelopes undecryptable, so retirement requires verified
  re-encryption or approved destruction first;
- changing the active key does not automatically re-encrypt stored data; and
- backup encryption is a separate operational control. The local `backup_restore.py` archives are
  not encrypted by this primitive.

A production deployment must obtain keys from an approved KMS/HSM or equivalent secret-management
service. The accountable security/deployment owner must define generation, custody, access policy,
separation of duties, rotation/retirement, backup/escrow if authorized, compromise response,
audit/alerting and deletion. Lane 2 must consume a narrow key-provider interface rather than embed
provider credentials or key material in application configuration.

## 4. Adoption gate for a future field

Before any model uses this primitive, its issue/PR must provide:

1. the exact field and threat being mitigated;
2. data owner, lawful purpose, retention/deletion behavior and logs that must redact it;
3. immutable context construction and behavior when the owning record ID changes;
4. schema migration, backfill, rollback and mixed-key read behavior;
5. approved key provider and accountable custody/rotation owner;
6. tamper, wrong-context, unavailable-key, rotation and recovery tests; and
7. Lane 6 operational evidence that TLS, storage/backup encryption and secrets handling are also
   configured—application-level encryption is not a substitute for them.

Until those conditions exist, this package closes only the reusable code/contract gap. Production
encryption, key ownership and compliance remain **BLOCKED-EXTERNAL/OPERATIONAL**.

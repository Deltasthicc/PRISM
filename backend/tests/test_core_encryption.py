"""Package Q tests for the versioned authenticated-encryption boundary."""

from __future__ import annotations

import base64

import pytest

from security.encryption import (
    ENVELOPE_ALGORITHM,
    ENVELOPE_VERSION,
    MAX_CONTEXT_BYTES,
    MAX_PLAINTEXT_BYTES,
    EncryptedEnvelope,
    EncryptionError,
    EncryptionKeyring,
    build_encryption_context,
    generate_aes256_key,
)


def _key(byte: int) -> bytes:
    return bytes([byte]) * 32


def _keyring(*, active: str = "key-2026-09") -> EncryptionKeyring:
    return EncryptionKeyring(
        keys={"key-2026-08": _key(8), "key-2026-09": _key(9)},
        active_key_id=active,
    )


def _context(record_id: str = "1", field: str = "field") -> bytes:
    return build_encryption_context("records", record_id, field)


def test_round_trip_uses_versioned_json_serializable_envelope():
    keyring = _keyring()

    envelope = keyring.encrypt(
        b"future-sensitive-value",
        context=build_encryption_context(
            "identity_bindings",
            "binding-123",
            "future-field",
        ),
    )

    assert envelope.version == ENVELOPE_VERSION
    assert envelope.algorithm == ENVELOPE_ALGORITHM
    assert envelope.key_id == "key-2026-09"
    assert set(envelope.to_dict()) == {
        "version",
        "algorithm",
        "key_id",
        "nonce_b64",
        "ciphertext_b64",
    }
    assert (
        keyring.decrypt(
            envelope.to_dict(),
            context=build_encryption_context(
                "identity_bindings",
                "binding-123",
                "future-field",
            ),
        )
        == b"future-sensitive-value"
    )


def test_encrypt_consumes_a_distinct_96_bit_nonce_for_each_message(monkeypatch):
    keyring = _keyring()
    requested_lengths: list[int] = []
    nonces = iter([b"a" * 12, b"b" * 12])

    def _next_nonce(length: int) -> bytes:
        requested_lengths.append(length)
        return next(nonces)

    monkeypatch.setattr("security.encryption.os.urandom", _next_nonce)
    first = keyring.encrypt(b"same", context=_context())
    second = keyring.encrypt(b"same", context=_context())

    assert requested_lengths == [12, 12]
    assert base64.urlsafe_b64decode(first.nonce_b64) == b"a" * 12
    assert base64.urlsafe_b64decode(second.nonce_b64) == b"b" * 12
    assert first.nonce_b64 != second.nonce_b64
    assert first.ciphertext_b64 != second.ciphertext_b64


@pytest.mark.parametrize(
    "mutation",
    [
        lambda envelope: {**envelope, "ciphertext_b64": _flip_first_byte(envelope["ciphertext_b64"])},
        lambda envelope: {**envelope, "nonce_b64": _flip_first_byte(envelope["nonce_b64"])},
        lambda envelope: {**envelope, "key_id": "key-2026-08"},
    ],
    ids=["ciphertext", "nonce", "key-id"],
)
def test_tampered_envelope_fails_closed(mutation):
    keyring = _keyring()
    envelope = keyring.encrypt(b"secret", context=_context()).to_dict()

    with pytest.raises(EncryptionError, match="authentication failed"):
        keyring.decrypt(mutation(envelope), context=_context())


def _flip_first_byte(value: str) -> str:
    decoded = bytearray(base64.urlsafe_b64decode(value))
    decoded[0] ^= 1
    return base64.urlsafe_b64encode(decoded).decode("ascii")


def test_ciphertext_is_bound_to_its_record_and_field_context():
    keyring = _keyring()
    envelope = keyring.encrypt(b"secret", context=_context("1", "field-a"))

    with pytest.raises(EncryptionError, match="authentication failed"):
        keyring.decrypt(envelope, context=_context("2", "field-a"))
    with pytest.raises(EncryptionError, match="authentication failed"):
        keyring.decrypt(envelope, context=_context("1", "field-b"))


def test_context_builder_is_injective_for_delimiter_bearing_components():
    assert build_encryption_context("records", "a:b", "c") != build_encryption_context(
        "records", "a", "b:c"
    )


def test_rotation_encrypts_with_active_key_and_retains_old_key_for_decryption():
    old_keyring = EncryptionKeyring(keys={"old": _key(1)}, active_key_id="old")
    old_envelope = old_keyring.encrypt(b"before rotation", context=_context("1"))

    rotated = EncryptionKeyring(
        keys={"old": _key(1), "new": _key(2)},
        active_key_id="new",
    )
    new_envelope = rotated.encrypt(b"after rotation", context=_context("2"))

    assert old_envelope.key_id == "old"
    assert new_envelope.key_id == "new"
    assert rotated.decrypt(old_envelope, context=_context("1")) == b"before rotation"
    assert rotated.decrypt(new_envelope, context=_context("2")) == b"after rotation"


def test_missing_retired_key_fails_without_exposing_key_material():
    retired_key = bytes(range(32))
    current_key = bytes(range(32, 64))
    old = EncryptionKeyring(keys={"retired": retired_key}, active_key_id="retired")
    envelope = old.encrypt(b"secret", context=_context())
    current = EncryptionKeyring(keys={"current": current_key}, active_key_id="current")

    with pytest.raises(EncryptionError, match="unavailable key_id") as caught:
        current.decrypt(envelope, context=_context())

    rendered = str(caught.value) + repr(current)
    for secret in (retired_key, current_key):
        assert repr(secret) not in rendered
        assert secret.hex() not in rendered
        assert base64.urlsafe_b64encode(secret).decode("ascii") not in rendered


@pytest.mark.parametrize(
    ("keys", "active", "message"),
    [
        ({}, "active", "non-empty mapping"),
        ({"active": b"short"}, "active", "exactly 32 bytes"),
        ({"available": _key(1)}, "missing", "does not name a configured key"),
        ({"bad key id": _key(1)}, "bad key id", "key_id must be"),
    ],
)
def test_keyring_configuration_fails_closed(keys, active, message):
    with pytest.raises(EncryptionError, match=message):
        EncryptionKeyring(keys=keys, active_key_id=active)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {
            "version": 2,
            "algorithm": ENVELOPE_ALGORITHM,
            "key_id": "key-1",
            "nonce_b64": base64.urlsafe_b64encode(b"n" * 12).decode(),
            "ciphertext_b64": base64.urlsafe_b64encode(b"c" * 16).decode(),
        },
        {
            "version": ENVELOPE_VERSION,
            "algorithm": "AES-CBC",
            "key_id": "key-1",
            "nonce_b64": base64.urlsafe_b64encode(b"n" * 12).decode(),
            "ciphertext_b64": base64.urlsafe_b64encode(b"c" * 16).decode(),
        },
    ],
)
def test_malformed_or_unsupported_envelopes_are_rejected(value):
    with pytest.raises(EncryptionError):
        EncryptedEnvelope.from_dict(value)


def test_context_is_mandatory_and_plaintext_must_be_bytes():
    keyring = _keyring()
    with pytest.raises(EncryptionError, match="context must not be empty"):
        keyring.encrypt(b"secret", context=b"")
    with pytest.raises(EncryptionError, match="plaintext must be bytes"):
        keyring.encrypt("secret", context=_context())
    with pytest.raises(EncryptionError, match="created by build_encryption_context"):
        keyring.encrypt(b"secret", context=b"records:1:field")


def test_plaintext_context_and_serialized_envelope_are_bounded():
    keyring = _keyring()
    with pytest.raises(EncryptionError, match="plaintext exceeds"):
        keyring.encrypt(b"x" * (MAX_PLAINTEXT_BYTES + 1), context=_context())
    with pytest.raises(EncryptionError, match="context exceeds"):
        keyring.encrypt(b"secret", context=b"x" * (MAX_CONTEXT_BYTES + 1))

    envelope = keyring.encrypt(b"secret", context=_context()).to_dict()
    envelope["ciphertext_b64"] = "A" * ((MAX_PLAINTEXT_BYTES + 1024) * 2)
    with pytest.raises(EncryptionError, match="exceeds the supported envelope size"):
        keyring.decrypt(envelope, context=_context())


def test_non_string_unknown_envelope_field_returns_controlled_error():
    envelope = _keyring().encrypt(b"secret", context=_context()).to_dict()
    envelope[1] = "unexpected"
    with pytest.raises(EncryptionError, match="exactly the v1 fields"):
        EncryptedEnvelope.from_dict(envelope)


def test_noncanonical_or_standard_base64_is_rejected():
    envelope = _keyring().encrypt(b"secret", context=_context()).to_dict()
    nonce_with_urlsafe_symbols = b"\xfb\xff" + (b"n" * 10)
    canonical_urlsafe = base64.urlsafe_b64encode(nonce_with_urlsafe_symbols).decode("ascii")
    standard_alias = base64.b64encode(nonce_with_urlsafe_symbols).decode("ascii")
    assert canonical_urlsafe != standard_alias
    assert base64.urlsafe_b64decode(canonical_urlsafe) == base64.b64decode(standard_alias)
    envelope["nonce_b64"] = standard_alias
    with pytest.raises(EncryptionError, match="canonical URL-safe base64"):
        EncryptedEnvelope.from_dict(envelope)

    envelope = _keyring().encrypt(b"secret", context=_context()).to_dict()
    canonical_ciphertext = base64.urlsafe_b64encode(b"c" * 16).decode("ascii")
    # The low four bits of the final data character are padding bits for a
    # one-byte remainder. "w" -> "x" changes only those ignored bits, so a
    # permissive decoder yields the same bytes even though the spelling is
    # non-canonical.
    noncanonical_pad_bits = canonical_ciphertext[:-3] + "x=="
    assert base64.urlsafe_b64decode(canonical_ciphertext) == base64.urlsafe_b64decode(
        noncanonical_pad_bits
    )
    envelope["ciphertext_b64"] = noncanonical_pad_bits
    with pytest.raises(EncryptionError, match="canonical URL-safe base64"):
        EncryptedEnvelope.from_dict(envelope)


def test_malformed_metadata_is_not_reflected_in_errors():
    marker = "ATTACKER-CONTROLLED\r\n" * 1000
    envelope = _keyring().encrypt(b"secret", context=_context()).to_dict()
    envelope["algorithm"] = marker
    with pytest.raises(EncryptionError, match="unsupported encrypted envelope algorithm") as caught:
        EncryptedEnvelope.from_dict(envelope)
    assert marker not in str(caught.value)

    envelope = _keyring().encrypt(b"secret", context=_context()).to_dict()
    del envelope["algorithm"]
    envelope[marker] = ENVELOPE_ALGORITHM
    with pytest.raises(EncryptionError, match="exactly the v1 fields") as caught:
        EncryptedEnvelope.from_dict(envelope)
    assert marker not in str(caught.value)


def test_generated_keys_are_distinct_256_bit_values():
    first = generate_aes256_key()
    second = generate_aes256_key()
    assert len(first) == 32
    assert len(second) == 32
    assert first != second

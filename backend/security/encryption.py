"""Versioned authenticated-encryption primitive for future sensitive fields.

No current model stores an application password, API key, OAuth client secret or
other field that has been approved for application-level encryption. This module
is therefore deliberately not wired into persistence. It defines the fail-closed
record envelope and key-rotation behavior that a future reviewed field can use;
production key custody remains an external operational decision.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENVELOPE_VERSION = 1
ENVELOPE_ALGORITHM = "AES-256-GCM"
AES256_KEY_BYTES = 32
GCM_NONCE_BYTES = 12
GCM_TAG_BYTES = 16
MAX_PLAINTEXT_BYTES = 64 * 1024
MAX_CONTEXT_BYTES = 1024
MAX_CONTEXT_COMPONENTS = 8
MAX_CONTEXT_COMPONENT_BYTES = 255

_KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_BASE64URL_PATTERN = re.compile(r"[A-Za-z0-9_-]+={0,2}")
_AAD_PREFIX = b"prism:encrypted-envelope:v1\x00"
_CONTEXT_PREFIX = b"prism:encryption-context:v1\x00"
_ENVELOPE_FIELDS = frozenset(
    {"version", "algorithm", "key_id", "nonce_b64", "ciphertext_b64"}
)


class EncryptionError(RuntimeError):
    """Raised for invalid configuration, envelopes or authentication failure."""


def _validate_key_id(key_id: str) -> str:
    if not isinstance(key_id, str) or _KEY_ID_PATTERN.fullmatch(key_id) is None:
        raise EncryptionError(
            "key_id must be 1-64 ASCII letters, digits, dots, underscores or hyphens "
            "and must start with a letter or digit"
        )
    return key_id


def _encode_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode_base64(value: Any, *, field: str, max_decoded_bytes: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise EncryptionError(f"{field} must be a non-empty URL-safe base64 string")
    if _BASE64URL_PATTERN.fullmatch(value) is None:
        raise EncryptionError(f"{field} is not canonical URL-safe base64")
    # Reject oversized serialized input before allocating the decoded buffer.
    max_encoded_characters = ((max_decoded_bytes + 2) // 3) * 4
    if len(value) > max_encoded_characters:
        raise EncryptionError(f"{field} exceeds the supported envelope size")
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EncryptionError(f"{field} is not canonical URL-safe base64") from exc
    if _encode_base64(decoded) != value:
        raise EncryptionError(f"{field} is not canonical URL-safe base64")
    if len(decoded) > max_decoded_bytes:
        raise EncryptionError(f"{field} exceeds the supported envelope size")
    return decoded


def _require_bytes(value: Any, *, field: str, allow_empty: bool) -> bytes:
    if not isinstance(value, bytes):
        raise EncryptionError(f"{field} must be bytes")
    if not allow_empty and not value:
        raise EncryptionError(f"{field} must not be empty")
    return value


def build_encryption_context(*components: str) -> bytes:
    """Build an injective, length-prefixed context for record/field binding.

    Components normally identify a table/domain, immutable record ID and field.
    Length-prefixing prevents delimiter collisions such as (``"a:b", "c"``)
    versus (``"a", "b:c"``).
    """

    if not 1 <= len(components) <= MAX_CONTEXT_COMPONENTS:
        raise EncryptionError(
            f"context requires 1-{MAX_CONTEXT_COMPONENTS} non-empty string components"
        )
    encoded_components: list[bytes] = []
    for component in components:
        if not isinstance(component, str) or not component:
            raise EncryptionError("context components must be non-empty strings")
        encoded = component.encode("utf-8")
        if len(encoded) > MAX_CONTEXT_COMPONENT_BYTES:
            raise EncryptionError(
                f"context component exceeds {MAX_CONTEXT_COMPONENT_BYTES} UTF-8 bytes"
            )
        encoded_components.append(encoded)

    context = bytearray(_CONTEXT_PREFIX)
    context.append(len(encoded_components))
    for encoded in encoded_components:
        context.extend(len(encoded).to_bytes(2, "big"))
        context.extend(encoded)
    if len(context) > MAX_CONTEXT_BYTES:
        raise EncryptionError(f"context exceeds {MAX_CONTEXT_BYTES} bytes")
    return bytes(context)


def _validate_context(context: Any) -> bytes:
    context = _require_bytes(context, field="context", allow_empty=False)
    if len(context) > MAX_CONTEXT_BYTES:
        raise EncryptionError(f"context exceeds {MAX_CONTEXT_BYTES} bytes")
    if not context.startswith(_CONTEXT_PREFIX):
        raise EncryptionError("context must be created by build_encryption_context")
    cursor = len(_CONTEXT_PREFIX)
    if cursor >= len(context):
        raise EncryptionError("context encoding is malformed")
    component_count = context[cursor]
    cursor += 1
    if not 1 <= component_count <= MAX_CONTEXT_COMPONENTS:
        raise EncryptionError("context encoding is malformed")
    for _ in range(component_count):
        if cursor + 2 > len(context):
            raise EncryptionError("context encoding is malformed")
        component_length = int.from_bytes(context[cursor : cursor + 2], "big")
        cursor += 2
        if not 1 <= component_length <= MAX_CONTEXT_COMPONENT_BYTES:
            raise EncryptionError("context encoding is malformed")
        if cursor + component_length > len(context):
            raise EncryptionError("context encoding is malformed")
        try:
            context[cursor : cursor + component_length].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EncryptionError("context encoding is malformed") from exc
        cursor += component_length
    if cursor != len(context):
        raise EncryptionError("context encoding is malformed")
    return context


def _associated_data(key_id: str, context: bytes) -> bytes:
    # Bind the cleartext envelope routing metadata to the authentication tag.
    # Changing key_id or using the ciphertext for another record/context fails.
    return _AAD_PREFIX + key_id.encode("ascii") + b"\x00" + context


@dataclass(frozen=True, slots=True)
class EncryptedEnvelope:
    """JSON-serializable metadata plus AES-GCM ciphertext/tag."""

    version: int
    algorithm: str
    key_id: str
    nonce_b64: str
    ciphertext_b64: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "nonce_b64": self.nonce_b64,
            "ciphertext_b64": self.ciphertext_b64,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EncryptedEnvelope:
        if not isinstance(value, Mapping):
            raise EncryptionError("encrypted envelope must be a mapping")
        if len(value) != len(_ENVELOPE_FIELDS):
            raise EncryptionError("encrypted envelope must contain exactly the v1 fields")
        fields = set(value)
        if fields != _ENVELOPE_FIELDS:
            raise EncryptionError("encrypted envelope must contain exactly the v1 fields")
        version = value["version"]
        algorithm = value["algorithm"]
        if type(version) is not int or version != ENVELOPE_VERSION:
            raise EncryptionError("unsupported encrypted envelope version")
        if not isinstance(algorithm, str) or algorithm != ENVELOPE_ALGORITHM:
            raise EncryptionError("unsupported encrypted envelope algorithm")
        key_id = _validate_key_id(value["key_id"])
        nonce = _decode_base64(
            value["nonce_b64"],
            field="nonce_b64",
            max_decoded_bytes=GCM_NONCE_BYTES,
        )
        ciphertext = _decode_base64(
            value["ciphertext_b64"],
            field="ciphertext_b64",
            max_decoded_bytes=MAX_PLAINTEXT_BYTES + GCM_TAG_BYTES,
        )
        if len(nonce) != GCM_NONCE_BYTES:
            raise EncryptionError(f"nonce must decode to exactly {GCM_NONCE_BYTES} bytes")
        if len(ciphertext) < GCM_TAG_BYTES:
            raise EncryptionError("ciphertext is too short to contain an AES-GCM authentication tag")
        return cls(
            version=version,
            algorithm=algorithm,
            key_id=key_id,
            nonce_b64=value["nonce_b64"],
            ciphertext_b64=value["ciphertext_b64"],
        )


class EncryptionKeyring:
    """Encrypt with one active key and decrypt with active or retained old keys.

    Key material is copied into private instance state and is never included in
    exception text or object representation. Python immutable bytes cannot be
    reliably zeroized; keys remain in process memory until their objects are
    reclaimed. The caller owns retrieval, custody and rotation. A production
    implementation should use non-exportable approved KMS/HSM operations rather
    than source control, request data or long-lived raw application key bytes.
    """

    def __init__(self, *, keys: Mapping[str, bytes], active_key_id: str) -> None:
        active_key_id = _validate_key_id(active_key_id)
        if not isinstance(keys, Mapping) or not keys:
            raise EncryptionError("keys must be a non-empty mapping")

        validated: dict[str, bytes] = {}
        for key_id, key in keys.items():
            normalized_id = _validate_key_id(key_id)
            key_bytes = _require_bytes(key, field=f"key {normalized_id!r}", allow_empty=False)
            if len(key_bytes) != AES256_KEY_BYTES:
                raise EncryptionError(
                    f"key {normalized_id!r} must be exactly {AES256_KEY_BYTES} bytes for AES-256-GCM"
                )
            # Force a distinct immutable copy; bytes(existing_bytes) may return
            # the original object unchanged.
            validated[normalized_id] = bytes(bytearray(key_bytes))

        if active_key_id not in validated:
            raise EncryptionError("active_key_id does not name a configured key")
        self._keys = validated
        self._active_key_id = active_key_id

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def key_ids(self) -> frozenset[str]:
        return frozenset(self._keys)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(active_key_id={self._active_key_id!r}, "
            f"key_ids={sorted(self._keys)!r})"
        )

    def encrypt(self, plaintext: bytes, *, context: bytes) -> EncryptedEnvelope:
        plaintext = _require_bytes(plaintext, field="plaintext", allow_empty=True)
        if len(plaintext) > MAX_PLAINTEXT_BYTES:
            raise EncryptionError(f"plaintext exceeds {MAX_PLAINTEXT_BYTES} bytes")
        context = _validate_context(context)
        nonce = os.urandom(GCM_NONCE_BYTES)
        key_id = self._active_key_id
        ciphertext = AESGCM(self._keys[key_id]).encrypt(
            nonce,
            plaintext,
            _associated_data(key_id, context),
        )
        return EncryptedEnvelope(
            version=ENVELOPE_VERSION,
            algorithm=ENVELOPE_ALGORITHM,
            key_id=key_id,
            nonce_b64=_encode_base64(nonce),
            ciphertext_b64=_encode_base64(ciphertext),
        )

    def decrypt(
        self,
        envelope: EncryptedEnvelope | Mapping[str, Any],
        *,
        context: bytes,
    ) -> bytes:
        context = _validate_context(context)
        if not isinstance(envelope, EncryptedEnvelope):
            envelope = EncryptedEnvelope.from_dict(envelope)
        else:
            # Reparse to apply the same strict validation to manually constructed
            # dataclass instances as to deserialized mappings.
            envelope = EncryptedEnvelope.from_dict(envelope.to_dict())

        key = self._keys.get(envelope.key_id)
        if key is None:
            raise EncryptionError("encrypted envelope references an unavailable key_id")
        nonce = _decode_base64(
            envelope.nonce_b64,
            field="nonce_b64",
            max_decoded_bytes=GCM_NONCE_BYTES,
        )
        ciphertext = _decode_base64(
            envelope.ciphertext_b64,
            field="ciphertext_b64",
            max_decoded_bytes=MAX_PLAINTEXT_BYTES + GCM_TAG_BYTES,
        )
        try:
            return AESGCM(key).decrypt(
                nonce,
                ciphertext,
                _associated_data(envelope.key_id, context),
            )
        except InvalidTag as exc:
            # Do not distinguish wrong keys, context or tampering to callers.
            raise EncryptionError("encrypted envelope authentication failed") from exc


def generate_aes256_key() -> bytes:
    """Generate 32 random bytes suitable for one AES-256-GCM key.

    This helper does not persist, print or register the key. Production key
    generation and custody must be performed by the approved KMS/HSM owner.
    """

    return AESGCM.generate_key(bit_length=256)

"""Local-disk storage for the trainer content library (SIH26075 PS75-10).

Every uploaded byte is UNTRUSTED input (CLAUDE.md invariant 10). The rules
this module enforces, all server-side:

* The only name ever used on disk is a server-generated `<uuid4 hex>.<ext>`
  (`stored_name`); nothing the client sends (filename, Content-Type) reaches
  a filesystem path. On read the name is re-validated against a strict
  pattern and the resolved path must stay inside the storage directory.
* Type allowlist by extension AND a cheap content sniff (magic bytes, an
  OOXML zip-directory check, UTF-8/no-NUL for text). A `.pdf` that is really
  HTML is rejected. The stored `media_type` comes from THIS allowlist, never
  from the client's header.
* The upload is streamed to a temp file in fixed-size chunks with a hard size
  cap, hashing as it goes; an oversize or invalid upload leaves no file
  behind. The final file appears atomically (temp file then `os.replace`).

NOT implemented (stated so nobody assumes otherwise): there is NO virus or
malware scanning and NO transcoding, re-encoding or content sanitisation of
any kind. The sniff only checks that the bytes look like the claimed format;
a well-formed file can still carry a malicious payload. Safety on the way
out relies on never serving inline (`Content-Disposition: attachment`),
`X-Content-Type-Options: nosniff` and a restrictive CSP -- see
`routes/content_library.py`.

Storage is the local filesystem (env `CONTENT_LIBRARY_DIR`, default
`backend/data/content_library`). It is not durable on hosts with ephemeral
disks (e.g. Render's free tier); a production deployment needs a mounted
volume or object storage behind this same interface.

Size enforcement is layered: `UploadBodyLimitMiddleware` rejects an oversized
request by its Content-Length before the multipart body is parsed (so the
framework never spools it), and `store_upload` enforces the exact per-file
cap while streaming as the authoritative check.
"""
from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
# Multipart framing + the small text fields; the per-file cap is exact.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
UPLOAD_PATH = "/learning/library/items"

_STORED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.([a-z0-9]{2,4})$")
_MAX_DISPLAY_NAME = 120


class StorageError(Exception):
    """Base class; `status_code` is the HTTP status the route should return."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnsupportedTypeError(StorageError):
    status_code = 415


class FileTooLargeError(StorageError):
    status_code = 413


class EmptyFileError(StorageError):
    status_code = 422


@dataclass(frozen=True)
class StoredFile:
    stored_name: str
    media_type: str
    size_bytes: int
    sha256: str
    original_filename: str


# ---------------------------------------------------------------- allowlist


def _sniff_pdf(head: bytes) -> bool:
    # The spec allows a few bytes of junk before the header; accept the
    # marker within the first KiB like most readers do.
    return b"%PDF-" in head[:1024]


def _sniff_mp4(head: bytes) -> bool:
    return len(head) >= 12 and head[4:8] == b"ftyp"


def _sniff_webm(head: bytes) -> bool:
    return head.startswith(b"\x1a\x45\xdf\xa3")


def _sniff_mp3(head: bytes) -> bool:
    if head.startswith(b"ID3"):
        return True
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0


def _zip_with_prefix(prefix: str) -> Callable[[Path], bool]:
    def check(path: Path) -> bool:
        # Reads only the zip central directory; nothing is extracted, so a
        # zip bomb cannot expand here.
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        except (zipfile.BadZipFile, OSError):
            return False
        return "[Content_Types].xml" in names and any(n.startswith(prefix) for n in names)

    return check


@dataclass(frozen=True)
class _Spec:
    media_type: str
    head_check: Callable[[bytes], bool] | None = None
    file_check: Callable[[Path], bool] | None = None
    text: bool = False


ALLOWED_TYPES: dict[str, _Spec] = {
    "pdf": _Spec("application/pdf", head_check=_sniff_pdf),
    "pptx": _Spec(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        head_check=lambda h: h.startswith(b"PK\x03\x04"),
        file_check=_zip_with_prefix("ppt/"),
    ),
    "docx": _Spec(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        head_check=lambda h: h.startswith(b"PK\x03\x04"),
        file_check=_zip_with_prefix("word/"),
    ),
    "txt": _Spec("text/plain; charset=utf-8", text=True),
    "md": _Spec("text/markdown; charset=utf-8", text=True),
    "mp4": _Spec("video/mp4", head_check=_sniff_mp4),
    "webm": _Spec("video/webm", head_check=_sniff_webm),
    "mp3": _Spec("audio/mpeg", head_check=_sniff_mp3),
}


def allowed_extensions() -> tuple[str, ...]:
    return tuple(ALLOWED_TYPES)


def media_type_for(extension: str) -> str | None:
    spec = ALLOWED_TYPES.get(extension)
    return spec.media_type if spec else None


# ---------------------------------------------------------------- settings


def storage_dir() -> Path:
    configured = os.getenv("CONTENT_LIBRARY_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "content_library"


def max_upload_bytes() -> int:
    raw = os.getenv("CONTENT_LIBRARY_MAX_BYTES")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_MAX_BYTES


# ---------------------------------------------------------------- filenames


def split_extension(filename: str) -> str:
    """Lower-cased extension (no dot) of the last path component, or ''."""
    base = re.split(r"[\\/]", filename)[-1]
    _, dot, ext = base.rpartition(".")
    return ext.lower() if dot else ""


def sanitize_display_name(filename: str | None) -> str:
    """Make a client filename safe to STORE AND DISPLAY. The result is never
    used to build a filesystem path. Strips directory components, control /
    format / private-use characters (NUL, CR/LF, bidi overrides) and
    characters that are significant in headers or markup, then bounds the
    length while preserving the extension."""
    name = unicodedata.normalize("NFKC", filename or "")
    name = re.split(r"[\\/]", name)[-1]
    name = "".join(ch for ch in name if not unicodedata.category(ch).startswith("C"))
    name = re.sub(r'[<>:"|?*;\x7f]', "_", name).strip().strip(".")
    if not name:
        return "upload"
    if len(name) > _MAX_DISPLAY_NAME:
        stem, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 8:
            name = stem[: _MAX_DISPLAY_NAME - len(ext) - 1] + "." + ext
        else:
            name = name[:_MAX_DISPLAY_NAME]
    return name


# ---------------------------------------------------------------- paths


def resolve_stored_path(stored_name: str) -> Path | None:
    """Map a stored_name to its on-disk path, or None if it is not a name
    this module could have generated or if it resolves outside the storage
    directory (defence in depth: stored_name comes from our own database)."""
    if not _STORED_NAME_RE.match(stored_name or ""):
        return None
    root = storage_dir().resolve()
    candidate = (root / stored_name).resolve()
    if candidate.parent != root:
        return None
    return candidate


def delete_stored_file(stored_name: str) -> None:
    """Remove a stored file. A file that is already gone counts as success;
    any other failure (permissions, bad name) raises so callers can refuse to
    drop the database row and orphan the bytes silently."""
    path = resolve_stored_path(stored_name)
    if path is None:
        raise StorageError("Invalid stored file name")
    try:
        path.unlink()
    except FileNotFoundError:
        return


# ---------------------------------------------------------------- writing


def store_upload(
    source: BinaryIO,
    original_filename: str | None,
    *,
    max_bytes: int | None = None,
) -> StoredFile:
    """Validate and persist one upload. `source` only needs `.read(n)`."""
    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    display_name = sanitize_display_name(original_filename)
    extension = split_extension(display_name)
    spec = ALLOWED_TYPES.get(extension)
    if spec is None:
        raise UnsupportedTypeError(
            "Unsupported file type. Allowed: " + ", ".join(sorted(ALLOWED_TYPES))
        )

    root = storage_dir()
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{extension}"
    final_path = root / stored_name
    temp_path = root / f".tmp-{uuid.uuid4().hex}"

    digest = hashlib.sha256()
    size = 0
    head = b""
    decoder = codecs.getincrementaldecoder("utf-8")() if spec.text else None
    try:
        with open(temp_path, "xb") as out:
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise FileTooLargeError(
                        f"File exceeds the {limit} byte upload limit"
                    )
                if len(head) < 4096:
                    head = (head + chunk)[:4096]
                if decoder is not None:
                    if b"\x00" in chunk:
                        raise UnsupportedTypeError("File content does not match its type")
                    try:
                        decoder.decode(chunk)
                    except UnicodeDecodeError:
                        raise UnsupportedTypeError(
                            "File content does not match its type"
                        ) from None
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise EmptyFileError("Uploaded file is empty")
        if decoder is not None:
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                raise UnsupportedTypeError("File content does not match its type") from None
        if spec.head_check is not None and not spec.head_check(head):
            raise UnsupportedTypeError("File content does not match its type")
        if spec.file_check is not None and not spec.file_check(temp_path):
            raise UnsupportedTypeError("File content does not match its type")
        os.replace(temp_path, final_path)
    except BaseException:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise

    return StoredFile(
        stored_name=stored_name,
        media_type=spec.media_type,
        size_bytes=size,
        sha256=digest.hexdigest(),
        original_filename=display_name,
    )


# ---------------------------------------------------------------- middleware


class UploadBodyLimitMiddleware:
    """Pure-ASGI guard run BEFORE the multipart body is parsed.

    The framework parses (and spools) the whole multipart body before a
    handler runs, so a handler-side cap alone cannot stop a huge request from
    being buffered. For `POST /learning/library/items` this rejects a missing
    Content-Length (411) or one beyond cap + framing overhead (413) up front.
    The HTTP server enforces that the body matches its declared length, so
    this bound cannot be dodged by lying. The exact per-file cap is still
    enforced while streaming in `store_upload`.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"].rstrip("/") == UPLOAD_PATH
        ):
            length = None
            for name, value in scope.get("headers", []):
                if name == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        length = -1
                    break
            if length is None or length < 0:
                await self._reject(send, 411, "Content-Length is required for uploads")
                return
            if length > max_upload_bytes() + MULTIPART_OVERHEAD_BYTES:
                await self._reject(send, 413, "Upload exceeds the size limit")
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

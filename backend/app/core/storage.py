"""Binary storage for documents.

Files never go into relational tables: the database keeps metadata and a storage key.
Keys are random (not derived from user input) and files are write-once, so a stored
document cannot be replaced in place.
"""

import hashlib
import os
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import BusinessRuleError

# Allowed content types and the magic bytes the file must start with. The declared
# type and extension are not trusted on their own.
ALLOWED: dict[str, tuple[tuple[str, ...], tuple[bytes, ...]]] = {
    "application/pdf": ((".pdf",), (b"%PDF-",)),
    "image/png": ((".png",), (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": ((".jpg", ".jpeg"), (b"\xff\xd8\xff",)),
    "image/webp": ((".webp",), (b"RIFF",)),
    "text/csv": ((".csv",), ()),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ((".xlsx",), (b"PK\x03\x04",)),
}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def detect_type(filename: str, data: bytes) -> str:
    """Return the validated content type or raise ``BusinessRuleError``."""
    ext = os.path.splitext(filename.lower())[1]
    for ctype, (exts, magics) in ALLOWED.items():
        if ext in exts:
            if magics and not any(data.startswith(m) for m in magics):
                break
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                break
            if ctype == "text/csv":
                try:
                    data[:4096].decode("utf-8")
                except UnicodeDecodeError:
                    break
            return ctype
    raise BusinessRuleError(
        "File type not allowed or content does not match its extension",
        code="invalid_file_type",
        details={"allowed": sorted({e for exts, _ in ALLOWED.values() for e in exts})},
    )


def validate_upload(filename: str, data: bytes) -> str:
    limit = get_settings().max_upload_mb * 1024 * 1024
    if not data:
        raise BusinessRuleError("The file is empty", code="empty_file")
    if len(data) > limit:
        raise BusinessRuleError("The file exceeds the maximum size", code="file_too_large",
                                details={"max_mb": get_settings().max_upload_mb})
    return detect_type(filename, data)


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    def put(self, organization_id: uuid.UUID, data: bytes) -> tuple[str, str]:
        """Store bytes; returns (storage_key, sha256)."""
        key = f"{organization_id}/{uuid.uuid4().hex}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "xb") as fh:  # "x": never overwrite
            fh.write(data)
        return key, hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().storage_dir)

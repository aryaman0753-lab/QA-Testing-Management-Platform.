"""Attachment storage boundary; LocalStorage can later be replaced by S3Storage."""
import re
import uuid
from pathlib import Path

from app.common.exceptions import NotFoundError, ValidationAppError

ALLOWED_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def safe_filename(filename: str) -> str:
    name = Path(filename or "").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not name or name in {".", ".."} or len(name) > 255:
        raise ValidationAppError("Invalid attachment filename.")
    return name


def detect_mime(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    expected = ALLOWED_TYPES.get(extension)
    if expected is None:
        raise ValidationAppError("Unsupported file type. Images, text/log files, MP4 and WebM are allowed.")

    signatures = {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        ".webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        ".mp4": len(content) >= 12 and content[4:8] == b"ftyp",
        ".webm": content.startswith(b"\x1a\x45\xdf\xa3"),
    }
    if extension in signatures and not signatures[extension]:
        raise ValidationAppError("The file contents do not match its extension.")
    if extension in {".txt", ".log"}:
        if b"\x00" in content[:8192]:
            raise ValidationAppError("The uploaded text file appears to contain binary data.")
        try:
            content[:8192].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationAppError("Text attachments must be UTF-8 encoded.") from exc
    return expected


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def save(self, bug_id: uuid.UUID, filename: str, content: bytes) -> str:
        relative = Path(str(bug_id)) / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        target = (self.root / relative).resolve()
        if self.root not in target.parents:
            raise ValidationAppError("Invalid attachment path.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative.as_posix()

    def resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents or not target.is_file():
            raise NotFoundError("Attachment file not found.")
        return target

    def delete(self, relative_path: str) -> None:
        try:
            self.resolve(relative_path).unlink(missing_ok=True)
        except NotFoundError:
            pass

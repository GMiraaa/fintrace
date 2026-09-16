from __future__ import annotations

import re
import secrets
import unicodedata
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


async def store_pdf_upload(
    upload: UploadFile,
    *,
    input_dir: Path,
    max_size_bytes: int,
) -> Path:
    original_name = upload.filename or ""
    if not original_name:
        raise _bad_request("A filename is required.")
    if Path(original_name).name != original_name or any(
        separator in original_name for separator in ("/", "\\")
    ):
        raise _bad_request("Invalid filename path.")
    if Path(original_name).suffix.lower() != ".pdf":
        raise _bad_request("Only PDF files are accepted.")
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise _bad_request("File content type must be application/pdf.")

    content = await upload.read(max_size_bytes + 1)
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="PDF exceeds the configured upload size limit.",
        )
    if not content.startswith(b"%PDF-"):
        raise _bad_request("File signature is not a PDF.")

    input_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_filename(original_name)
    destination = _unique_destination(input_dir, safe_name)
    temporary = destination.with_suffix(destination.suffix + ".uploading")
    try:
        with temporary.open("xb") as file:
            file.write(content)
            file.flush()
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _sanitize_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFKD", filename)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(ascii_name).stem)
    stem = stem.strip("._-") or "document"
    return f"{stem[:100]}.pdf"


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    while True:
        suffix = secrets.token_hex(4)
        candidate = directory / f"{stem}_{suffix}.pdf"
        if not candidate.exists():
            return candidate


def _bad_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )

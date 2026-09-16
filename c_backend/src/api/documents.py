from __future__ import annotations

import hashlib
import re
from pathlib import Path

DOCUMENT_ID_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")


def find_pdf_by_document_id(
    input_dir: str | Path,
    document_id: str,
) -> Path | None:
    """Localiza um PDF pela identidade de conteúdo, sem aceitar caminhos externos."""
    match = DOCUMENT_ID_PATTERN.fullmatch(document_id)
    if match is None:
        return None

    expected_digest = match.group(1)
    directory = Path(input_dir).resolve()
    if not directory.is_dir():
        return None

    for candidate in sorted(directory.glob("*.pdf")):
        if candidate.is_file() and _sha256(candidate) == expected_digest:
            return candidate
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

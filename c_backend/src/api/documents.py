from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pymupdf

DOCUMENT_ID_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")


def find_pdf_by_document_id(
    input_dir: str | Path,
    document_id: str,
) -> Path | None:
    """Localiza um PDF pela identidade de conteúdo, sem aceitar caminhos externos."""
    match = DOCUMENT_ID_PATTERN.fullmatch(document_id)
    if match is None:
        return None

    return find_pdf_by_sha256(input_dir, match.group(1))


def find_pdf_by_sha256(
    input_dir: str | Path,
    expected_digest: str,
    *,
    exclude: Path | None = None,
) -> Path | None:
    """Localiza outro PDF pelo hash, opcionalmente ignorando um upload."""
    directory = Path(input_dir).resolve()
    if not directory.is_dir():
        return None

    excluded_path = exclude.resolve() if exclude is not None else None
    for candidate in sorted(directory.glob("*.pdf")):
        if excluded_path is not None and candidate.resolve() == excluded_path:
            continue
        if candidate.is_file() and _sha256(candidate) == expected_digest:
            return candidate
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_first_page_preview(
    pdf_path: str | Path,
    *,
    maximum_width: int = 480,
) -> bytes:
    """Renderiza uma miniatura PNG sem depender do visualizador PDF do browser."""
    path = Path(pdf_path)
    with pymupdf.open(path) as document:
        if document.page_count == 0:
            raise ValueError("PDF contains no pages")
        page = document[0]
        scale = min(maximum_width / max(page.rect.width, 1), 1.5)
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            alpha=False,
            colorspace=pymupdf.csRGB,
        )
        return pixmap.tobytes("png")

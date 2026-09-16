from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pdfplumber

MAX_TEXT_CHARACTERS = 40_000
MAX_WORDS = 2_000


def build_pdfplumber_tools(pdf_path: str | Path) -> list[Callable[..., str]]:
    """Cria tools limitadas ao PDF que está sendo processado."""
    bound_path = Path(pdf_path).resolve()
    if not bound_path.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {bound_path.name}")

    def extract_pdf_text(
        page_start: int = 1,
        page_end: int = 0,
        preserve_layout: bool = True,
    ) -> str:
        """Extrai texto do PDF atual com pdfplumber.

        Args:
            page_start: Primeira página, usando numeração iniciada em 1.
            page_end: Última página inclusiva; use 0 para ir até a página final.
            preserve_layout: Tenta preservar o posicionamento visual do texto.

        Returns:
            JSON com o texto e o número de cada página solicitada.
        """
        with pdfplumber.open(bound_path) as pdf:
            start, end = _validated_range(page_start, page_end, len(pdf.pages))
            pages = []
            remaining = MAX_TEXT_CHARACTERS
            truncated = False
            for page_number in range(start, end + 1):
                text = pdf.pages[page_number - 1].extract_text(
                    layout=preserve_layout
                ) or ""
                if len(text) > remaining:
                    text = text[:remaining]
                    truncated = True
                pages.append({"page": page_number, "text": text})
                remaining -= len(text)
                if remaining <= 0:
                    truncated = page_number < end or truncated
                    break
        return _json_result(
            file_name=bound_path.name,
            pages=pages,
            truncated=truncated,
        )

    def extract_pdf_tables(page_number: int) -> str:
        """Extrai tabelas de uma página do PDF atual com pdfplumber.

        Args:
            page_number: Página desejada, usando numeração iniciada em 1.

        Returns:
            JSON com as tabelas, linhas e células encontradas na página.
        """
        with pdfplumber.open(bound_path) as pdf:
            _validate_page(page_number, len(pdf.pages))
            tables = pdf.pages[page_number - 1].extract_tables()
        normalized = [
            [
                [
                    cell.strip() if isinstance(cell, str) else cell
                    for cell in row
                ]
                for row in table
            ]
            for table in tables
        ]
        return _json_result(
            file_name=bound_path.name,
            page=page_number,
            tables=normalized,
        )

    def inspect_pdf_words(page_number: int) -> str:
        """Inspeciona palavras e coordenadas de uma página do PDF atual.

        Args:
            page_number: Página desejada, usando numeração iniciada em 1.

        Returns:
            JSON com texto e caixa delimitadora das palavras encontradas.
        """
        with pdfplumber.open(bound_path) as pdf:
            _validate_page(page_number, len(pdf.pages))
            extracted = pdf.pages[page_number - 1].extract_words()
        words = [
            {
                "text": word.get("text", ""),
                "x0": word.get("x0"),
                "top": word.get("top"),
                "x1": word.get("x1"),
                "bottom": word.get("bottom"),
            }
            for word in extracted[:MAX_WORDS]
        ]
        return _json_result(
            file_name=bound_path.name,
            page=page_number,
            words=words,
            truncated=len(extracted) > MAX_WORDS,
        )

    return [extract_pdf_text, extract_pdf_tables, inspect_pdf_words]


def _validated_range(start: int, end: int, page_count: int) -> tuple[int, int]:
    effective_end = page_count if end == 0 else end
    _validate_page(start, page_count)
    _validate_page(effective_end, page_count)
    if effective_end < start:
        raise ValueError("page_end deve ser maior ou igual a page_start")
    return start, effective_end


def _validate_page(page_number: int, page_count: int) -> None:
    if page_number < 1 or page_number > page_count:
        raise ValueError(
            f"Página {page_number} inválida; o PDF possui {page_count} página(s)"
        )


def _json_result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

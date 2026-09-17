from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.documents.models import NormalizedDocument
from src.tools.reference import GoldenRecordRepository

from .pdf_tools import build_pdfplumber_tools
from .reference_tool import build_reference_lookup_tool


class CorporateActionToolbox:
    """Centraliza as tools permitidas para a extração de eventos corporativos."""

    def __init__(
        self,
        repository: GoldenRecordRepository,
        *,
        pdf_tools_builder: Callable[
            [str | Path], list[Callable[..., str]]
        ] = build_pdfplumber_tools,
    ) -> None:
        self._reference_lookup = build_reference_lookup_tool(repository)
        self._pdf_tools_builder = pdf_tools_builder

    def tools_for(
        self,
        document: NormalizedDocument,
        *,
        include_pdf_tools: bool = True,
    ) -> list[Callable[..., str]]:
        """Retorna somente as capacidades autorizadas para esta execução."""
        tools: list[Callable[..., str]] = [self._reference_lookup]
        if include_pdf_tools and document.source_path:
            tools.extend(self._pdf_tools_builder(document.source_path))
        return tools

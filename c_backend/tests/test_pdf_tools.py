import json
from pathlib import Path

import pytest

from src.agent.pdf_tools import build_pdfplumber_tools

DATA_DIR = Path(__file__).parents[2] / "a_data/a_input"
SAMPLE_PDF = DATA_DIR / "01_energetica_vale_tiete_dividendo.pdf"


def _tool_named(name: str):
    return next(
        tool for tool in build_pdfplumber_tools(SAMPLE_PDF)
        if tool.__name__ == name
    )


def test_pdf_text_tool_extracts_only_the_requested_pages() -> None:
    payload = json.loads(_tool_named("extract_pdf_text")(1, 1, False))

    assert payload["file_name"] == SAMPLE_PDF.name
    assert [page["page"] for page in payload["pages"]] == [1]
    assert "ENERGÉTICA VALE DO TIETÊ" in payload["pages"][0]["text"]


def test_pdf_table_and_word_tools_return_structured_json() -> None:
    tables = json.loads(_tool_named("extract_pdf_tables")(1))
    words = json.loads(_tool_named("inspect_pdf_words")(1))

    assert tables["page"] == 1
    assert isinstance(tables["tables"], list)
    assert words["page"] == 1
    assert words["words"]
    assert {"text", "x0", "top", "x1", "bottom"} <= words["words"][0].keys()


def test_pdf_tools_reject_pages_outside_the_bound_document() -> None:
    with pytest.raises(ValueError, match="inválida"):
        _tool_named("inspect_pdf_words")(999)


def test_pdf_tools_reject_a_missing_bound_document(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_pdfplumber_tools(tmp_path / "inexistente.pdf")

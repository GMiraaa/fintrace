from pathlib import Path

from src.agent.toolbox import CorporateActionToolbox
from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import ExtractionMethod
from src.models.schemas import ReferenceValidation


class EmptyReferenceRepository:
    def lookup(self, **_kwargs) -> ReferenceValidation:
        return ReferenceValidation()


def document(source_path: str | None = None) -> NormalizedDocument:
    return NormalizedDocument(
        file_name="notice.pdf",
        sha256="a" * 64,
        page_count=1,
        source_path=source_path,
        pages=[
            NormalizedPage(
                page_number=1,
                text="Documento de teste",
                extraction_method=ExtractionMethod.NATIVE_TEXT,
                native_text_length=18,
            )
        ],
    )


def test_toolbox_always_exposes_reference_lookup() -> None:
    toolbox = CorporateActionToolbox(EmptyReferenceRepository())

    tools = toolbox.tools_for(document())

    assert [tool.__name__ for tool in tools] == ["lookup_golden_record"]


def test_toolbox_adds_pdf_tools_when_document_has_source_path(tmp_path: Path) -> None:
    pdf = tmp_path / "notice.pdf"
    pdf.write_bytes(b"pdf")

    def extract_pdf_text() -> str:
        return "texto"

    toolbox = CorporateActionToolbox(
        EmptyReferenceRepository(),
        pdf_tools_builder=lambda path: (
            [extract_pdf_text] if Path(path) == pdf else []
        ),
    )

    tools = toolbox.tools_for(document(str(pdf)))

    assert [tool.__name__ for tool in tools] == [
        "lookup_golden_record",
        "extract_pdf_text",
    ]


def test_toolbox_can_omit_pdf_tools_for_basic_agent(tmp_path: Path) -> None:
    pdf = tmp_path / "notice.pdf"
    pdf.write_bytes(b"pdf")
    toolbox = CorporateActionToolbox(EmptyReferenceRepository())

    tools = toolbox.tools_for(document(str(pdf)), include_pdf_tools=False)

    assert [tool.__name__ for tool in tools] == ["lookup_golden_record"]

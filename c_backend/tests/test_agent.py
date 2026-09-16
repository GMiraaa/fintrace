from pathlib import Path
from types import SimpleNamespace

from src.agent.gemini import GeminiCorporateActionAgent
from src.agent.mapping import extraction_to_document_record
from src.agent.schemas import (
    AgentExtraction,
    ExtractedEvidence,
    ExtractedField,
)
from src.agent.skill_loader import (
    load_corporate_actions_skill,
    load_project_agent_skills,
)
from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import (
    EventType,
    ExtractionMethod,
    FieldStatus,
    Origin,
)


def normalized_document() -> NormalizedDocument:
    return NormalizedDocument(
        file_name="notice.pdf",
        sha256="a" * 64,
        page_count=1,
        pages=[
            NormalizedPage(
                page_number=1,
                text=(
                    "Companhia Alfa S.A. comunica o pagamento de Juros sobre "
                    "o Capital Próprio. Código ALFA3."
                ),
                extraction_method=ExtractionMethod.NATIVE_TEXT,
                native_text_length=95,
            )
        ],
    )


def test_mapping_accepts_only_evidence_present_on_page() -> None:
    extraction = AgentExtraction()
    extraction.issuer.name = ExtractedField[str](
        value="Companhia Alfa S.A.",
        status=FieldStatus.EXTRACTED,
        sources=[
            ExtractedEvidence(page=1, evidence="Companhia Alfa S.A.")
        ],
    )

    record = extraction_to_document_record(extraction, normalized_document())

    assert record.issuer.name.origin is Origin.DOCUMENT
    assert record.issuer.name.sources[0].page == 1


def test_mapping_marks_hallucinated_evidence_as_ambiguous() -> None:
    extraction = AgentExtraction()
    extraction.security.ticker = ExtractedField[str](
        value="FAKE3",
        status=FieldStatus.EXTRACTED,
        sources=[ExtractedEvidence(page=1, evidence="Código FAKE3")],
    )

    record = extraction_to_document_record(extraction, normalized_document())

    assert record.security.ticker.status is FieldStatus.AMBIGUOUS
    assert record.security.ticker.sources == []


def test_gemini_adapter_accepts_parsed_response() -> None:
    extraction = AgentExtraction()
    extraction.corporate_action.event_type = ExtractedField[EventType](
        value=EventType.JCP,
        status=FieldStatus.EXTRACTED,
    )
    response = SimpleNamespace(parsed=extraction, text=None)
    models = SimpleNamespace(generate_content=lambda **_kwargs: response)
    client = SimpleNamespace(models=models)
    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        client=client,
    )

    result = agent.extract(normalized_document())

    assert result.corporate_action.event_type.value is EventType.JCP


def test_gemini_consensus_passes_use_independent_instructions() -> None:
    prompts = []

    def generate_content(**kwargs):
        prompts.append(kwargs["contents"])
        return SimpleNamespace(parsed=AgentExtraction(), text=None)

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        client=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        ),
    )

    agent.extract_for_consensus(normalized_document(), pass_number=1)
    agent.extract_for_consensus(normalized_document(), pass_number=2)

    assert "Build the primary structured extraction" in prompts[0]
    assert "Recheck identifiers, dates, amounts" in prompts[1]


def test_gemini_adapter_exposes_reference_function_calling_tool() -> None:
    received = {}
    response = SimpleNamespace(parsed=AgentExtraction(), text=None)

    def generate_content(**kwargs):
        received.update(kwargs)
        return response

    def lookup_golden_record(isin: str = "") -> str:
        """Consulta um ISIN na base de referência."""
        return isin

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )
    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        reference_lookup_tool=lookup_golden_record,
        client=client,
    )

    agent.extract(normalized_document())

    assert received["config"].tools == [lookup_golden_record]


def test_gemini_adapter_exposes_pdf_tools_bound_to_current_document(
    tmp_path: Path,
) -> None:
    received = {}
    response = SimpleNamespace(parsed=AgentExtraction(), text=None)
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"pdf")
    document = normalized_document().model_copy(
        update={"source_path": str(pdf_path)}
    )

    def generate_content(**kwargs):
        received.update(kwargs)
        return response

    def build_tools(path: str):
        assert path == str(pdf_path)

        def extract_pdf_text(page_start: int = 1) -> str:
            """Extrai texto do PDF atual."""
            return str(page_start)

        return [extract_pdf_text]

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        pdf_tools_builder=build_tools,
        client=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        ),
    )

    agent.extract(document)

    assert [tool.__name__ for tool in received["config"].tools] == [
        "extract_pdf_text"
    ]
    assert "PDFPLUMBER TOOLS" in received["contents"]
    assert "source_path" not in document.model_dump()


def test_strong_agent_requires_pdf_tool_during_escalation(tmp_path: Path) -> None:
    received = {}
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"pdf")
    document = normalized_document().model_copy(
        update={"source_path": str(pdf_path)}
    )

    def extract_pdf_text(page_start: int = 1) -> str:
        return str(page_start)

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="strong-model",
        skill_text="test skill",
        pdf_tools_builder=lambda _path: [extract_pdf_text],
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: (
                    received.update(kwargs)
                    or SimpleNamespace(parsed=AgentExtraction(), text=None)
                )
            )
        ),
    )

    agent.extract_with_context(
        document,
        current=AgentExtraction(),
        unresolved_fields=["issuer.name"],
    )

    assert "call at least one PDFPLUMBER tool" in received["contents"]


def test_skill_loader_includes_required_references() -> None:
    skill_dir = (
        Path(__file__).parents[2] / "d_skills/corporate_actions"
    )

    text = load_corporate_actions_skill(skill_dir)

    assert "Event identification" in text
    assert "Evidence and uncertainty" in text
    assert "tax depends on" in text


def test_project_agent_loads_pdf_extraction_skill() -> None:
    root = Path(__file__).parents[2]

    text = load_project_agent_skills(root)

    assert "Skill de domínio: eventos corporativos" in text
    assert "Skill complementar: extração de PDFs" in text
    assert "PDF Extraction Skill" in text
    assert "pdfplumber" in text
    assert "Handle Scanned PDFs" in text

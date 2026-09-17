from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agent.gemini import (
    AgentProviderError,
    AgentStructuredOutputError,
    GeminiCorporateActionAgent,
    _gemini_response_schema,
)
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
    assert agent.max_remote_calls == 5


def test_agent_schema_avoids_constraints_unsupported_by_gemini_sdk() -> None:
    schema = _gemini_response_schema()

    assert "exclusiveMinimum" not in str(schema)
    assert "additionalProperties" not in str(schema)


def test_gemini_adapter_preserves_sanitized_provider_error_detail() -> None:
    class ProviderFailure(Exception):
        status_code = 400
        message = "invalid request api_key=secret-value"

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kwargs: (_ for _ in ()).throw(
                    ProviderFailure()
                )
            )
        ),
    )

    try:
        agent.extract(normalized_document())
    except AgentProviderError as error:
        message = str(error)
    else:
        raise AssertionError("AgentProviderError was not raised")

    assert "ProviderFailure status=400" in message
    assert "api_key=<redacted>" in message
    assert "secret-value" not in message


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
    requests = []
    lookups = []

    def generate_content(**kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            return SimpleNamespace(
                function_calls=[
                    SimpleNamespace(
                        name="lookup_golden_record",
                        args={"isin": "BRTESTACNOR1"},
                    )
                ]
            )
        return SimpleNamespace(parsed=AgentExtraction(), text=None)

    def lookup_golden_record(isin: str = "") -> str:
        """Consulta um ISIN na base de referência."""
        lookups.append(isin)
        return isin

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )
    toolbox = SimpleNamespace(
        tools_for=lambda _document, **_kwargs: [lookup_golden_record]
    )
    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        toolbox=toolbox,
        client=client,
    )

    agent.extract(normalized_document())

    assert [tool.__name__ for tool in requests[0]["config"].tools] == [
        "lookup_golden_record"
    ]
    assert requests[0]["config"].automatic_function_calling.disable is True
    function_calling = requests[0]["config"].tool_config.function_calling_config
    assert function_calling.mode.value == "ANY"
    assert requests[1]["config"].tools is None
    assert requests[1]["config"].automatic_function_calling is None
    assert lookups == ["BRTESTACNOR1"]
    assert "MUST return function calls" in requests[0]["contents"]
    assert "GOLDEN RECORD FUNCTION RESULTS" in requests[1]["contents"]


def test_gemini_adapter_rejects_response_without_required_reference_call() -> None:
    def lookup_golden_record(isin: str = "") -> str:
        return isin

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        toolbox=SimpleNamespace(
            tools_for=lambda _document, **_kwargs: [lookup_golden_record]
        ),
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kwargs: SimpleNamespace(
                    function_calls=[]
                )
            )
        ),
    )

    with pytest.raises(AgentStructuredOutputError, match="once or twice"):
        agent.extract(normalized_document())


def test_gemini_adapter_accepts_two_reference_calls() -> None:
    requests = []

    def lookup_golden_record(isin: str = "") -> str:
        return isin

    def generate_content(**kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            return SimpleNamespace(
                function_calls=[
                    SimpleNamespace(
                        name="lookup_golden_record",
                        args={"isin": "BRTESTACNOR1"},
                    ),
                    SimpleNamespace(
                        name="lookup_golden_record",
                        args={"isin": "BRTESTACNOR1"},
                    ),
                ]
            )
        return SimpleNamespace(parsed=AgentExtraction(), text=None)

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        toolbox=SimpleNamespace(
            tools_for=lambda _document, **_kwargs: [lookup_golden_record]
        ),
        client=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        ),
    )

    agent.extract(normalized_document())

    assert len(requests) == 2


def test_gemini_adapter_rejects_more_than_two_reference_calls() -> None:
    def lookup_golden_record(isin: str = "") -> str:
        return isin

    def generate_content(**kwargs):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="lookup_golden_record", args={"isin": "A"}
                ),
                SimpleNamespace(
                    name="lookup_golden_record", args={"isin": "B"}
                ),
                SimpleNamespace(
                    name="lookup_golden_record", args={"isin": "C"}
                ),
            ]
        )

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        toolbox=SimpleNamespace(
            tools_for=lambda _document, **_kwargs: [lookup_golden_record]
        ),
        client=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        ),
    )

    with pytest.raises(AgentStructuredOutputError, match="once or twice"):
        agent.extract(normalized_document())


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

    def extract_pdf_text(page_start: int = 1) -> str:
        """Extrai texto do PDF atual."""
        return str(page_start)

    def tools_for(bound_document, *, include_pdf_tools):
        assert bound_document.source_path == str(pdf_path)
        assert include_pdf_tools is True
        return [extract_pdf_text]

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="test-model",
        skill_text="test skill",
        toolbox=SimpleNamespace(tools_for=tools_for),
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


def test_strong_agent_keeps_pdf_tools_optional_during_escalation(
    tmp_path: Path,
) -> None:
    received = {}
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"pdf")
    document = normalized_document().model_copy(
        update={"source_path": str(pdf_path)}
    )

    def extract_pdf_text(page_start: int = 1) -> str:
        return str(page_start)

    toolbox = SimpleNamespace(
        tools_for=lambda _document, **_kwargs: [extract_pdf_text]
    )

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="strong-model",
        skill_text="test skill",
        toolbox=toolbox,
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

    assert "Use these tools only when" in received["contents"]
    assert "call at least one PDFPLUMBER tool" not in received["contents"]
    assert received["config"].automatic_function_calling.maximum_remote_calls == 5


def test_basic_agent_can_disable_pdf_tools(tmp_path: Path) -> None:
    received = {}
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"pdf")
    document = normalized_document().model_copy(
        update={"source_path": str(pdf_path)}
    )

    def tools_for(_document, *, include_pdf_tools):
        assert include_pdf_tools is False
        return []

    agent = GeminiCorporateActionAgent(
        api_key="",
        model="basic-model",
        skill_text="test skill",
        toolbox=SimpleNamespace(tools_for=tools_for),
        include_pdf_tools=False,
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: (
                    received.update(kwargs)
                    or SimpleNamespace(parsed=AgentExtraction(), text=None)
                )
            )
        ),
    )

    agent.extract(document)

    assert received["config"].tools is None
    assert "PDFPLUMBER TOOLS" not in received["contents"]


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

from datetime import date
from decimal import Decimal

from src.agent.cascade import CascadingCorporateActionExtractor
from src.agent.deterministic import PythonCorporateActionExtractor
from src.agent.gemini import AgentProviderError
from src.agent.schemas import AgentExtraction, ExtractedEvidence, ExtractedField
from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import (
    EventType,
    ExtractionAttemptOutcome,
    ExtractionMethod,
    ExtractionStrategy,
    FieldStatus,
)


def document(text: str = "Documento de teste") -> NormalizedDocument:
    return NormalizedDocument(
        file_name="aviso.pdf",
        sha256="a" * 64,
        page_count=1,
        pages=[
            NormalizedPage(
                page_number=1,
                text=text,
                extraction_method=ExtractionMethod.NATIVE_TEXT,
                native_text_length=len(text),
            )
        ],
    )


def field(value, evidence: str = "evidência") -> ExtractedField:
    return ExtractedField(
        value=value,
        status=FieldStatus.EXTRACTED,
        sources=[ExtractedEvidence(page=1, evidence=evidence)],
    )


def sufficient_dividend() -> AgentExtraction:
    extraction = AgentExtraction()
    extraction.issuer.name = field("Companhia Teste S.A.")
    extraction.security.isin = field("BRTESTACNOR1")
    extraction.corporate_action.event_type = field(EventType.DIVIDEND)
    extraction.corporate_action.dates.approval_date = field(date(2026, 1, 5))
    extraction.corporate_action.dates.record_date = field(date(2026, 1, 10))
    extraction.corporate_action.dates.ex_date = field(date(2026, 1, 11))
    extraction.corporate_action.financials.gross_amount_per_share = field(
        Decimal("0.25")
    )
    extraction.corporate_action.financials.currency = field("BRL")
    return extraction


class StaticExtractor:
    def __init__(self, extraction: AgentExtraction, model: str | None = None) -> None:
        self.extraction = extraction
        self.model = model
        self.calls = 0

    def extract(self, _document: NormalizedDocument) -> AgentExtraction:
        self.calls += 1
        return self.extraction.model_copy(deep=True)


class FailingExtractor:
    model = "modelo-indisponível"

    def extract(self, _document: NormalizedDocument) -> AgentExtraction:
        raise AgentProviderError("provider indisponível")


def test_python_extractor_reads_explicit_jcp_fields() -> None:
    text = """BANCO TESTE S.A.
CNPJ/ME nº 60.111.222/0001-55
Juros sobre o Capital Próprio (JCP)
Valor bruto por ação preferencial (PN)
R$ 0,1738420000
Data-base (“data com”)
16/06/2026
Data “ex-JCP”
17/06/2026
Código de negociação
TEST4 (ISIN BRTESTACNPR2)
"""

    extraction = PythonCorporateActionExtractor().extract(document(text))

    assert extraction.corporate_action.event_type.value is EventType.JCP
    assert extraction.issuer.cnpj.value == "60.111.222/0001-55"
    assert extraction.security.ticker.value == "TEST4"
    assert extraction.corporate_action.dates.record_date.value == date(2026, 6, 16)
    assert extraction.corporate_action.financials.gross_amount_per_share.value == Decimal(
        "0.1738420000"
    )


def test_python_extractor_reads_narrative_approval_date() -> None:
    text = """BANCO TESTE S.A.
O Conselho de Administração, em reunião realizada em 02 de junho de 2026,
aprovou o pagamento de Juros sobre o Capital Próprio.
"""

    extraction = PythonCorporateActionExtractor().extract(document(text))

    assert extraction.corporate_action.dates.approval_date.value == date(
        2026, 6, 2
    )


def test_approval_date_is_critical_for_cascade() -> None:
    incomplete = sufficient_dividend()
    incomplete.corporate_action.dates.approval_date = ExtractedField()
    basic = StaticExtractor(sufficient_dividend(), model="básico")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(incomplete),
        basic_agent=basic,
    )

    result = cascade.extract(document())

    assert basic.calls == 1
    assert "corporate_action.dates.approval_date" in (
        result.attempts[0].unresolved_fields
    )


def test_cascade_stops_after_sufficient_python_extraction() -> None:
    python = StaticExtractor(sufficient_dividend())
    basic = StaticExtractor(sufficient_dividend(), model="básico")
    strong = StaticExtractor(sufficient_dividend(), model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=basic,
        strong_agent=strong,
    )

    result = cascade.extract(document())

    assert basic.calls == 0
    assert strong.calls == 0
    assert result.attempts[0].strategy is ExtractionStrategy.PYTHON
    assert result.attempts[0].outcome is ExtractionAttemptOutcome.SUFFICIENT


def test_cascade_uses_basic_model_before_strong_model() -> None:
    python = StaticExtractor(AgentExtraction())
    basic = StaticExtractor(sufficient_dividend(), model="básico")
    strong = StaticExtractor(sufficient_dividend(), model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=basic,
        strong_agent=strong,
    )

    result = cascade.extract(document())

    assert basic.calls == 1
    assert strong.calls == 0
    assert [attempt.outcome for attempt in result.attempts] == [
        ExtractionAttemptOutcome.INSUFFICIENT,
        ExtractionAttemptOutcome.SUFFICIENT,
    ]


def test_cascade_reaches_strong_model_when_basic_is_insufficient() -> None:
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=StaticExtractor(AgentExtraction(), model="básico"),
        strong_agent=StaticExtractor(sufficient_dividend(), model="forte"),
    )

    result = cascade.extract(document())

    assert [attempt.strategy for attempt in result.attempts] == [
        ExtractionStrategy.PYTHON,
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.STRONG_LLM,
    ]
    assert result.attempts[-1].outcome is ExtractionAttemptOutcome.SUFFICIENT


def test_cascade_continues_after_basic_provider_error() -> None:
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=FailingExtractor(),
        strong_agent=StaticExtractor(sufficient_dividend(), model="forte"),
    )

    result = cascade.extract(document())

    assert result.attempts[1].outcome is ExtractionAttemptOutcome.ERROR
    assert result.attempts[2].outcome is ExtractionAttemptOutcome.SUFFICIENT

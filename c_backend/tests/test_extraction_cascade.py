from datetime import date
from decimal import Decimal

from src.agent.cascade import CascadingCorporateActionExtractor
from src.agent.deterministic import PythonCorporateActionExtractor
from src.agent.gemini import AgentProviderError, AgentProviderUnavailableError
from src.agent.schemas import AgentExtraction, ExtractedEvidence, ExtractedField
from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import (
    EventType,
    ExtractionAttemptOutcome,
    ExtractionMethod,
    ExtractionStrategy,
    FieldStatus,
)
from src.models.schemas import PreliminaryCheck


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
    extraction.security.ticker = field("TEST3")
    extraction.corporate_action.event_type = field(EventType.DIVIDEND)
    extraction.corporate_action.dates.approval_date = field(date(2026, 1, 5))
    extraction.corporate_action.dates.record_date = field(date(2026, 1, 10))
    extraction.corporate_action.dates.ex_date = field(date(2026, 1, 11))
    extraction.corporate_action.dates.payment_date = field(date(2026, 1, 20))
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
        raise AgentProviderUnavailableError("provider indisponível")


class InvalidRequestExtractor:
    model = "modelo-com-configuração-inválida"

    def extract(self, _document: NormalizedDocument) -> AgentExtraction:
        raise AgentProviderError("requisição inválida")


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
    basic = StaticExtractor(incomplete, model="básico")
    strong = StaticExtractor(sufficient_dividend(), model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=basic,
        strong_agent=strong,
    )

    result = cascade.extract(document())

    assert basic.calls == 2
    assert "corporate_action.dates.approval_date" in (
        result.attempts[0].unresolved_fields
    )


def test_isin_ticker_and_payment_date_are_independently_required() -> None:
    incomplete = sufficient_dividend()
    incomplete.security.ticker = ExtractedField()
    incomplete.corporate_action.dates.payment_date = ExtractedField()

    unresolved = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=StaticExtractor(incomplete, model="básico"),
        strong_agent=StaticExtractor(sufficient_dividend(), model="forte"),
    ).extract(document()).attempts[0].unresolved_fields

    assert "security.ticker" in unresolved
    assert "corporate_action.dates.payment_date" in unresolved


def test_cascade_prioritizes_basic_model_even_when_python_would_succeed() -> None:
    python = StaticExtractor(sufficient_dividend())
    basic = StaticExtractor(sufficient_dividend(), model="básico")
    strong = StaticExtractor(sufficient_dividend(), model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=basic,
        strong_agent=strong,
    )

    result = cascade.extract(document())

    assert basic.calls == 2
    assert strong.calls == 0
    assert python.calls == 0
    assert result.attempts[0].strategy is ExtractionStrategy.BASIC_LLM
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

    assert basic.calls == 2
    assert strong.calls == 0
    assert python.calls == 0
    assert [attempt.outcome for attempt in result.attempts] == [
        ExtractionAttemptOutcome.SUFFICIENT,
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
        ExtractionStrategy.BASIC_LLM,
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

    assert result.attempts[0].outcome is ExtractionAttemptOutcome.ERROR
    assert result.attempts[1].outcome is ExtractionAttemptOutcome.ERROR
    assert result.attempts[2].outcome is ExtractionAttemptOutcome.SUFFICIENT


def test_cascade_uses_python_when_no_model_is_configured() -> None:
    python = StaticExtractor(sufficient_dividend())
    cascade = CascadingCorporateActionExtractor(python_extractor=python)

    result = cascade.extract(document())

    assert python.calls == 1
    assert [attempt.strategy for attempt in result.attempts] == [
        ExtractionStrategy.PYTHON
    ]


def test_cascade_uses_python_when_all_models_are_unavailable() -> None:
    python = StaticExtractor(sufficient_dividend())
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=FailingExtractor(),
        strong_agent=FailingExtractor(),
    )

    result = cascade.extract(document())

    assert python.calls == 1
    assert [attempt.strategy for attempt in result.attempts] == [
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.STRONG_LLM,
        ExtractionStrategy.PYTHON,
    ]


def test_cascade_uses_python_when_all_models_fail_with_non_transient_error() -> None:
    python = StaticExtractor(sufficient_dividend())
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=InvalidRequestExtractor(),
    )

    result = cascade.extract(document())

    assert python.calls == 1
    assert [attempt.strategy for attempt in result.attempts] == [
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.PYTHON,
    ]
    assert result.attempts[0].outcome is ExtractionAttemptOutcome.ERROR
    assert result.attempts[-1].outcome is ExtractionAttemptOutcome.SUFFICIENT


def test_cascade_does_not_hide_valid_but_incomplete_model_response() -> None:
    python = StaticExtractor(sufficient_dividend())
    cascade = CascadingCorporateActionExtractor(
        python_extractor=python,
        basic_agent=StaticExtractor(AgentExtraction(), model="modelo-básico"),
    )

    result = cascade.extract(document())

    assert python.calls == 0
    assert [attempt.strategy for attempt in result.attempts] == [
        ExtractionStrategy.BASIC_LLM,
        ExtractionStrategy.BASIC_LLM,
    ]
    assert all(
        attempt.outcome is ExtractionAttemptOutcome.INSUFFICIENT
        for attempt in result.attempts
    )


class SequenceExtractor:
    model = "modelo-básico"

    def __init__(self, extractions: list[AgentExtraction]) -> None:
        self.extractions = extractions
        self.calls = 0

    def extract(self, _document: NormalizedDocument) -> AgentExtraction:
        extraction = self.extractions[self.calls]
        self.calls += 1
        return extraction.model_copy(deep=True)


def test_disagreement_between_basic_passes_triggers_strong_verdict() -> None:
    first = sufficient_dividend()
    second = sufficient_dividend()
    second.security.ticker = field("OUTR3")
    verdict = sufficient_dividend()
    strong = StaticExtractor(verdict, model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=SequenceExtractor([first, second]),
        strong_agent=strong,
    )

    result = cascade.extract(document())

    assert strong.calls == 1
    assert result.extraction.security.ticker.value == "TEST3"
    assert result.agreement_scores["security.ticker"] == 67
    assert any(
        check.code == "AGENT_CONSENSUS" and not check.passed
        for check in result.preliminary_checks
    )


def test_failed_non_required_preliminary_check_does_not_trigger_strong_model() -> None:
    strong = StaticExtractor(sufficient_dividend(), model="forte")
    cascade = CascadingCorporateActionExtractor(
        python_extractor=StaticExtractor(AgentExtraction()),
        basic_agent=StaticExtractor(sufficient_dividend(), model="básico"),
        strong_agent=strong,
        preliminary_validator=lambda _extraction, _document: [
            PreliminaryCheck(
                code="DATE_COHERENCE",
                passed=False,
                message="Datas incoerentes.",
            )
        ],
    )

    result = cascade.extract(document())

    assert strong.calls == 0
    assert all(
        attempt.strategy is ExtractionStrategy.BASIC_LLM
        for attempt in result.attempts
    )

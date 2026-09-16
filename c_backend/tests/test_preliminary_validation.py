from datetime import date
from decimal import Decimal

from src.agent.preliminary import build_preliminary_validator
from src.agent.schemas import AgentExtraction, ExtractedEvidence, ExtractedField
from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import EventType, ExtractionMethod, FieldStatus
from src.models.schemas import ReferenceRecord
from src.tools.reference import GoldenRecordRepository


def _field(value, evidence: str):
    return ExtractedField(
        value=value,
        status=FieldStatus.EXTRACTED,
        sources=[ExtractedEvidence(page=1, evidence=evidence)],
    )


def _document(*, method: ExtractionMethod = ExtractionMethod.NATIVE_TEXT):
    text = (
        "Companhia Alfa S.A. ISIN BRALFAACNOR1 código ALFA3 dividendos "
        "aprovado em 01/06/2026 data com 16/06/2026 data ex 17/06/2026 "
        "pagamento 14/08/2026 valor R$ 0,17 moeda BRL"
    )
    return NormalizedDocument(
        file_name="notice.pdf",
        sha256="a" * 64,
        page_count=1,
        pages=[
            NormalizedPage(
                page_number=1,
                text=text,
                extraction_method=method,
                native_text_length=0 if method is ExtractionMethod.OCR else len(text),
                ocr_applied=method is ExtractionMethod.OCR,
            )
        ],
    )


def _extraction() -> AgentExtraction:
    extraction = AgentExtraction()
    extraction.issuer.name = _field("Companhia Alfa S.A.", "Companhia Alfa S.A.")
    extraction.security.isin = _field("BRALFAACNOR1", "ISIN BRALFAACNOR1")
    extraction.security.ticker = _field("ALFA3", "código ALFA3")
    action = extraction.corporate_action
    action.event_type = _field(EventType.DIVIDEND, "dividendos")
    action.dates.approval_date = _field(date(2026, 6, 1), "01/06/2026")
    action.dates.record_date = _field(date(2026, 6, 16), "16/06/2026")
    action.dates.ex_date = _field(date(2026, 6, 17), "17/06/2026")
    action.dates.payment_date = _field(date(2026, 8, 14), "14/08/2026")
    action.financials.gross_amount_per_share = _field(Decimal("0.17"), "R$ 0,17")
    action.financials.currency = _field("BRL", "moeda BRL")
    return extraction


def _validator():
    repository = GoldenRecordRepository(
        [
            ReferenceRecord(
                issuer="Companhia Alfa S.A.",
                cnpj="11.111.111/0001-11",
                isin="BRALFAACNOR1",
                ticker="ALFA3",
                share_class="ON",
                listing_segment="Novo Mercado",
                status="ativo",
            )
        ]
    )
    return build_preliminary_validator(repository)


def test_preliminary_validation_approves_grounded_coherent_extraction() -> None:
    checks = _validator()(_extraction(), _document())

    assert all(check.passed for check in checks)


def test_preliminary_validation_detects_evidence_and_reference_failures() -> None:
    extraction = _extraction()
    extraction.security.ticker = _field("OUTR3", "trecho inexistente")

    checks = {check.code: check for check in _validator()(extraction, _document())}

    assert checks["EVIDENCE_GROUNDING"].passed is False
    assert checks["GOLDEN_VALIDATION"].passed is False


def test_preliminary_validation_detects_weak_ocr() -> None:
    document = _document(method=ExtractionMethod.OCR)
    document.pages[0].text = "texto curto"

    checks = {check.code: check for check in _validator()(_extraction(), document)}

    assert checks["OCR_QUALITY"].passed is False


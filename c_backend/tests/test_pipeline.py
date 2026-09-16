import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.agent.schemas import (
    AgentExtraction,
    ExtractedEvidence,
    ExtractedField,
)
from src.documents.preprocessor import DocumentPreprocessor
from src.models.enums import (
    ConfidenceLevel,
    EventType,
    FieldStatus,
    Origin,
    ProcessingStatus,
    TaxTreatment,
)
from src.pipeline.processor import ProcessingPipeline
from src.tools.reference import GoldenRecordRepository

ROOT = Path(__file__).parents[2]
DATA_DIR = ROOT / "a_data/a_input"


class StaticAgent:
    def __init__(self, extraction: AgentExtraction) -> None:
        self.extraction = extraction

    def extract(self, _document):
        return self.extraction.model_copy(deep=True)


def extracted_field(value, evidence: str) -> ExtractedField:
    return ExtractedField(
        value=value,
        status=FieldStatus.EXTRACTED,
        sources=[ExtractedEvidence(page=1, evidence=evidence)],
    )


def jcp_extraction() -> AgentExtraction:
    extraction = AgentExtraction()
    extraction.issuer.name = extracted_field(
        "Banco Meridional do Brasil S.A.",
        "BANCO MERIDIONAL DO BRASIL S.A.",
    )
    extraction.issuer.cnpj = extracted_field(
        "60.111.222/0001-55",
        "CNPJ/ME nº 60.111.222/0001-55",
    )
    extraction.security.isin = extracted_field(
        "BRBMRDACNPR7",
        "ISIN BRBMRDACNPR7",
    )
    extraction.security.ticker = extracted_field("BMRD4", "BMRD4")
    extraction.security.share_class = extracted_field(
        "PN", "ação preferencial"
    )
    action = extraction.corporate_action
    action.event_type = extracted_field(
        EventType.JCP,
        "Juros sobre o Capital Próprio (JCP)",
    )
    action.dates.approval_date = extracted_field(
        date(2026, 6, 2), "02 de junho de 2026"
    )
    action.dates.record_date = extracted_field(
        date(2026, 6, 16), "16 de junho de 2026"
    )
    action.dates.ex_date = extracted_field(
        date(2026, 6, 17), "17 de junho de 2026"
    )
    action.dates.payment_date = extracted_field(
        date(2026, 8, 14), "14/08/2026"
    )
    action.financials.gross_amount_per_share = extracted_field(
        Decimal("0.1738420000"), "R$ 0,1738420000"
    )
    action.financials.net_amount_per_share = extracted_field(
        Decimal("0.1434196500"), "R$ 0,1434196500"
    )
    action.financials.tax_rate_percent = extracted_field(
        Decimal("17.5"), "17,5%"
    )
    action.financials.tax_treatment = extracted_field(
        TaxTreatment.TAX_RULE_UNIFORM,
        "Sobre o valor bruto incidirá Imposto de Renda Retido na Fonte",
    )
    action.financials.currency = extracted_field("BRL", "R$ 0,1738420000")
    return extraction


def pipeline(tmp_path: Path, extraction: AgentExtraction) -> ProcessingPipeline:
    repository = GoldenRecordRepository.from_csv(
        ROOT / "a_data/c_golden_records/golden_records.csv"
    )
    return ProcessingPipeline(
        preprocessor=DocumentPreprocessor(),
        agent=StaticAgent(extraction),
        reference_repository=repository,
        output_dir=tmp_path,
    )


def test_pipeline_processes_and_persists_valid_jcp(tmp_path: Path) -> None:
    processor = pipeline(tmp_path, jcp_extraction())

    record = processor.process_document(
        DATA_DIR / "02_banco_meridional_jcp.pdf"
    )

    assert record.processing_status is ProcessingStatus.ACCEPTED
    assert record.reference_validation.exact_match is True
    assert any(
        item.rule == "FIN_GROSS_NET_TAX_CONSISTENT"
        for item in record.validations
    )
    output = tmp_path / "02_banco_meridional_jcp.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert (
        payload["corporate_action"]["financials"]["gross_amount_per_share"][
            "value"
        ]
        == "0.1738420000"
    )


def test_pipeline_enriches_missing_ticker_from_reference(tmp_path: Path) -> None:
    extraction = jcp_extraction()
    extraction.security.ticker = ExtractedField[str]()
    processor = pipeline(tmp_path, extraction)

    record = processor.process_document(
        DATA_DIR / "02_banco_meridional_jcp.pdf",
        persist=False,
    )

    assert record.security.ticker.value == "BMRD4"
    assert record.security.ticker.origin is Origin.REFERENCE
    assert record.security.ticker.status is FieldStatus.REFERENCE_ENRICHED


def test_failed_rule_reduces_involved_field_confidence(tmp_path: Path) -> None:
    extraction = jcp_extraction()
    extraction.corporate_action.dates.payment_date.value = date(2026, 6, 1)
    extraction.corporate_action.dates.payment_date.sources = [
        ExtractedEvidence(page=1, evidence="02 de junho de 2026")
    ]
    processor = pipeline(tmp_path, extraction)

    record = processor.process_document(
        DATA_DIR / "02_banco_meridional_jcp.pdf",
        persist=False,
    )

    assert record.processing_status is ProcessingStatus.REVIEW_REQUIRED
    assert (
        record.corporate_action.dates.payment_date.confidence
        is ConfidenceLevel.LOW
    )


def test_reference_conflict_marks_field_as_conflict(tmp_path: Path) -> None:
    extraction = jcp_extraction()
    extraction.security.ticker.value = "TIET3"
    extraction.security.ticker.sources = [
        ExtractedEvidence(page=1, evidence="BMRD4")
    ]
    processor = pipeline(tmp_path, extraction)

    record = processor.process_document(
        DATA_DIR / "02_banco_meridional_jcp.pdf",
        persist=False,
    )

    assert record.security.ticker.status is FieldStatus.CONFLICT
    assert record.security.ticker.confidence is ConfidenceLevel.LOW


def test_batch_continues_after_corrupt_pdf(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\nbroken")
    processor = pipeline(tmp_path, jcp_extraction())

    result = processor.process_batch(
        [DATA_DIR / "02_banco_meridional_jcp.pdf", broken]
    )

    assert len(result.records) == 1
    assert result.report.summary.processed == 2
    assert result.report.summary.failed == 1
    assert result.report.documents[-1].exceptions[0].code == "PDF_CORRUPT"
    assert (tmp_path / "broken.json").is_file()
    assert (tmp_path / "exception_report.json").is_file()

from datetime import date

from src.confidence.engine import apply_confidence
from src.models.enums import (
    ExtractionMethod,
    FieldStatus,
    Origin,
)
from src.models.schemas import AuditableField, SourceEvidence

from .factories import valid_document_record


def test_native_explicit_evidence_has_92_percent_confidence() -> None:
    record = apply_confidence(valid_document_record())

    assert record.security.isin.confidence == 92


def test_ocr_evidence_has_78_percent_confidence() -> None:
    record = valid_document_record()
    record.security.isin.sources[0].extraction_method = ExtractionMethod.OCR

    apply_confidence(record)

    assert record.security.isin.confidence == 78


def test_explicit_not_disclosed_has_95_percent_confidence() -> None:
    record = valid_document_record()
    record.corporate_action.dates.payment_date = AuditableField[date](
        value=None,
        status=FieldStatus.NOT_DISCLOSED,
        origin=Origin.DOCUMENT,
        sources=[
            SourceEvidence(
                page=1,
                evidence="A data será oportunamente definida.",
                extraction_method=ExtractionMethod.NATIVE_TEXT,
            )
        ],
    )

    apply_confidence(record)

    assert record.corporate_action.dates.payment_date.confidence == 95


def test_conflict_has_10_percent_confidence() -> None:
    record = valid_document_record()
    record.security.ticker.status = FieldStatus.CONFLICT

    apply_confidence(record)

    assert record.security.ticker.confidence == 10


def test_agent_agreement_contributes_to_field_confidence() -> None:
    record = valid_document_record()

    apply_confidence(record, agreement_scores={"security.isin": 50})

    assert record.security.isin.confidence == 79

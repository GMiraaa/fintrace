from datetime import date

from src.confidence.engine import apply_confidence
from src.models.enums import (
    ConfidenceLevel,
    ExtractionMethod,
    FieldStatus,
    Origin,
)
from src.models.schemas import AuditableField, SourceEvidence

from .factories import valid_document_record


def test_native_explicit_evidence_is_high_confidence() -> None:
    record = apply_confidence(valid_document_record())

    assert record.security.isin.confidence is ConfidenceLevel.HIGH


def test_ocr_evidence_is_medium_confidence() -> None:
    record = valid_document_record()
    record.security.isin.sources[0].extraction_method = ExtractionMethod.OCR

    apply_confidence(record)

    assert record.security.isin.confidence is ConfidenceLevel.MEDIUM


def test_explicit_not_disclosed_is_high_confidence() -> None:
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

    assert (
        record.corporate_action.dates.payment_date.confidence
        is ConfidenceLevel.HIGH
    )


def test_conflict_is_low_confidence() -> None:
    record = valid_document_record()
    record.security.ticker.status = FieldStatus.CONFLICT

    apply_confidence(record)

    assert record.security.ticker.confidence is ConfidenceLevel.LOW

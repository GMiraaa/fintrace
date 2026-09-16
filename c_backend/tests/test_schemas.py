from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.enums import (
    EventType,
    ExtractionMethod,
    FieldStatus,
    Origin,
    ProcessingStatus,
    RatioKind,
)
from src.models.schemas import (
    AuditableField,
    DocumentRecord,
    RatioValue,
    SourceDocument,
    SourceEvidence,
)


def test_auditable_field_serializes_decimal_as_string() -> None:
    field = AuditableField[Decimal](
        value=Decimal("0.1738420000"),
        status=FieldStatus.EXTRACTED,
        origin=Origin.DOCUMENT,
        confidence=95,
    )

    assert '"value":"0.1738420000"' in field.model_dump_json()


def test_auditable_date_uses_iso_8601() -> None:
    field = AuditableField[date](
        value=date(2026, 6, 16),
        status=FieldStatus.EXTRACTED,
        origin=Origin.DOCUMENT,
        confidence=95,
    )

    assert field.model_dump(mode="json")["value"] == "2026-06-16"


def test_not_disclosed_can_have_high_percentage_confidence() -> None:
    field = AuditableField[date](
        value=None,
        status=FieldStatus.NOT_DISCLOSED,
        origin=Origin.DOCUMENT,
        confidence=95,
        sources=[
            SourceEvidence(
                page=1,
                evidence="A data de pagamento será oportunamente definida.",
                extraction_method=ExtractionMethod.NATIVE_TEXT,
            )
        ],
    )

    assert field.value is None
    assert field.confidence == 95


def test_ratio_rejects_zero_values() -> None:
    with pytest.raises(ValidationError):
        RatioValue(
            kind=RatioKind.RESULTING_PER_EXISTING,
            numerator=Decimal("0"),
            denominator=Decimal("10"),
        )


def test_models_reject_unknown_properties() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourceEvidence(
            page=1,
            evidence="Juros sobre o capital próprio",
            extraction_method=ExtractionMethod.NATIVE_TEXT,
            unsupported=True,
        )


def test_minimal_document_record_is_valid() -> None:
    digest = "a" * 64
    record = DocumentRecord(
        document_id=f"sha256:{digest}",
        source_document=SourceDocument(
            file_name="notice.pdf",
            sha256=digest,
            page_count=1,
            extraction_methods=[ExtractionMethod.NATIVE_TEXT],
        ),
        processing_status=ProcessingStatus.ACCEPTED,
    )

    assert record.schema_version == "2.0"
    assert record.corporate_action.event_type.value is None
    assert record.corporate_action.event_type.status is FieldStatus.UNKNOWN


def test_event_type_enum_rejects_uncontrolled_value() -> None:
    with pytest.raises(ValidationError):
        AuditableField[EventType](value="CASH_EVENT")

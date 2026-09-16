from collections.abc import Iterator

from pydantic import BaseModel

from src.models.enums import (
    ConfidenceLevel,
    ExtractionMethod,
    FieldStatus,
    Origin,
    ValidationStatus,
)
from src.models.schemas import AuditableField, DocumentRecord


def apply_confidence(record: DocumentRecord) -> DocumentRecord:
    for field in _walk_auditable_fields(record):
        field.confidence = _calculate_field_confidence(
            field,
            reference_exact_match=record.reference_validation.exact_match,
        )
    return record


def _calculate_field_confidence(
    field: AuditableField,
    *,
    reference_exact_match: bool,
) -> ConfidenceLevel:
    if field.status in {
        FieldStatus.AMBIGUOUS,
        FieldStatus.CONFLICT,
        FieldStatus.UNREADABLE,
        FieldStatus.UNKNOWN,
    }:
        return ConfidenceLevel.LOW

    if any(item.status is ValidationStatus.FAIL for item in field.validation):
        return ConfidenceLevel.LOW

    if field.status is FieldStatus.NOT_APPLICABLE:
        return ConfidenceLevel.HIGH

    if field.status is FieldStatus.NOT_DISCLOSED:
        return ConfidenceLevel.HIGH if field.sources else ConfidenceLevel.MEDIUM

    if field.origin is Origin.REFERENCE:
        return (
            ConfidenceLevel.HIGH
            if reference_exact_match
            else ConfidenceLevel.MEDIUM
        )

    if field.origin is Origin.DERIVED:
        if field.validation and all(
            item.status is ValidationStatus.PASS for item in field.validation
        ):
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM

    if field.origin is Origin.DOCUMENT and field.sources:
        if any(
            source.extraction_method is ExtractionMethod.OCR
            for source in field.sources
        ):
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH

    return ConfidenceLevel.LOW


def _walk_auditable_fields(value: object) -> Iterator[AuditableField]:
    if isinstance(value, AuditableField):
        yield value
        return
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            yield from _walk_auditable_fields(getattr(value, field_name))
    elif isinstance(value, list):
        for item in value:
            yield from _walk_auditable_fields(item)

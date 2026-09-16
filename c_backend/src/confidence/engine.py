from collections.abc import Iterator

from pydantic import BaseModel

from src.models.enums import (
    ExtractionMethod,
    FieldStatus,
    Origin,
    ValidationStatus,
)
from src.models.schemas import AuditableField, DocumentRecord


def apply_confidence(
    record: DocumentRecord,
    *,
    agreement_scores: dict[str, int] | None = None,
) -> DocumentRecord:
    for path, field in _walk_auditable_fields(record):
        field.agent_agreement = (agreement_scores or {}).get(path)
        field.confidence = _calculate_field_confidence(
            field,
            reference_exact_match=record.reference_validation.exact_match,
            agreement=(agreement_scores or {}).get(path),
        )
    return record


def _calculate_field_confidence(
    field: AuditableField,
    *,
    reference_exact_match: bool,
    agreement: int | None,
) -> int:
    if field.status in {
        FieldStatus.AMBIGUOUS,
        FieldStatus.CONFLICT,
        FieldStatus.UNREADABLE,
    }:
        return 10
    if field.status is FieldStatus.UNKNOWN:
        return 0

    if any(item.status is ValidationStatus.FAIL for item in field.validation):
        return 15

    if field.status is FieldStatus.NOT_APPLICABLE:
        quality = 100

    elif field.status is FieldStatus.NOT_DISCLOSED:
        quality = 95 if field.sources else 60
    elif field.origin is Origin.REFERENCE:
        quality = 95 if reference_exact_match else 75
    elif field.origin is Origin.DERIVED:
        if field.validation and all(
            item.status is ValidationStatus.PASS for item in field.validation
        ):
            quality = 95
        else:
            quality = 75
    elif field.origin is Origin.DOCUMENT and field.sources:
        if any(
            source.extraction_method is ExtractionMethod.OCR
            for source in field.sources
        ):
            quality = 78
        else:
            quality = 92
    else:
        quality = 20

    if agreement is None or field.origin is not Origin.DOCUMENT:
        return quality
    return round(quality * 0.7 + agreement * 0.3)


def _walk_auditable_fields(
    value: object,
    prefix: str = "",
) -> Iterator[tuple[str, AuditableField]]:
    if isinstance(value, AuditableField):
        yield prefix, value
        return
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            path = f"{prefix}.{field_name}" if prefix else field_name
            yield from _walk_auditable_fields(getattr(value, field_name), path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            yield from _walk_auditable_fields(item, path)

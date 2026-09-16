from src.confidence import apply_confidence, calculate_document_confidence
from src.models.enums import FieldStatus

from .factories import valid_document_record


def test_document_confidence_averages_material_field_percentages() -> None:
    record = valid_document_record()
    apply_confidence(record)

    confidence = calculate_document_confidence(record)

    assert confidence.score == 92
    assert confidence.completion_percentage == 100
    assert confidence.missing_fields == []


def test_document_confidence_lists_missing_material_fields() -> None:
    record = valid_document_record()
    record.corporate_action.dates.approval_date.value = None
    record.corporate_action.dates.approval_date.status = FieldStatus.UNKNOWN
    record.corporate_action.dates.approval_date.sources = []
    apply_confidence(record)

    confidence = calculate_document_confidence(record)

    assert confidence.score < 100
    assert confidence.completion_percentage < 100
    assert "corporate_action.dates.approval_date" in confidence.missing_fields

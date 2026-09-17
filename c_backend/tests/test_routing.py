from datetime import date

from src.confidence.engine import apply_confidence
from src.models.enums import (
    ExceptionCategory,
    ExtractionAttemptOutcome,
    ExtractionStrategy,
    FieldStatus,
    Origin,
    ProcessingStatus,
    ValidationStatus,
)
from src.models.schemas import AuditableField, ExtractionAttempt, ValidationResult
from src.routing.report import build_exception_report
from src.routing.router import route_for_review

from .factories import valid_document_record


def test_valid_record_is_automatically_accepted() -> None:
    record = valid_document_record()
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.ACCEPTED
    assert record.review.required is False


def test_not_disclosed_payment_routes_to_follow_up_not_review() -> None:
    record = valid_document_record()
    record.corporate_action.dates.payment_date = AuditableField[date](
        value=None,
        status=FieldStatus.NOT_DISCLOSED,
        origin=Origin.DOCUMENT,
        sources=record.corporate_action.dates.record_date.sources,
    )
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.PENDING_INFORMATION
    assert record.review.required is False
    assert record.follow_up.required is True
    assert record.follow_up.reasons[0].category is ExceptionCategory.BUSINESS_EXCEPTION


def test_failed_date_rule_requires_review() -> None:
    record = valid_document_record()
    record.validations.append(
        ValidationResult(
            rule="DATE_PAYMENT_BEFORE_RECORD",
            status=ValidationStatus.FAIL,
            message="Payment date occurs before record date.",
        )
    )
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.REVIEW_REQUIRED
    assert any(
        reason.code == "DATE_SEQUENCE_INCONSISTENT"
        for reason in record.review.reasons
    )


def test_reference_conflict_requires_review() -> None:
    record = valid_document_record()
    record.reference_validation.conflicts.append(
        {
            "code": "REF_TICKER_CONFLICT",
            "field": "ticker",
            "expected": "ALFA3",
            "observed": "BETA4",
        }
    )
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.REVIEW_REQUIRED
    assert any(
        reason.code == "REFERENCE_IDENTIFIER_CONFLICT"
        for reason in record.review.reasons
    )


def test_exhausted_extraction_cascade_requires_review() -> None:
    record = valid_document_record()
    record.extraction_attempts = [
        ExtractionAttempt(
            strategy=ExtractionStrategy.STRONG_LLM,
            outcome=ExtractionAttemptOutcome.INSUFFICIENT,
            model="modelo-forte",
            unresolved_fields=["corporate_action.event_type"],
        )
    ]
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.REVIEW_REQUIRED
    assert any(
        reason.code == "EXTRACTION_CASCADE_EXHAUSTED"
        for reason in record.review.reasons
    )


def test_failed_optional_escalation_does_not_force_review() -> None:
    record = valid_document_record()
    record.extraction_attempts = [
        ExtractionAttempt(
            strategy=ExtractionStrategy.STRONG_LLM,
            outcome=ExtractionAttemptOutcome.ERROR,
            model="modelo-forte",
            unresolved_fields=[],
            error="provider indisponível",
        )
    ]
    apply_confidence(record)

    route_for_review(record)

    assert record.processing_status is ProcessingStatus.ACCEPTED
    assert all(
        reason.code != "EXTRACTION_CASCADE_EXHAUSTED"
        for reason in record.review.reasons
    )


def test_exception_report_counts_routes() -> None:
    accepted = valid_document_record()
    apply_confidence(accepted)
    route_for_review(accepted)

    pending = valid_document_record()
    pending.document_id = f"sha256:{'b' * 64}"
    pending.corporate_action.dates.payment_date.status = FieldStatus.NOT_DISCLOSED
    pending.corporate_action.dates.payment_date.value = None
    apply_confidence(pending)
    route_for_review(pending)

    report = build_exception_report([accepted, pending])

    assert report.summary.processed == 2
    assert report.summary.accepted == 1
    assert report.summary.pending_information == 1

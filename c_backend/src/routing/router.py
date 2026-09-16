from src.confidence import calculate_document_confidence
from src.models.enums import (
    ConfidenceLevel,
    EventType,
    ExceptionCategory,
    ExtractionAttemptOutcome,
    FieldStatus,
    ProcessingStatus,
    ValidationStatus,
)
from src.models.schemas import DocumentRecord, RoutingReason


def route_for_review(record: DocumentRecord) -> DocumentRecord:
    if not record.document_confidence.required_fields:
        record.document_confidence = calculate_document_confidence(record)
    review_reasons: list[RoutingReason] = []
    follow_up_reasons: list[RoutingReason] = []

    if (
        record.extraction_attempts
        and record.extraction_attempts[-1].outcome
        is not ExtractionAttemptOutcome.SUFFICIENT
    ):
        review_reasons.append(
            _reason(
                "EXTRACTION_CASCADE_EXHAUSTED",
                ExceptionCategory.REVIEW_EXCEPTION,
                "The extraction cascade ended with unresolved critical fields.",
            )
        )

    if record.corporate_action.event_type.value in {None, EventType.UNKNOWN}:
        review_reasons.append(
            _reason(
                "EVENT_CLASSIFICATION_AMBIGUOUS",
                ExceptionCategory.REVIEW_EXCEPTION,
                "The corporate action type could not be determined.",
            )
        )

    if record.corporate_action.classification_conflicts:
        review_reasons.append(
            _reason(
                "TITLE_BODY_CLASSIFICATION_CONFLICT",
                ExceptionCategory.REVIEW_EXCEPTION,
                "Material classification evidence is contradictory.",
            )
        )

    if record.document_confidence.score < 75:
        review_reasons.append(
            _reason(
                "DOCUMENT_CONFIDENCE_LOW",
                ExceptionCategory.REVIEW_EXCEPTION,
                (
                    "Document confidence is below 75%: "
                    f"{record.document_confidence.score}%."
                ),
            )
        )

    if record.reference_validation.reference_record is None:
        review_reasons.append(
            _reason(
                "REFERENCE_NOT_FOUND",
                ExceptionCategory.VALIDATION_EXCEPTION,
                "No golden record could be confirmed for the extracted security.",
            )
        )
    if record.reference_validation.conflicts:
        review_reasons.append(
            _reason(
                "REFERENCE_IDENTIFIER_CONFLICT",
                ExceptionCategory.VALIDATION_EXCEPTION,
                "Extracted identifiers conflict with the golden record.",
            )
        )

    for validation in record.validations:
        if validation.status is not ValidationStatus.FAIL:
            continue
        if validation.rule.startswith("DATE_"):
            review_reasons.append(
                _reason(
                    "DATE_SEQUENCE_INCONSISTENT",
                    ExceptionCategory.VALIDATION_EXCEPTION,
                    validation.message,
                )
            )
        elif validation.rule.startswith("FIN_"):
            review_reasons.append(
                _reason(
                    "FINANCIAL_VALUES_INCONSISTENT",
                    ExceptionCategory.VALIDATION_EXCEPTION,
                    validation.message,
                )
            )

    for name, field in _critical_fields(record):
        if field.status is FieldStatus.UNREADABLE:
            review_reasons.append(
                _reason(
                    "DOCUMENT_PARTIALLY_UNREADABLE",
                    ExceptionCategory.REVIEW_EXCEPTION,
                    f"Critical field is unreadable: {name}.",
                )
            )
        elif field.confidence is ConfidenceLevel.LOW:
            review_reasons.append(
                _reason(
                    "CRITICAL_FIELD_LOW_CONFIDENCE",
                    ExceptionCategory.REVIEW_EXCEPTION,
                    f"Critical field has low confidence: {name}.",
                )
            )

    payment = record.corporate_action.dates.payment_date
    if payment.status is FieldStatus.NOT_DISCLOSED:
        follow_up_reasons.append(
            _reason(
                "PAYMENT_DATE_NOT_DISCLOSED",
                ExceptionCategory.BUSINESS_EXCEPTION,
                "The issuer states that the payment date will be disclosed later.",
            )
        )

    record.review.required = bool(review_reasons)
    record.review.reasons = _deduplicate(review_reasons)
    record.follow_up.required = bool(follow_up_reasons)
    record.follow_up.reasons = _deduplicate(follow_up_reasons)
    record.exceptions = [*record.review.reasons, *record.follow_up.reasons]

    if record.review.required:
        record.processing_status = ProcessingStatus.REVIEW_REQUIRED
    elif record.follow_up.required:
        record.processing_status = ProcessingStatus.PENDING_INFORMATION
    else:
        record.processing_status = ProcessingStatus.ACCEPTED
    return record


def _critical_fields(record: DocumentRecord) -> list[tuple]:
    fields = [
        ("issuer.name", record.issuer.name),
        ("security.isin", record.security.isin),
        ("security.ticker", record.security.ticker),
        ("corporate_action.event_type", record.corporate_action.event_type),
        ("dates.approval_date", record.corporate_action.dates.approval_date),
        ("dates.record_date", record.corporate_action.dates.record_date),
        ("dates.ex_date", record.corporate_action.dates.ex_date),
    ]
    event_type = record.corporate_action.event_type.value
    if event_type in {EventType.DIVIDEND, EventType.JCP}:
        fields.append(
            (
                "financials.gross_amount_per_share",
                record.corporate_action.financials.gross_amount_per_share,
            )
        )
    if event_type in {
        EventType.BONUS_SHARES,
        EventType.STOCK_SPLIT,
        EventType.REVERSE_SPLIT,
    }:
        fields.append(
            ("financials.ratio", record.corporate_action.financials.ratio)
        )
    return fields


def _reason(
    code: str,
    category: ExceptionCategory,
    message: str,
) -> RoutingReason:
    return RoutingReason(code=code, category=category, message=message)


def _deduplicate(reasons: list[RoutingReason]) -> list[RoutingReason]:
    unique: dict[tuple[str, str], RoutingReason] = {}
    for reason in reasons:
        unique[(reason.code, reason.message)] = reason
    return list(unique.values())

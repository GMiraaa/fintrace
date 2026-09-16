from src.models.enums import EventType, FieldStatus, ValidationStatus
from src.models.schemas import CorporateAction, ValidationResult


def validate_event_rules(action: CorporateAction) -> list[ValidationResult]:
    event_type = action.event_type.value
    results: list[ValidationResult] = []

    if event_type in {None, EventType.UNKNOWN}:
        results.append(
            ValidationResult(
                rule="EVENT_UNKNOWN",
                status=ValidationStatus.FAIL,
                message="The corporate action type could not be determined.",
                expected="A supported event type or OTHER",
                observed=event_type.value if event_type is not None else None,
            )
        )
        return results

    if action.classification_conflicts:
        results.append(
            ValidationResult(
                rule="EVENT_CLASSIFICATION_CONFLICT",
                status=ValidationStatus.FAIL,
                message="Material classification signals contradict one another.",
                expected="Consistent classification evidence",
                observed=[
                    conflict.description
                    for conflict in action.classification_conflicts
                ],
            )
        )
    else:
        results.append(
            ValidationResult(
                rule="EVENT_CLASSIFICATION_SUPPORTED",
                status=ValidationStatus.PASS,
                message="No material classification conflict was reported.",
                expected=event_type.value,
                observed=event_type.value,
            )
        )

    required_fields = _required_fields(action, event_type)
    for name, field in required_fields:
        if field.value is None and field.status not in {
            FieldStatus.NOT_DISCLOSED,
            FieldStatus.NOT_APPLICABLE,
        }:
            results.append(
                ValidationResult(
                    rule="EVENT_REQUIRED_FIELD_MISSING",
                    status=ValidationStatus.FAIL,
                    message=f"Required field is missing for {event_type.value}: {name}.",
                    expected=name,
                    observed=None,
                )
            )

    return results


def _required_fields(action: CorporateAction, event_type: EventType) -> list[tuple]:
    dates = action.dates
    financials = action.financials
    common_dates = [
        ("record_date", dates.record_date),
        ("ex_date", dates.ex_date),
    ]

    if event_type in {EventType.DIVIDEND, EventType.JCP}:
        return [
            *common_dates,
            ("gross_amount_per_share", financials.gross_amount_per_share),
            ("currency", financials.currency),
        ]
    if event_type is EventType.BONUS_SHARES:
        return [
            *common_dates,
            ("ratio", financials.ratio),
        ]
    if event_type in {EventType.STOCK_SPLIT, EventType.REVERSE_SPLIT}:
        return [
            ("record_date", dates.record_date),
            ("ratio", financials.ratio),
        ]
    return []

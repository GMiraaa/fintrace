from src.models.enums import EventType, FieldStatus, ValidationStatus
from src.models.schemas import EventDates, ValidationResult


def validate_dates(event_type: EventType, dates: EventDates) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    approval = dates.approval_date.value
    record = dates.record_date.value
    ex_date = dates.ex_date.value
    payment = dates.payment_date.value

    if approval is not None and record is not None:
        results.append(
            _ordered_result(
                rule="DATE_APPROVAL_AFTER_RECORD",
                valid=approval <= record,
                expected="approval_date <= record_date",
                observed=f"{approval.isoformat()} > {record.isoformat()}",
                success_message="Approval date is not after the record date.",
                failure_message="Approval date occurs after the record date.",
            )
        )

    if record is not None and ex_date is not None:
        results.append(
            _ordered_result(
                rule="DATE_RECORD_NOT_BEFORE_EX",
                valid=record < ex_date,
                expected="record_date < ex_date",
                observed=f"{record.isoformat()} / {ex_date.isoformat()}",
                success_message="Record date occurs before the ex-date.",
                failure_message="Record date must occur before the ex-date.",
            )
        )

    if event_type in {EventType.DIVIDEND, EventType.JCP}:
        if dates.payment_date.status is FieldStatus.NOT_DISCLOSED:
            results.append(
                ValidationResult(
                    rule="DATE_PAYMENT_NOT_DISCLOSED",
                    status=ValidationStatus.WARN,
                    message="The issuer explicitly states that payment date is not disclosed.",
                    expected="A disclosed payment date",
                    observed=None,
                )
            )
        elif record is not None and payment is not None:
            results.append(
                _ordered_result(
                    rule="DATE_PAYMENT_BEFORE_RECORD",
                    valid=payment >= record,
                    expected="payment_date >= record_date",
                    observed=f"{payment.isoformat()} / {record.isoformat()}",
                    success_message="Payment date is not before the record date.",
                    failure_message="Payment date occurs before the record date.",
                )
            )

    return results


def _ordered_result(
    *,
    rule: str,
    valid: bool,
    expected: str,
    observed: str,
    success_message: str,
    failure_message: str,
) -> ValidationResult:
    return ValidationResult(
        rule=rule,
        status=ValidationStatus.PASS if valid else ValidationStatus.FAIL,
        message=success_message if valid else failure_message,
        expected=expected,
        observed=observed,
    )

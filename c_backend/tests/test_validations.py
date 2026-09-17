from datetime import date
from decimal import Decimal

from src.models.enums import (
    EventType,
    FieldStatus,
    Origin,
    RatioKind,
    TaxTreatment,
    ValidationStatus,
)
from src.models.schemas import AuditableField, Financials, RatioValue
from src.tools.dates import validate_dates
from src.tools.event_rules import validate_event_rules
from src.tools.financial import validate_financial_values

from .factories import document_field, valid_document_record


def test_jcp_gross_net_tax_is_consistent() -> None:
    financials = valid_document_record().corporate_action.financials

    results = validate_financial_values(financials)

    result = next(item for item in results if item.rule.startswith("FIN_GROSS"))
    assert result.rule == "FIN_GROSS_NET_TAX_CONSISTENT"
    assert result.status is ValidationStatus.PASS


def test_financial_mismatch_fails() -> None:
    financials = valid_document_record().corporate_action.financials
    financials.net_amount_per_share.value = Decimal("0.1500000000")

    results = validate_financial_values(financials)

    result = next(item for item in results if item.rule.startswith("FIN_GROSS"))
    assert result.rule == "FIN_GROSS_NET_TAX_MISMATCH"
    assert result.status is ValidationStatus.FAIL


def test_beneficiary_dependent_tax_does_not_derive_universal_net() -> None:
    financials = Financials(
        gross_amount_per_share=document_field(Decimal("0.4275")),
        tax_rate_percent=document_field(Decimal("10")),
        tax_treatment=document_field(TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY),
        currency=document_field("BRL"),
    )

    results = validate_financial_values(financials)

    assert financials.net_amount_per_share.value is None
    warning = next(
        item for item in results if item.rule == "FIN_TAX_DEPENDS_ON_BENEFICIARY"
    )
    assert warning.status is ValidationStatus.WARN


def test_beneficiary_dependent_tax_accepts_explicitly_disclosed_net() -> None:
    financials = Financials(
        gross_amount_per_share=document_field(Decimal("0.1738420000")),
        net_amount_per_share=document_field(Decimal("0.1434196500")),
        tax_rate_percent=document_field(Decimal("17.5")),
        tax_treatment=document_field(TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY),
        currency=document_field("BRL"),
    )

    results = validate_financial_values(financials)

    disclosed = next(
        item for item in results if item.rule == "FIN_TAX_CONDITIONAL_NET_DISCLOSED"
    )
    consistency = next(
        item for item in results if item.rule == "FIN_GROSS_NET_TAX_CONSISTENT"
    )
    assert disclosed.status is ValidationStatus.WARN
    assert consistency.status is ValidationStatus.PASS
    assert not any(
        item.rule == "FIN_UNIVERSAL_NET_NOT_APPLICABLE" for item in results
    )


def test_beneficiary_dependent_tax_rejects_derived_net() -> None:
    financials = Financials(
        gross_amount_per_share=document_field(Decimal("0.1738420000")),
        net_amount_per_share=AuditableField(
            value=Decimal("0.1434196500"),
            status=FieldStatus.DERIVED,
            origin=Origin.DERIVED,
        ),
        tax_rate_percent=document_field(Decimal("17.5")),
        tax_treatment=document_field(TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY),
        currency=document_field("BRL"),
    )

    results = validate_financial_values(financials)

    rejected = next(
        item for item in results if item.rule == "FIN_UNIVERSAL_NET_NOT_APPLICABLE"
    )
    assert rejected.status is ValidationStatus.FAIL
    assert not any(
        item.rule == "FIN_TAX_CONDITIONAL_NET_DISCLOSED" for item in results
    )


def test_beneficiary_dependent_tax_checks_disclosed_net_arithmetic() -> None:
    financials = Financials(
        gross_amount_per_share=document_field(Decimal("0.1738420000")),
        net_amount_per_share=document_field(Decimal("0.1500000000")),
        tax_rate_percent=document_field(Decimal("17.5")),
        tax_treatment=document_field(TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY),
        currency=document_field("BRL"),
    )

    results = validate_financial_values(financials)

    mismatch = next(
        item for item in results if item.rule == "FIN_GROSS_NET_TAX_MISMATCH"
    )
    assert mismatch.status is ValidationStatus.FAIL


def test_monetary_value_requires_currency() -> None:
    financials = Financials(
        gross_amount_per_share=document_field(Decimal("1.00")),
    )

    results = validate_financial_values(financials)

    result = next(item for item in results if item.rule == "FIN_CURRENCY_MISSING")
    assert result.status is ValidationStatus.FAIL


def test_ratio_is_validated() -> None:
    financials = Financials(
        ratio=document_field(
            RatioValue(
                kind=RatioKind.RESULTING_PER_EXISTING,
                numerator=Decimal("1"),
                denominator=Decimal("10"),
            )
        )
    )

    results = validate_financial_values(financials)

    assert results[0].rule == "FIN_RATIO_VALID"


def test_invalid_ratio_is_preserved_and_fails_validation() -> None:
    financials = Financials(
        ratio=document_field(
            RatioValue(
                kind=RatioKind.RESULTING_PER_EXISTING,
                numerator=Decimal("0"),
                denominator=Decimal("10"),
            )
        )
    )

    results = validate_financial_values(financials)

    assert results[0].rule == "FIN_RATIO_INVALID"
    assert results[0].status is ValidationStatus.FAIL


def test_payment_before_record_date_fails() -> None:
    record = valid_document_record()
    dates = record.corporate_action.dates
    dates.record_date.value = date(2026, 7, 15)
    dates.payment_date.value = date(2026, 7, 10)

    results = validate_dates(EventType.DIVIDEND, dates)

    result = next(item for item in results if item.rule == "DATE_PAYMENT_BEFORE_RECORD")
    assert result.status is ValidationStatus.FAIL


def test_not_disclosed_payment_is_a_warning() -> None:
    dates = valid_document_record().corporate_action.dates
    dates.payment_date = AuditableField(
        value=None,
        status=FieldStatus.NOT_DISCLOSED,
    )

    results = validate_dates(EventType.JCP, dates)

    result = next(item for item in results if item.rule == "DATE_PAYMENT_NOT_DISCLOSED")
    assert result.status is ValidationStatus.WARN


def test_event_rules_require_ratio_for_reverse_split() -> None:
    action = valid_document_record().corporate_action
    action.event_type = document_field(EventType.REVERSE_SPLIT)

    results = validate_event_rules(action)

    missing = [item.expected for item in results if item.status is ValidationStatus.FAIL]
    assert "ratio" in missing


def test_unknown_event_is_not_forced_into_a_category() -> None:
    action = valid_document_record().corporate_action
    action.event_type = document_field(EventType.UNKNOWN)

    results = validate_event_rules(action)

    assert results[0].rule == "EVENT_UNKNOWN"
    assert results[0].status is ValidationStatus.FAIL

from decimal import Decimal

from src.models.enums import TaxTreatment, ValidationStatus
from src.models.schemas import Financials, ValidationResult

DEFAULT_FINANCIAL_TOLERANCE = Decimal("0.0000005")


def validate_financial_values(
    financials: Financials,
    *,
    tolerance: Decimal = DEFAULT_FINANCIAL_TOLERANCE,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    gross = financials.gross_amount_per_share.value
    net = financials.net_amount_per_share.value
    tax_rate = financials.tax_rate_percent.value
    treatment = financials.tax_treatment.value

    if treatment is TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY:
        results.append(
            ValidationResult(
                rule="FIN_TAX_DEPENDS_ON_BENEFICIARY",
                status=ValidationStatus.WARN,
                message=(
                    "Tax depends on beneficiary conditions; a universal net amount "
                    "must not be derived."
                ),
                expected=None,
                observed=str(net) if net is not None else None,
            )
        )
        if net is not None:
            results.append(
                ValidationResult(
                    rule="FIN_UNIVERSAL_NET_NOT_APPLICABLE",
                    status=ValidationStatus.FAIL,
                    message=(
                        "A universal net amount is incompatible with beneficiary-"
                        "dependent taxation unless explicitly qualified."
                    ),
                    expected=None,
                    observed=str(net),
                )
            )
    elif gross is not None and net is not None and tax_rate is not None:
        expected_net = gross * (Decimal("1") - tax_rate / Decimal("100"))
        difference = abs(net - expected_net)
        valid = difference <= tolerance
        results.append(
            ValidationResult(
                rule=(
                    "FIN_GROSS_NET_TAX_CONSISTENT"
                    if valid
                    else "FIN_GROSS_NET_TAX_MISMATCH"
                ),
                status=ValidationStatus.PASS if valid else ValidationStatus.FAIL,
                message=(
                    "Gross, tax rate, and net amount are mathematically consistent."
                    if valid
                    else "Net amount does not match gross amount after tax."
                ),
                expected=str(expected_net),
                observed=str(net),
            )
        )

    has_monetary_value = any(
        value is not None
        for value in (
            gross,
            net,
            financials.attributed_cost_per_share.value,
        )
    )
    if has_monetary_value and financials.currency.value is None:
        results.append(
            ValidationResult(
                rule="FIN_CURRENCY_MISSING",
                status=ValidationStatus.FAIL,
                message="A monetary value was extracted without its currency.",
                expected="ISO 4217 currency code",
                observed=None,
            )
        )

    ratio = financials.ratio.value
    if ratio is not None:
        valid_ratio = ratio.numerator > 0 and ratio.denominator > 0
        results.append(
            ValidationResult(
                rule="FIN_RATIO_VALID" if valid_ratio else "FIN_RATIO_INVALID",
                status=(
                    ValidationStatus.PASS if valid_ratio else ValidationStatus.FAIL
                ),
                message=(
                    "Corporate action ratio is positive."
                    if valid_ratio
                    else "Corporate action ratio must be positive."
                ),
                expected="numerator > 0 and denominator > 0",
                observed=(
                    f"{ratio.numerator}:{ratio.denominator} ({ratio.kind.value})"
                ),
            )
        )

    return results

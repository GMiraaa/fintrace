from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import Field

from src.models.enums import EventType, FieldStatus, RatioKind, TaxTreatment
from src.models.schemas import RatioValue, StrictModel


class ExtractedEvidence(StrictModel):
    page: int = Field(ge=1)
    evidence: str = Field(min_length=1)


T = TypeVar("T")


class ExtractedField(StrictModel, Generic[T]):
    value: T | None = None
    status: FieldStatus = FieldStatus.UNKNOWN
    sources: list[ExtractedEvidence] = Field(default_factory=list)


class ExtractedIssuer(StrictModel):
    name: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    cnpj: ExtractedField[str] = Field(default_factory=ExtractedField[str])


class ExtractedSecurity(StrictModel):
    isin: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    ticker: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    share_class: ExtractedField[str] = Field(default_factory=ExtractedField[str])


class ExtractedDates(StrictModel):
    approval_date: ExtractedField[date] = Field(default_factory=ExtractedField[date])
    record_date: ExtractedField[date] = Field(default_factory=ExtractedField[date])
    ex_date: ExtractedField[date] = Field(default_factory=ExtractedField[date])
    payment_date: ExtractedField[date] = Field(default_factory=ExtractedField[date])
    credit_date: ExtractedField[date] = Field(default_factory=ExtractedField[date])
    fraction_period_start: ExtractedField[date] = Field(
        default_factory=ExtractedField[date]
    )
    fraction_period_end: ExtractedField[date] = Field(
        default_factory=ExtractedField[date]
    )


class ExtractedFinancials(StrictModel):
    gross_amount_per_share: ExtractedField[Decimal] = Field(
        default_factory=ExtractedField[Decimal]
    )
    net_amount_per_share: ExtractedField[Decimal] = Field(
        default_factory=ExtractedField[Decimal]
    )
    tax_rate_percent: ExtractedField[Decimal] = Field(
        default_factory=ExtractedField[Decimal]
    )
    tax_treatment: ExtractedField[TaxTreatment] = Field(
        default_factory=ExtractedField[TaxTreatment]
    )
    currency: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    ratio: ExtractedField[RatioValue] = Field(
        default_factory=ExtractedField[RatioValue]
    )
    attributed_cost_per_share: ExtractedField[Decimal] = Field(
        default_factory=ExtractedField[Decimal]
    )


class ExtractedClassificationSignal(StrictModel):
    supports: EventType
    rationale: str = Field(min_length=1)
    source: ExtractedEvidence


class ExtractedClassificationConflict(StrictModel):
    description: str = Field(min_length=1)
    signals: list[ExtractedClassificationSignal] = Field(min_length=2)


class ExtractedCorporateAction(StrictModel):
    event_type: ExtractedField[EventType] = Field(
        default_factory=ExtractedField[EventType]
    )
    classification_evidence: list[ExtractedClassificationSignal] = Field(
        default_factory=list
    )
    classification_conflicts: list[ExtractedClassificationConflict] = Field(
        default_factory=list
    )
    dates: ExtractedDates = Field(default_factory=ExtractedDates)
    financials: ExtractedFinancials = Field(default_factory=ExtractedFinancials)


class AgentExtraction(StrictModel):
    issuer: ExtractedIssuer = Field(default_factory=ExtractedIssuer)
    security: ExtractedSecurity = Field(default_factory=ExtractedSecurity)
    corporate_action: ExtractedCorporateAction = Field(
        default_factory=ExtractedCorporateAction
    )

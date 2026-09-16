from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import (
    ConfidenceLevel,
    EventType,
    ExceptionCategory,
    ExtractionAttemptOutcome,
    ExtractionMethod,
    ExtractionStrategy,
    FieldStatus,
    Origin,
    ProcessingStatus,
    RatioKind,
    TaxTreatment,
    ValidationStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceEvidence(StrictModel):
    page: int = Field(ge=1)
    evidence: str = Field(min_length=1)
    extraction_method: ExtractionMethod

    @field_validator("evidence")
    @classmethod
    def evidence_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("evidence must not be blank")
        return cleaned


class ValidationResult(StrictModel):
    rule: str = Field(min_length=1)
    status: ValidationStatus
    message: str = Field(min_length=1)
    expected: Any | None = None
    observed: Any | None = None


T = TypeVar("T")


class AuditableField(StrictModel, Generic[T]):
    value: T | None = None
    status: FieldStatus = FieldStatus.UNKNOWN
    origin: Origin = Origin.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    sources: list[SourceEvidence] = Field(default_factory=list)
    validation: list[ValidationResult] = Field(default_factory=list)


class SourceDocument(StrictModel):
    file_name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    extraction_methods: list[ExtractionMethod] = Field(min_length=1)


class Issuer(StrictModel):
    name: AuditableField[str] = Field(default_factory=AuditableField[str])
    cnpj: AuditableField[str] = Field(default_factory=AuditableField[str])


class Security(StrictModel):
    isin: AuditableField[str] = Field(default_factory=AuditableField[str])
    ticker: AuditableField[str] = Field(default_factory=AuditableField[str])
    share_class: AuditableField[str] = Field(default_factory=AuditableField[str])
    listing_segment: AuditableField[str] = Field(default_factory=AuditableField[str])
    asset_status: AuditableField[str] = Field(default_factory=AuditableField[str])


class EventDates(StrictModel):
    approval_date: AuditableField[date] = Field(default_factory=AuditableField[date])
    record_date: AuditableField[date] = Field(default_factory=AuditableField[date])
    ex_date: AuditableField[date] = Field(default_factory=AuditableField[date])
    payment_date: AuditableField[date] = Field(default_factory=AuditableField[date])
    credit_date: AuditableField[date] = Field(default_factory=AuditableField[date])
    fraction_period_start: AuditableField[date] = Field(
        default_factory=AuditableField[date]
    )
    fraction_period_end: AuditableField[date] = Field(
        default_factory=AuditableField[date]
    )


class RatioValue(StrictModel):
    kind: RatioKind
    numerator: Decimal = Field(gt=0)
    denominator: Decimal = Field(gt=0)
    percentage: Decimal | None = Field(default=None, ge=0)


class Financials(StrictModel):
    gross_amount_per_share: AuditableField[Decimal] = Field(
        default_factory=AuditableField[Decimal]
    )
    net_amount_per_share: AuditableField[Decimal] = Field(
        default_factory=AuditableField[Decimal]
    )
    tax_rate_percent: AuditableField[Decimal] = Field(
        default_factory=AuditableField[Decimal]
    )
    tax_treatment: AuditableField[TaxTreatment] = Field(
        default_factory=AuditableField[TaxTreatment]
    )
    currency: AuditableField[str] = Field(default_factory=AuditableField[str])
    ratio: AuditableField[RatioValue] = Field(
        default_factory=AuditableField[RatioValue]
    )
    attributed_cost_per_share: AuditableField[Decimal] = Field(
        default_factory=AuditableField[Decimal]
    )


class ClassificationSignal(StrictModel):
    supports: EventType
    rationale: str = Field(min_length=1)
    source: SourceEvidence


class ClassificationConflict(StrictModel):
    description: str = Field(min_length=1)
    signals: list[ClassificationSignal] = Field(min_length=2)


class CorporateAction(StrictModel):
    event_type: AuditableField[EventType] = Field(
        default_factory=AuditableField[EventType]
    )
    classification_evidence: list[ClassificationSignal] = Field(
        default_factory=list
    )
    classification_conflicts: list[ClassificationConflict] = Field(
        default_factory=list
    )
    dates: EventDates = Field(default_factory=EventDates)
    financials: Financials = Field(default_factory=Financials)


class ReferenceRecord(StrictModel):
    issuer: str
    cnpj: str
    isin: str
    ticker: str
    share_class: str
    listing_segment: str
    status: str


class ReferenceConflict(StrictModel):
    code: str
    field: str
    expected: Any | None = None
    observed: Any | None = None


class ReferenceValidation(StrictModel):
    exact_match: bool = False
    matched_by: list[str] = Field(default_factory=list)
    reference_record: ReferenceRecord | None = None
    conflicts: list[ReferenceConflict] = Field(default_factory=list)
    possible_matches: list[ReferenceRecord] = Field(default_factory=list)


class RoutingReason(StrictModel):
    code: str = Field(min_length=1)
    category: ExceptionCategory
    message: str = Field(min_length=1)


class ExtractionAttempt(StrictModel):
    strategy: ExtractionStrategy
    outcome: ExtractionAttemptOutcome
    model: str | None = None
    unresolved_fields: list[str] = Field(default_factory=list)
    error: str | None = None


class ReviewDecision(StrictModel):
    required: bool = False
    reasons: list[RoutingReason] = Field(default_factory=list)


class FollowUpDecision(StrictModel):
    required: bool = False
    reasons: list[RoutingReason] = Field(default_factory=list)


class DocumentRecord(StrictModel):
    schema_version: str = Field(default="1.0", pattern=r"^1\.0$")
    document_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_document: SourceDocument
    processing_status: ProcessingStatus
    issuer: Issuer = Field(default_factory=Issuer)
    security: Security = Field(default_factory=Security)
    corporate_action: CorporateAction = Field(default_factory=CorporateAction)
    extraction_attempts: list[ExtractionAttempt] = Field(default_factory=list)
    reference_validation: ReferenceValidation = Field(
        default_factory=ReferenceValidation
    )
    validations: list[ValidationResult] = Field(default_factory=list)
    review: ReviewDecision = Field(default_factory=ReviewDecision)
    follow_up: FollowUpDecision = Field(default_factory=FollowUpDecision)
    exceptions: list[RoutingReason] = Field(default_factory=list)


class ExceptionReportSummary(StrictModel):
    processed: int = Field(ge=0)
    accepted: int = Field(ge=0)
    human_review: int = Field(ge=0)
    pending_information: int = Field(ge=0)
    failed: int = Field(ge=0)


class ExceptionReportDocument(StrictModel):
    document_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    file_name: str = Field(min_length=1)
    processing_status: ProcessingStatus
    exceptions: list[RoutingReason] = Field(default_factory=list)


class ExceptionReport(StrictModel):
    schema_version: str = Field(default="1.0", pattern=r"^1\.0$")
    summary: ExceptionReportSummary
    documents: list[ExceptionReportDocument] = Field(default_factory=list)

from __future__ import annotations

from typing import TypeVar

from src.documents.models import NormalizedDocument
from src.models.enums import (
    ConfidenceLevel,
    FieldStatus,
    Origin,
    ProcessingStatus,
)
from src.models.schemas import (
    AuditableField,
    ClassificationConflict,
    ClassificationSignal,
    CorporateAction,
    DocumentRecord,
    EventDates,
    Financials,
    Issuer,
    Security,
    SourceDocument,
    SourceEvidence,
)
from src.tools.normalization import normalize_text

from .schemas import (
    AgentExtraction,
    ExtractedClassificationConflict,
    ExtractedClassificationSignal,
    ExtractedField,
)

T = TypeVar("T")


def extraction_to_document_record(
    extraction: AgentExtraction,
    document: NormalizedDocument,
) -> DocumentRecord:
    action = extraction.corporate_action
    return DocumentRecord(
        document_id=f"sha256:{document.sha256}",
        source_document=SourceDocument(
            file_name=document.file_name,
            sha256=document.sha256,
            page_count=document.page_count,
            extraction_methods=document.extraction_methods,
        ),
        processing_status=ProcessingStatus.ACCEPTED,
        issuer=Issuer(
            name=_map_field(extraction.issuer.name, document),
            cnpj=_map_field(extraction.issuer.cnpj, document),
        ),
        security=Security(
            isin=_map_field(extraction.security.isin, document),
            ticker=_map_field(extraction.security.ticker, document),
            share_class=_map_field(extraction.security.share_class, document),
        ),
        corporate_action=CorporateAction(
            event_type=_map_field(action.event_type, document),
            classification_evidence=[
                mapped
                for signal in action.classification_evidence
                if (mapped := _map_signal(signal, document)) is not None
            ],
            classification_conflicts=[
                mapped
                for conflict in action.classification_conflicts
                if (mapped := _map_conflict(conflict, document)) is not None
            ],
            dates=EventDates(
                approval_date=_map_field(action.dates.approval_date, document),
                record_date=_map_field(action.dates.record_date, document),
                ex_date=_map_field(action.dates.ex_date, document),
                payment_date=_map_field(action.dates.payment_date, document),
                credit_date=_map_field(action.dates.credit_date, document),
                fraction_period_start=_map_field(
                    action.dates.fraction_period_start, document
                ),
                fraction_period_end=_map_field(
                    action.dates.fraction_period_end, document
                ),
            ),
            financials=Financials(
                gross_amount_per_share=_map_field(
                    action.financials.gross_amount_per_share, document
                ),
                net_amount_per_share=_map_field(
                    action.financials.net_amount_per_share, document
                ),
                tax_rate_percent=_map_field(
                    action.financials.tax_rate_percent, document
                ),
                tax_treatment=_map_field(
                    action.financials.tax_treatment, document
                ),
                currency=_map_field(action.financials.currency, document),
                ratio=_map_field(action.financials.ratio, document),
                attributed_cost_per_share=_map_field(
                    action.financials.attributed_cost_per_share, document
                ),
            ),
        ),
    )


def _map_field(
    field: ExtractedField[T],
    document: NormalizedDocument,
) -> AuditableField[T]:
    sources = []
    invalid_evidence = False
    for evidence in field.sources:
        source = _map_evidence(evidence.page, evidence.evidence, document)
        if source is None:
            invalid_evidence = True
        else:
            sources.append(source)

    status = field.status
    if invalid_evidence and not sources:
        status = FieldStatus.AMBIGUOUS

    origin = (
        Origin.DOCUMENT
        if status
        in {
            FieldStatus.EXTRACTED,
            FieldStatus.NOT_DISCLOSED,
            FieldStatus.AMBIGUOUS,
            FieldStatus.CONFLICT,
            FieldStatus.UNREADABLE,
        }
        else Origin.UNKNOWN
    )
    return AuditableField[T](
        value=field.value,
        status=status,
        origin=origin,
        confidence=ConfidenceLevel.LOW,
        sources=sources,
    )


def _map_signal(
    signal: ExtractedClassificationSignal,
    document: NormalizedDocument,
) -> ClassificationSignal | None:
    source = _map_evidence(
        signal.source.page,
        signal.source.evidence,
        document,
    )
    if source is None:
        return None
    return ClassificationSignal(
        supports=signal.supports,
        rationale=signal.rationale,
        source=source,
    )


def _map_conflict(
    conflict: ExtractedClassificationConflict,
    document: NormalizedDocument,
) -> ClassificationConflict | None:
    signals = [
        mapped
        for signal in conflict.signals
        if (mapped := _map_signal(signal, document)) is not None
    ]
    if len(signals) < 2:
        return None
    return ClassificationConflict(
        description=conflict.description,
        signals=signals,
    )


def _map_evidence(
    page_number: int,
    evidence: str,
    document: NormalizedDocument,
) -> SourceEvidence | None:
    page = next(
        (item for item in document.pages if item.page_number == page_number),
        None,
    )
    if page is None:
        return None

    normalized_evidence = normalize_text(evidence)
    normalized_page = normalize_text(page.text)
    if (
        normalized_evidence is None
        or normalized_page is None
        or normalized_evidence not in normalized_page
    ):
        return None

    return SourceEvidence(
        page=page_number,
        evidence=evidence.strip(),
        extraction_method=page.extraction_method,
    )

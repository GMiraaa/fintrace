from __future__ import annotations

from typing import Any

from src.models.enums import ConfidenceLevel, EventType, FieldStatus
from src.models.schemas import AuditableField, DocumentConfidence, DocumentRecord


def calculate_document_confidence(record: DocumentRecord) -> DocumentConfidence:
    """Calcula cobertura e confiança agregada somente sobre campos materiais."""
    requirements = _required_fields(record)
    scores: list[int] = []
    resolved: list[str] = []
    missing: list[str] = []

    for name, field in requirements:
        field_score = _field_score(field)
        scores.append(field_score)
        if field_score > 0:
            resolved.append(name)
        else:
            missing.append(name)

    count = len(requirements)
    completion = round(len(resolved) * 100 / count) if count else 0
    score = round(sum(scores) / count) if count else 0
    return DocumentConfidence(
        score=score,
        completion_percentage=completion,
        required_fields=[name for name, _ in requirements],
        resolved_fields=resolved,
        missing_fields=missing,
        rationale=(
            f"{len(resolved)} de {count} campos materiais foram resolvidos. "
            "O score pondera campos de confiança alta como 100 pontos, média "
            "como 80, baixa como 40 e campos ausentes como zero."
        ),
    )


def _required_fields(
    record: DocumentRecord,
) -> list[tuple[str, AuditableField[Any]]]:
    action = record.corporate_action
    fields: list[tuple[str, AuditableField[Any]]] = [
        ("issuer.name", record.issuer.name),
        ("security.isin", record.security.isin),
        ("security.ticker", record.security.ticker),
        ("corporate_action.event_type", action.event_type),
        ("corporate_action.dates.approval_date", action.dates.approval_date),
    ]
    by_event: dict[EventType, list[tuple[str, AuditableField[Any]]]] = {
        EventType.DIVIDEND: [
            ("corporate_action.dates.record_date", action.dates.record_date),
            ("corporate_action.dates.ex_date", action.dates.ex_date),
            ("corporate_action.dates.payment_date", action.dates.payment_date),
            (
                "corporate_action.financials.gross_amount_per_share",
                action.financials.gross_amount_per_share,
            ),
            ("corporate_action.financials.currency", action.financials.currency),
        ],
        EventType.JCP: [
            ("corporate_action.dates.record_date", action.dates.record_date),
            ("corporate_action.dates.ex_date", action.dates.ex_date),
            ("corporate_action.dates.payment_date", action.dates.payment_date),
            (
                "corporate_action.financials.gross_amount_per_share",
                action.financials.gross_amount_per_share,
            ),
            ("corporate_action.financials.currency", action.financials.currency),
        ],
        EventType.BONUS_SHARES: [
            ("corporate_action.dates.record_date", action.dates.record_date),
            ("corporate_action.dates.ex_date", action.dates.ex_date),
            ("corporate_action.financials.ratio", action.financials.ratio),
        ],
        EventType.STOCK_SPLIT: [
            ("corporate_action.dates.record_date", action.dates.record_date),
            ("corporate_action.financials.ratio", action.financials.ratio),
        ],
        EventType.REVERSE_SPLIT: [
            ("corporate_action.dates.record_date", action.dates.record_date),
            ("corporate_action.financials.ratio", action.financials.ratio),
        ],
    }
    event_type = action.event_type.value
    return [*fields, *by_event.get(event_type, [])]


def _field_score(field: AuditableField[Any]) -> int:
    if field.status is FieldStatus.NOT_APPLICABLE:
        return 100
    resolved = field.value is not None or (
        field.status is FieldStatus.NOT_DISCLOSED and bool(field.sources)
    )
    if not resolved:
        return 0
    return {
        ConfidenceLevel.HIGH: 100,
        ConfidenceLevel.MEDIUM: 80,
        ConfidenceLevel.LOW: 40,
    }[field.confidence]

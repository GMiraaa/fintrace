from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.documents.models import NormalizedDocument
from src.models.enums import (
    EventType,
    ExtractionAttemptOutcome,
    ExtractionStrategy,
    FieldStatus,
)
from src.models.schemas import ExtractionAttempt

from .base import CorporateActionAgent
from .gemini import (
    AgentProviderError,
    AgentProviderUnavailableError,
    AgentStructuredOutputError,
)
from .schemas import AgentExtraction, ExtractedField

UNRESOLVED_STATUSES = {
    FieldStatus.UNKNOWN,
    FieldStatus.AMBIGUOUS,
    FieldStatus.CONFLICT,
    FieldStatus.UNREADABLE,
}


@dataclass(frozen=True)
class ExtractionRun:
    extraction: AgentExtraction
    attempts: list[ExtractionAttempt]


class CascadingCorporateActionExtractor:
    """Prioriza IA e usa Python somente como contingência operacional."""

    def __init__(
        self,
        *,
        python_extractor: CorporateActionAgent,
        basic_agent: CorporateActionAgent | None = None,
        strong_agent: CorporateActionAgent | None = None,
    ) -> None:
        self.python_extractor = python_extractor
        self.basic_agent = basic_agent
        self.strong_agent = strong_agent

    def extract(self, document: NormalizedDocument) -> ExtractionRun:
        agents = [
            (strategy, agent)
            for strategy, agent in (
                (ExtractionStrategy.BASIC_LLM, self.basic_agent),
                (ExtractionStrategy.STRONG_LLM, self.strong_agent),
            )
            if agent is not None
        ]
        if not agents:
            return self._extract_with_python(document, attempts=[])

        extraction = AgentExtraction()
        attempts: list[ExtractionAttempt] = []
        provider_unavailable_for_all_attempts = True
        for strategy, agent in agents:
            model = getattr(agent, "model", None)
            try:
                candidate = (
                    agent.extract(document)
                    if not attempts
                    else _extract_with_context(
                        agent,
                        document,
                        current=extraction,
                    )
                )
                extraction = merge_extractions(extraction, candidate)
                current_attempt = _attempt(strategy, extraction, model=model)
                provider_unavailable_for_all_attempts = False
            except AgentStructuredOutputError as exc:
                provider_unavailable_for_all_attempts = False
                current_attempt = _failed_attempt(
                    strategy,
                    extraction,
                    model=model,
                    error=str(exc),
                )
            except AgentProviderUnavailableError as exc:
                current_attempt = _failed_attempt(
                    strategy,
                    extraction,
                    model=model,
                    error=str(exc),
                )
            except AgentProviderError as exc:
                provider_unavailable_for_all_attempts = False
                current_attempt = _failed_attempt(
                    strategy,
                    extraction,
                    model=model,
                    error=str(exc),
                )
            attempts.append(current_attempt)
            if not current_attempt.unresolved_fields:
                break

        if provider_unavailable_for_all_attempts:
            return self._extract_with_python(document, attempts=attempts)
        return ExtractionRun(extraction=extraction, attempts=attempts)

    def _extract_with_python(
        self,
        document: NormalizedDocument,
        *,
        attempts: list[ExtractionAttempt],
    ) -> ExtractionRun:
        extraction = self.python_extractor.extract(document)
        return ExtractionRun(
            extraction=extraction,
            attempts=[
                *attempts,
                _attempt(ExtractionStrategy.PYTHON, extraction, model=None),
            ],
        )


def assess_unresolved_fields(extraction: AgentExtraction) -> list[str]:
    fields = _field_map(extraction)
    unresolved: list[str] = []

    for path in (
        "issuer.name",
        "security.isin",
        "security.ticker",
        "corporate_action.event_type",
        "corporate_action.dates.approval_date",
    ):
        if not _is_resolved(fields[path]):
            unresolved.append(path)

    event_type = extraction.corporate_action.event_type.value
    required_by_event = {
        EventType.DIVIDEND: (
            "corporate_action.dates.record_date",
            "corporate_action.dates.ex_date",
            "corporate_action.dates.payment_date",
            "corporate_action.financials.gross_amount_per_share",
            "corporate_action.financials.currency",
        ),
        EventType.JCP: (
            "corporate_action.dates.record_date",
            "corporate_action.dates.ex_date",
            "corporate_action.dates.payment_date",
            "corporate_action.financials.gross_amount_per_share",
            "corporate_action.financials.currency",
        ),
        EventType.BONUS_SHARES: (
            "corporate_action.dates.record_date",
            "corporate_action.dates.ex_date",
            "corporate_action.financials.ratio",
        ),
        EventType.STOCK_SPLIT: (
            "corporate_action.dates.record_date",
            "corporate_action.financials.ratio",
        ),
        EventType.REVERSE_SPLIT: (
            "corporate_action.dates.record_date",
            "corporate_action.financials.ratio",
        ),
    }
    for path in required_by_event.get(event_type, ()):
        if not _is_resolved(fields[path]):
            unresolved.append(path)

    return list(dict.fromkeys(unresolved))


def merge_extractions(
    current: AgentExtraction,
    candidate: AgentExtraction,
) -> AgentExtraction:
    merged = current.model_copy(deep=True)
    merged_fields = _field_map(merged)
    candidate_fields = _field_map(candidate)

    for path, target in merged_fields.items():
        source = candidate_fields[path]
        if not _is_present(source):
            continue
        if not _is_present(target) or target.status in {
            FieldStatus.UNKNOWN,
            FieldStatus.AMBIGUOUS,
            FieldStatus.UNREADABLE,
        }:
            _copy_field(target, source)
            continue
        if target.value == source.value and target.status is not FieldStatus.CONFLICT:
            target.sources = _merge_sources(target.sources, source.sources)
            continue
        if source.value is not None and target.value != source.value:
            target.status = FieldStatus.CONFLICT
            target.sources = _merge_sources(target.sources, source.sources)

    evidence = (
        *merged.corporate_action.classification_evidence,
        *candidate.corporate_action.classification_evidence,
    )
    merged.corporate_action.classification_evidence = list(
        {item.model_dump_json(): item for item in evidence}.values()
    )
    merged.corporate_action.classification_conflicts.extend(
        candidate.corporate_action.classification_conflicts
    )
    return merged


def _attempt(
    strategy: ExtractionStrategy,
    extraction: AgentExtraction,
    *,
    model: str | None,
) -> ExtractionAttempt:
    unresolved = assess_unresolved_fields(extraction)
    return ExtractionAttempt(
        strategy=strategy,
        outcome=(
            ExtractionAttemptOutcome.INSUFFICIENT
            if unresolved
            else ExtractionAttemptOutcome.SUFFICIENT
        ),
        model=model,
        unresolved_fields=unresolved,
    )


def _failed_attempt(
    strategy: ExtractionStrategy,
    extraction: AgentExtraction,
    *,
    model: str | None,
    error: str,
) -> ExtractionAttempt:
    return ExtractionAttempt(
        strategy=strategy,
        outcome=ExtractionAttemptOutcome.ERROR,
        model=model,
        unresolved_fields=assess_unresolved_fields(extraction),
        error=error,
    )


def _field_map(extraction: AgentExtraction) -> dict[str, ExtractedField[Any]]:
    action = extraction.corporate_action
    return {
        "issuer.name": extraction.issuer.name,
        "issuer.cnpj": extraction.issuer.cnpj,
        "security.isin": extraction.security.isin,
        "security.ticker": extraction.security.ticker,
        "security.share_class": extraction.security.share_class,
        "corporate_action.event_type": action.event_type,
        "corporate_action.dates.approval_date": action.dates.approval_date,
        "corporate_action.dates.record_date": action.dates.record_date,
        "corporate_action.dates.ex_date": action.dates.ex_date,
        "corporate_action.dates.payment_date": action.dates.payment_date,
        "corporate_action.dates.credit_date": action.dates.credit_date,
        "corporate_action.dates.fraction_period_start": action.dates.fraction_period_start,
        "corporate_action.dates.fraction_period_end": action.dates.fraction_period_end,
        "corporate_action.financials.gross_amount_per_share": action.financials.gross_amount_per_share,
        "corporate_action.financials.net_amount_per_share": action.financials.net_amount_per_share,
        "corporate_action.financials.tax_rate_percent": action.financials.tax_rate_percent,
        "corporate_action.financials.tax_treatment": action.financials.tax_treatment,
        "corporate_action.financials.currency": action.financials.currency,
        "corporate_action.financials.ratio": action.financials.ratio,
        "corporate_action.financials.attributed_cost_per_share": action.financials.attributed_cost_per_share,
    }


def _is_present(field: ExtractedField[Any]) -> bool:
    return field.value is not None or field.status not in {FieldStatus.UNKNOWN}


def _is_resolved(field: ExtractedField[Any]) -> bool:
    if field.status in UNRESOLVED_STATUSES:
        return False
    if field.status in {FieldStatus.NOT_DISCLOSED, FieldStatus.NOT_APPLICABLE}:
        return bool(field.sources) or field.status is FieldStatus.NOT_APPLICABLE
    return field.value is not None and bool(field.sources)


def _copy_field(target: ExtractedField[Any], source: ExtractedField[Any]) -> None:
    copied = source.model_copy(deep=True)
    target.value = copied.value
    target.status = copied.status
    target.sources = copied.sources


def _merge_sources(current: list, candidate: list) -> list:
    unique = {item.model_dump_json(): item for item in (*current, *candidate)}
    return list(unique.values())


def _extract_with_context(
    agent: CorporateActionAgent,
    document: NormalizedDocument,
    *,
    current: AgentExtraction,
) -> AgentExtraction:
    contextual = getattr(agent, "extract_with_context", None)
    if callable(contextual):
        return contextual(
            document,
            current=current,
            unresolved_fields=assess_unresolved_fields(current),
        )
    return agent.extract(document)

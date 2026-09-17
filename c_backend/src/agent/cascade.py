from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.documents.models import NormalizedDocument
from src.models.enums import (
    EventType,
    ExtractionAttemptOutcome,
    ExtractionStrategy,
    FieldStatus,
)
from src.models.schemas import ExtractionAttempt, PreliminaryCheck

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
    preliminary_checks: list[PreliminaryCheck]
    agreement_scores: dict[str, int]


class CascadingCorporateActionExtractor:
    """Prioriza IA e usa Python somente como contingência operacional."""

    def __init__(
        self,
        *,
        python_extractor: CorporateActionAgent,
        basic_agent: CorporateActionAgent | None = None,
        strong_agent: CorporateActionAgent | None = None,
        preliminary_validator: (
            Callable[[AgentExtraction, NormalizedDocument], list[PreliminaryCheck]]
            | None
        ) = None,
        basic_passes: int = 2,
    ) -> None:
        if basic_passes < 2:
            raise ValueError("basic_passes must be at least 2")
        self.python_extractor = python_extractor
        self.basic_agent = basic_agent
        self.strong_agent = strong_agent
        self.preliminary_validator = preliminary_validator
        self.basic_passes = basic_passes

    def extract(self, document: NormalizedDocument) -> ExtractionRun:
        if self.basic_agent is None and self.strong_agent is None:
            return self._extract_with_python(document, attempts=[])

        extraction = AgentExtraction()
        attempts: list[ExtractionAttempt] = []
        responses: list[AgentExtraction] = []
        model_attempts = 0

        if self.basic_agent is not None:
            for _pass_number in range(1, self.basic_passes + 1):
                model_attempts += 1
                model = getattr(self.basic_agent, "model", None)
                try:
                    candidate = _extract_basic_pass(
                        self.basic_agent,
                        document,
                        pass_number=_pass_number,
                    )
                    responses.append(candidate.model_copy(deep=True))
                    extraction = (
                        candidate.model_copy(deep=True)
                        if len(responses) == 1
                        else merge_extractions(extraction, candidate)
                    )
                    current_attempt = _attempt(
                        ExtractionStrategy.BASIC_LLM,
                        extraction,
                        model=model,
                        pass_number=_pass_number,
                    )
                except AgentStructuredOutputError as exc:
                    current_attempt = _failed_attempt(
                        ExtractionStrategy.BASIC_LLM,
                        extraction,
                        model=model,
                        pass_number=_pass_number,
                        error=str(exc),
                    )
                except AgentProviderUnavailableError as exc:
                    current_attempt = _failed_attempt(
                        ExtractionStrategy.BASIC_LLM,
                        extraction,
                        model=model,
                        pass_number=_pass_number,
                        error=str(exc),
                    )
                except AgentProviderError as exc:
                    current_attempt = _failed_attempt(
                        ExtractionStrategy.BASIC_LLM,
                        extraction,
                        model=model,
                        pass_number=_pass_number,
                        error=str(exc),
                    )
                attempts.append(current_attempt)

        preliminary_checks = self._run_preliminary_checks(
            extraction,
            document,
            responses,
        )
        # The strong model is an extraction fallback, not a generic reviewer.
        # Escalate only while a material field required for this event remains
        # unresolved after the two basic passes. Other preliminary findings are
        # retained for audit and handled by deterministic validation/routing.
        needs_strong_model = bool(assess_unresolved_fields(extraction))

        if self.strong_agent is not None and needs_strong_model:
            model_attempts += 1
            model = getattr(self.strong_agent, "model", None)
            try:
                candidate = _extract_with_context(
                    self.strong_agent,
                    document,
                    current=extraction,
                    escalation_reasons=[
                        check.code for check in preliminary_checks if not check.passed
                    ],
                )
                responses.append(candidate.model_copy(deep=True))
                extraction = merge_extractions(
                    extraction,
                    candidate,
                    adjudicate=True,
                )
                current_attempt = _attempt(
                    ExtractionStrategy.STRONG_LLM,
                    extraction,
                    model=model,
                    pass_number=len(attempts) + 1,
                )
            except AgentStructuredOutputError as exc:
                current_attempt = _failed_attempt(
                    ExtractionStrategy.STRONG_LLM,
                    extraction,
                    model=model,
                    pass_number=len(attempts) + 1,
                    error=str(exc),
                )
            except AgentProviderUnavailableError as exc:
                current_attempt = _failed_attempt(
                    ExtractionStrategy.STRONG_LLM,
                    extraction,
                    model=model,
                    pass_number=len(attempts) + 1,
                    error=str(exc),
                )
            except AgentProviderError as exc:
                current_attempt = _failed_attempt(
                    ExtractionStrategy.STRONG_LLM,
                    extraction,
                    model=model,
                    pass_number=len(attempts) + 1,
                    error=str(exc),
                )
            attempts.append(current_attempt)

        # Provider/configuration errors must not turn the entire extraction into
        # an empty record.  Keep every failed LLM attempt for auditability, but
        # use the deterministic extractor whenever no model returned a valid
        # structured response at all.  A valid yet incomplete model response is
        # intentionally not hidden by this fallback and remains reviewable.
        if model_attempts > 0 and not responses:
            return self._extract_with_python(document, attempts=attempts)
        return ExtractionRun(
            extraction=extraction,
            attempts=attempts,
            preliminary_checks=preliminary_checks,
            # Provider failures are operational errors, not disagreements about
            # extracted values. Agreement is calculated only from valid replies.
            agreement_scores=calculate_agreement_scores(responses),
        )

    def _run_preliminary_checks(
        self,
        extraction: AgentExtraction,
        document: NormalizedDocument,
        responses: list[AgentExtraction],
    ) -> list[PreliminaryCheck]:
        unresolved = assess_unresolved_fields(extraction)
        agreement = calculate_agreement_scores(
            responses,
            expected_count=self.basic_passes,
        )
        compared_paths = {
            path
            for response in responses
            for path, field in _field_map(response).items()
            if _is_present(field)
        }
        disagreements = sorted(
            path for path in compared_paths if agreement.get(path, 0) < 100
        )
        checks = [
            PreliminaryCheck(
                code="REQUIRED_FIELDS",
                passed=not unresolved,
                message=(
                    "Todos os campos materiais foram resolvidos."
                    if not unresolved
                    else "Campos materiais pendentes: " + ", ".join(unresolved)
                ),
            ),
            PreliminaryCheck(
                code="AGENT_CONSENSUS",
                passed=len(responses) >= self.basic_passes and not disagreements,
                message=(
                    "As duas extrações básicas concordam nos campos informados."
                    if len(responses) >= self.basic_passes and not disagreements
                    else "Divergência ou ausência de consenso em: "
                    + (", ".join(disagreements) or "respostas básicas insuficientes")
                ),
            ),
        ]
        if self.preliminary_validator is not None and responses:
            checks.extend(self.preliminary_validator(extraction, document))
        return checks

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
                _attempt(
                    ExtractionStrategy.PYTHON,
                    extraction,
                    model=None,
                    pass_number=len(attempts) + 1,
                ),
            ],
            preliminary_checks=[],
            agreement_scores={},
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
    *,
    adjudicate: bool = False,
) -> AgentExtraction:
    merged = current.model_copy(deep=True)
    merged_fields = _field_map(merged)
    candidate_fields = _field_map(candidate)

    for path, target in merged_fields.items():
        source = candidate_fields[path]
        if not _is_present(source):
            continue
        if adjudicate:
            _copy_field(target, source)
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
    pass_number: int | None = None,
) -> ExtractionAttempt:
    unresolved = assess_unresolved_fields(extraction)
    return ExtractionAttempt(
        strategy=strategy,
        outcome=(
            ExtractionAttemptOutcome.INSUFFICIENT
            if unresolved
            else ExtractionAttemptOutcome.SUFFICIENT
        ),
        pass_number=pass_number,
        model=model,
        unresolved_fields=unresolved,
    )


def _failed_attempt(
    strategy: ExtractionStrategy,
    extraction: AgentExtraction,
    *,
    model: str | None,
    pass_number: int | None = None,
    error: str,
) -> ExtractionAttempt:
    return ExtractionAttempt(
        strategy=strategy,
        outcome=ExtractionAttemptOutcome.ERROR,
        pass_number=pass_number,
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
    escalation_reasons: list[str] | None = None,
) -> AgentExtraction:
    contextual = getattr(agent, "extract_with_context", None)
    if callable(contextual):
        return contextual(
            document,
            current=current,
            unresolved_fields=[
                *assess_unresolved_fields(current),
                *(f"preliminary_check:{code}" for code in escalation_reasons or []),
            ],
        )
    return agent.extract(document)


def _extract_basic_pass(
    agent: CorporateActionAgent,
    document: NormalizedDocument,
    *,
    pass_number: int,
) -> AgentExtraction:
    consensus_extract = getattr(agent, "extract_for_consensus", None)
    if callable(consensus_extract):
        return consensus_extract(document, pass_number=pass_number)
    return agent.extract(document)


def calculate_agreement_scores(
    responses: list[AgentExtraction],
    *,
    expected_count: int | None = None,
) -> dict[str, int]:
    if not responses:
        return {}
    scores: dict[str, int] = {}
    for path in _field_map(responses[0]):
        signatures = [
            _field_signature(_field_map(response)[path])
            for response in responses
        ]
        most_common = Counter(signatures).most_common(1)[0][1]
        denominator = max(expected_count or len(signatures), len(signatures))
        scores[path] = round(most_common * 100 / denominator)
    return scores


def _field_signature(field: ExtractedField[Any]) -> str:
    return json.dumps(
        {
            "value": field.model_dump(mode="json")["value"],
            "status": field.status.value,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

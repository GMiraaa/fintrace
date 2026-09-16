from __future__ import annotations

from collections.abc import Callable, Iterator

from pydantic import BaseModel

from src.agent.mapping import extraction_to_document_record
from src.agent.schemas import AgentExtraction
from src.documents.models import NormalizedDocument
from src.models.enums import ExtractionMethod, FieldStatus, Origin, ValidationStatus
from src.models.schemas import AuditableField, PreliminaryCheck
from src.tools.dates import validate_dates
from src.tools.event_rules import validate_event_rules
from src.tools.financial import validate_financial_values
from src.tools.reference import GoldenRecordRepository

PreliminaryValidator = Callable[
    [AgentExtraction, NormalizedDocument],
    list[PreliminaryCheck],
]


def build_preliminary_validator(
    repository: GoldenRecordRepository,
) -> PreliminaryValidator:
    """Monta os checks executados entre o consenso básico e a escalada."""

    def validate(
        extraction: AgentExtraction,
        document: NormalizedDocument,
    ) -> list[PreliminaryCheck]:
        record = extraction_to_document_record(extraction, document)
        reference = repository.lookup(
            issuer=record.issuer.name.value,
            cnpj=record.issuer.cnpj.value,
            isin=record.security.isin.value,
            ticker=record.security.ticker.value,
            share_class=record.security.share_class.value,
        )
        event_type = record.corporate_action.event_type.value
        date_results = (
            validate_dates(event_type, record.corporate_action.dates)
            if event_type is not None
            else []
        )
        financial_results = validate_financial_values(
            record.corporate_action.financials
        )
        event_results = validate_event_rules(record.corporate_action)

        invalid_evidence = [
            path
            for path, field in _walk_fields(record)
            if field.origin is Origin.DOCUMENT
            and field.status
            in {
                FieldStatus.EXTRACTED,
                FieldStatus.NOT_DISCLOSED,
                FieldStatus.AMBIGUOUS,
                FieldStatus.CONFLICT,
                FieldStatus.UNREADABLE,
            }
            and not field.sources
            and field.status is not FieldStatus.UNREADABLE
        ]
        weak_ocr_pages = [
            page.page_number
            for page in document.pages
            if page.extraction_method is ExtractionMethod.OCR
            and (
                bool(page.warnings)
                or sum(character.isalnum() for character in page.text) < 80
            )
        ]
        date_failures = _failed_rules(date_results)
        financial_failures = _failed_rules(financial_results)
        classification_failures = [
            result.rule
            for result in event_results
            if result.status is ValidationStatus.FAIL
            and result.rule in {"EVENT_CLASSIFICATION_CONFLICT", "EVENT_UNKNOWN"}
        ]

        return [
            _check(
                "EVIDENCE_GROUNDING",
                not invalid_evidence,
                "Todas as evidências foram localizadas nas páginas citadas."
                if not invalid_evidence
                else "Evidência não localizada para: " + ", ".join(invalid_evidence),
            ),
            _check(
                "GOLDEN_VALIDATION",
                reference.exact_match and not reference.conflicts,
                "Identidade confirmada sem conflitos na base de referência."
                if reference.exact_match and not reference.conflicts
                else "A identidade não foi confirmada ou diverge da base de referência.",
            ),
            _check(
                "DATE_COHERENCE",
                not date_failures,
                "As relações temporais avaliáveis são coerentes."
                if not date_failures
                else "Falharam as regras: " + ", ".join(date_failures),
            ),
            _check(
                "FINANCIAL_COHERENCE",
                not financial_failures,
                "Os valores financeiros avaliáveis são coerentes."
                if not financial_failures
                else "Falharam as regras: " + ", ".join(financial_failures),
            ),
            _check(
                "CLASSIFICATION_CONSISTENCY",
                not classification_failures,
                "A classificação não apresenta contradições materiais."
                if not classification_failures
                else "Falharam as regras: " + ", ".join(classification_failures),
            ),
            _check(
                "OCR_QUALITY",
                not weak_ocr_pages,
                "As páginas lidas por OCR possuem conteúdo suficiente."
                if not weak_ocr_pages
                else "OCR de baixa qualidade nas páginas: "
                + ", ".join(map(str, weak_ocr_pages)),
            ),
        ]

    return validate


def _failed_rules(results: list) -> list[str]:
    return [
        result.rule
        for result in results
        if result.status is ValidationStatus.FAIL
    ]


def _check(code: str, passed: bool, message: str) -> PreliminaryCheck:
    return PreliminaryCheck(code=code, passed=passed, message=message)


def _walk_fields(
    value: object,
    prefix: str = "",
) -> Iterator[tuple[str, AuditableField]]:
    if isinstance(value, AuditableField):
        yield prefix, value
        return
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            path = f"{prefix}.{name}" if prefix else name
            yield from _walk_fields(getattr(value, name), path)


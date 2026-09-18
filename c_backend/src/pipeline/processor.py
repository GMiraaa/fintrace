from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.agent.base import CorporateActionAgent
from src.agent.cascade import CascadingCorporateActionExtractor, ExtractionRun
from src.agent.gemini import AgentProviderError, AgentStructuredOutputError
from src.agent.mapping import extraction_to_document_record
from src.confidence import apply_confidence, calculate_document_confidence
from src.documents.preprocessor import (
    CorruptPdfError,
    DocumentPreprocessor,
    OcrProcessingError,
)
from src.logging_config import log_event
from src.models.enums import (
    ExceptionCategory,
    FieldStatus,
    Origin,
    ProcessingStatus,
    ValidationStatus,
)
from src.models.schemas import (
    DocumentRecord,
    ExceptionReport,
    ExceptionReportDocument,
    RoutingReason,
    ValidationResult,
)
from src.persistence import ArtifactRepository
from src.routing.report import build_exception_report
from src.routing.router import route_for_review
from src.tools.dates import validate_dates
from src.tools.event_rules import validate_event_rules
from src.tools.financial import validate_financial_values
from src.tools.reference import GoldenRecordRepository
from src.tools.normalization import normalize_text

logger = logging.getLogger(__name__)


class OutputPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BatchProcessingResult:
    records: list[DocumentRecord]
    report: ExceptionReport


class ProcessingPipeline:
    def __init__(
        self,
        *,
        preprocessor: DocumentPreprocessor,
        agent: CorporateActionAgent | CascadingCorporateActionExtractor,
        reference_repository: GoldenRecordRepository,
        output_dir: str | Path,
        artifact_repository: ArtifactRepository | None = None,
    ) -> None:
        self.preprocessor = preprocessor
        self.agent = agent
        self.reference_repository = reference_repository
        self.output_dir = Path(output_dir)
        self.artifact_repository = artifact_repository

    def process_document(
        self,
        path: str | Path,
        *,
        persist: bool = True,
    ) -> DocumentRecord:
        document_path = Path(path)
        started = time.perf_counter()
        log_event(
            logger,
            "document processing started",
            document_id=None,
            step="pipeline",
            status="STARTED",
            file_name=document_path.name,
        )

        normalized = self.preprocessor.preprocess(document_path)
        extraction_result = self.agent.extract(normalized)
        if isinstance(extraction_result, ExtractionRun):
            extraction = extraction_result.extraction
            extraction_attempts = extraction_result.attempts
            preliminary_checks = extraction_result.preliminary_checks
            agreement_scores = extraction_result.agreement_scores
        else:
            extraction = extraction_result
            extraction_attempts = []
            preliminary_checks = []
            agreement_scores = {}
        record = extraction_to_document_record(extraction, normalized)
        record.extraction_attempts = extraction_attempts
        record.preliminary_checks = preliminary_checks

        record.reference_validation = self.reference_repository.lookup(
            issuer=record.issuer.name.value,
            cnpj=record.issuer.cnpj.value,
            isin=record.security.isin.value,
            ticker=record.security.ticker.value,
            share_class=record.security.share_class.value,
        )
        self._apply_reference(record)
        record.validations.extend(self._reference_validation_results(record))

        event_type = record.corporate_action.event_type.value
        if event_type is not None:
            record.validations.extend(
                validate_dates(event_type, record.corporate_action.dates)
            )
        record.validations.extend(
            validate_financial_values(record.corporate_action.financials)
        )
        record.validations.extend(validate_event_rules(record.corporate_action))
        self._attach_field_validations(record)

        apply_confidence(record, agreement_scores=agreement_scores)
        record.document_confidence = calculate_document_confidence(record)
        route_for_review(record)

        if persist:
            self._write_record(record)

        log_event(
            logger,
            "document processing finished",
            document_id=record.document_id,
            step="pipeline",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            status=record.processing_status.value,
        )
        return record

    def process_batch(
        self,
        paths: list[str | Path],
        *,
        existing_records: Iterable[DocumentRecord] = (),
    ) -> BatchProcessingResult:
        records: list[DocumentRecord] = list(existing_records)
        failures: list[ExceptionReportDocument] = []
        for path in paths:
            try:
                records.append(self.process_document(path))
            except Exception as exc:
                failures.append(self._failed_report_document(Path(path), exc))
                failure_payload = {
                    "schema_version": "2.0",
                    **failures[-1].model_dump(mode="json"),
                }
                self._write_json(
                    f"{Path(path).stem}.json",
                    failure_payload,
                    artifact_type="DOCUMENT_RECORD",
                    document_id=failures[-1].document_id,
                    processing_status=ProcessingStatus.FAILED.value,
                )
                logger.exception(
                    "document processing failed",
                    extra={
                        "event_data": {
                            "document_id": failures[-1].document_id,
                            "step": "pipeline",
                            "status": "FAILED",
                            "file_name": Path(path).name,
                        }
                    },
                )

        report = build_exception_report(records, failures=failures)
        self._write_json(
            "exception_report.json",
            report.model_dump(mode="json"),
            artifact_type="EXCEPTION_REPORT",
        )
        return BatchProcessingResult(records=records, report=report)

    def persist_record(self, record: DocumentRecord) -> None:
        """Persiste uma nova versão de um registro alterado pelo operador."""
        self._write_record(record)

    def persist_report(self, report: ExceptionReport) -> None:
        """Atualiza o relatório consolidado após uma decisão operacional."""
        self._write_json(
            "exception_report.json",
            report.model_dump(mode="json"),
            artifact_type="EXCEPTION_REPORT",
        )

    def _apply_reference(self, record: DocumentRecord) -> None:
        reference = record.reference_validation.reference_record
        conflict_fields = {
            "issuer": record.issuer.name,
            "cnpj": record.issuer.cnpj,
            "isin": record.security.isin,
            "ticker": record.security.ticker,
            "share_class": record.security.share_class,
        }
        for conflict in record.reference_validation.conflicts:
            field = conflict_fields.get(conflict.field)
            if field is not None:
                field.status = FieldStatus.CONFLICT

        if reference is None:
            return
        field_pairs = (
            (record.issuer.name, reference.issuer),
            (record.issuer.cnpj, reference.cnpj),
            (record.security.isin, reference.isin),
            (record.security.ticker, reference.ticker),
            (record.security.share_class, reference.share_class),
            (record.security.listing_segment, reference.listing_segment),
            (record.security.asset_status, reference.status),
        )
        for field, value in field_pairs:
            if field.value is None and field.status is FieldStatus.UNKNOWN:
                field.value = value
                field.status = FieldStatus.REFERENCE_ENRICHED
                field.origin = Origin.REFERENCE
                field.confidence = 0

    def _reference_validation_results(
        self,
        record: DocumentRecord,
    ) -> list[ValidationResult]:
        reference = record.reference_validation
        results = []
        if reference.reference_record is None:
            results.append(
                ValidationResult(
                    rule="REF_NO_MATCH",
                    status=ValidationStatus.FAIL,
                    message="No reference record could be confirmed.",
                )
            )
            return results

        for field in reference.matched_by:
            results.append(
                ValidationResult(
                    rule=f"REF_{field.upper()}_MATCH",
                    status=ValidationStatus.PASS,
                    message=f"{field} matches the reference record.",
                )
            )
        for conflict in reference.conflicts:
            results.append(
                ValidationResult(
                    rule=conflict.code,
                    status=ValidationStatus.FAIL,
                    message=f"{conflict.field} conflicts with the reference record.",
                    expected=conflict.expected,
                    observed=conflict.observed,
                )
            )
        if normalize_text(reference.reference_record.status) != "ativo":
            results.append(
                ValidationResult(
                    rule="REF_ASSET_INACTIVE",
                    status=ValidationStatus.FAIL,
                    message="The reference record is not active.",
                    expected="ativo",
                    observed=reference.reference_record.status,
                )
            )
        return results

    def _attach_field_validations(self, record: DocumentRecord) -> None:
        dates = record.corporate_action.dates
        financials = record.corporate_action.financials
        reference_fields = {
            "REF_ISSUER": [record.issuer.name],
            "REF_CNPJ": [record.issuer.cnpj],
            "REF_ISIN": [record.security.isin],
            "REF_TICKER": [record.security.ticker],
            "REF_SHARE_CLASS": [record.security.share_class],
            "REF_ASSET": [record.security.asset_status],
        }
        rule_fields = {
            "DATE_APPROVAL": [dates.approval_date, dates.record_date],
            "DATE_RECORD": [dates.record_date, dates.ex_date],
            "DATE_PAYMENT": [dates.payment_date, dates.record_date],
            "FIN_GROSS_NET": [
                financials.gross_amount_per_share,
                financials.net_amount_per_share,
                financials.tax_rate_percent,
            ],
            "FIN_TAX": [
                financials.tax_treatment,
                financials.net_amount_per_share,
            ],
            "FIN_UNIVERSAL_NET": [financials.net_amount_per_share],
            "FIN_CURRENCY": [financials.currency],
            "FIN_RATIO": [financials.ratio],
            "EVENT_": [record.corporate_action.event_type],
        }
        rule_fields.update(reference_fields)

        for validation in record.validations:
            attached = set()
            for prefix, fields in rule_fields.items():
                if validation.rule.startswith(prefix):
                    for field in fields:
                        if id(field) not in attached:
                            field.validation.append(validation.model_copy(deep=True))
                            attached.add(id(field))

    def _write_record(self, record: DocumentRecord) -> None:
        file_name = f"{Path(record.source_document.file_name).stem}.json"
        self._write_json(
            file_name,
            record.model_dump(mode="json"),
            artifact_type="DOCUMENT_RECORD",
            document_id=record.document_id,
            processing_status=record.processing_status.value,
        )

    def _write_json(
        self,
        file_name: str,
        payload: dict,
        *,
        artifact_type: str,
        document_id: str | None = None,
        processing_status: str | None = None,
    ) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / file_name
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(destination)
            if self.artifact_repository is not None:
                self.artifact_repository.save_artifact(
                    artifact_type=artifact_type,
                    file_name=file_name,
                    payload=payload,
                    document_id=document_id,
                    processing_status=processing_status,
                )
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise OutputPersistenceError(
                f"unable to persist output artifact: {destination.name}"
            ) from exc

    def _failed_report_document(
        self,
        path: Path,
        error: Exception,
    ) -> ExceptionReportDocument:
        digest = _safe_sha256(path)
        code = _technical_error_code(error)
        return ExceptionReportDocument(
            document_id=f"sha256:{digest}",
            file_name=path.name,
            processing_status=ProcessingStatus.FAILED,
            exceptions=[
                RoutingReason(
                    code=code,
                    category=ExceptionCategory.TECHNICAL_ERROR,
                    message=str(error) or type(error).__name__,
                )
            ],
        )


def _technical_error_code(error: Exception) -> str:
    if isinstance(error, CorruptPdfError):
        return "PDF_CORRUPT"
    if isinstance(error, OcrProcessingError):
        return "OCR_FAILED"
    if isinstance(error, AgentStructuredOutputError):
        return "LLM_STRUCTURED_OUTPUT_INVALID"
    if isinstance(error, AgentProviderError):
        return "LLM_PROVIDER_UNAVAILABLE"
    if isinstance(error, OutputPersistenceError):
        return "OUTPUT_WRITE_FAILED"
    return "PROCESSING_FAILED"


def _safe_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        digest.update(str(path).encode("utf-8"))
    return digest.hexdigest()

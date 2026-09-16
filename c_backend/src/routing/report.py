from collections.abc import Iterable

from src.models.enums import ProcessingStatus
from src.models.schemas import (
    DocumentRecord,
    ExceptionReport,
    ExceptionReportDocument,
    ExceptionReportSummary,
)


def build_exception_report(
    records: Iterable[DocumentRecord],
    *,
    failures: Iterable[ExceptionReportDocument] = (),
) -> ExceptionReport:
    record_list = list(records)
    failure_list = list(failures)
    counts = {status: 0 for status in ProcessingStatus}
    for record in record_list:
        counts[record.processing_status] += 1

    return ExceptionReport(
        summary=ExceptionReportSummary(
            processed=len(record_list) + len(failure_list),
            accepted=counts[ProcessingStatus.ACCEPTED],
            human_review=counts[ProcessingStatus.REVIEW_REQUIRED],
            pending_information=counts[ProcessingStatus.PENDING_INFORMATION],
            failed=counts[ProcessingStatus.FAILED] + len(failure_list),
        ),
        documents=[
            ExceptionReportDocument(
                document_id=record.document_id,
                file_name=record.source_document.file_name,
                processing_status=record.processing_status,
                confidence_score=record.document_confidence.score,
                exceptions=record.exceptions,
            )
            for record in record_list
        ]
        + failure_list,
    )

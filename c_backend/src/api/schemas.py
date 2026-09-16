from pydantic import Field

from src.models.schemas import DocumentRecord, ExceptionReport, StrictModel


class HealthResponse(StrictModel):
    status: str
    provider: str
    provider_configured: bool
    golden_records_available: bool


class BatchUploadResponse(StrictModel):
    records: list[DocumentRecord] = Field(default_factory=list)
    report: ExceptionReport

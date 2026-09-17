from typing import Literal

from pydantic import Field

from src.models.schemas import DocumentRecord, ExceptionReport, StrictModel


class HealthResponse(StrictModel):
    status: str
    provider: str
    provider_configured: bool
    golden_records_available: bool
    database_configured: bool


class UploadResult(StrictModel):
    file_name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal[
        "PROCESSED",
        "REUSED",
        "DUPLICATE_IN_BATCH",
        "ALREADY_PROCESSING",
        "REEVALUATED",
    ]
    message: str


class BatchUploadResponse(StrictModel):
    records: list[DocumentRecord] = Field(default_factory=list)
    report: ExceptionReport
    uploads: list[UploadResult] = Field(default_factory=list)

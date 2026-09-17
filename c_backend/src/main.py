from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.api.dependencies import ProviderNotConfiguredError, build_pipeline
from src.api.documents import (
    DOCUMENT_ID_PATTERN,
    find_pdf_by_document_id,
    find_pdf_by_sha256,
)
from src.api.schemas import BatchUploadResponse, HealthResponse, UploadResult
from src.api.uploads import StoredUpload, store_pdf_upload
from src.config import AppSettings
from src.logging_config import configure_logging
from src.persistence import DocumentRegistry
from src.pipeline.processor import BatchProcessingResult, ProcessingPipeline
from src.routing.report import build_exception_report

PipelineFactory = Callable[[AppSettings], ProcessingPipeline]


def create_app(
    settings: AppSettings | None = None,
    *,
    pipeline_factory: PipelineFactory = build_pipeline,
) -> FastAPI:
    app_settings = settings or AppSettings.from_env()
    configure_logging(app_settings.log_level)

    application = FastAPI(
        title="FinTrace API",
        version="2.0.0",
        description=(
            "Structured, validated, and auditable corporate action processing."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.state.settings = app_settings
    application.state.pipeline = None

    def get_pipeline() -> ProcessingPipeline:
        if application.state.pipeline is None:
            application.state.pipeline = pipeline_factory(app_settings)
        return application.state.pipeline

    def get_registry(pipeline: ProcessingPipeline) -> DocumentRegistry | None:
        repository = pipeline.artifact_repository
        return repository if hasattr(repository, "claim_document") else None

    @application.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            provider=app_settings.llm_provider,
            provider_configured=bool(app_settings.gemini_api_key),
            golden_records_available=app_settings.golden_records_path.is_file(),
            database_configured=bool(app_settings.database_url),
        )

    @application.post(
        "/api/documents/upload",
        response_model=BatchUploadResponse,
    )
    async def upload_documents(
        files: list[UploadFile] = File(...),
    ) -> BatchUploadResponse:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one PDF is required.",
            )

        stored_uploads = []
        try:
            for upload in files:
                stored_uploads.append(
                    await store_pdf_upload(
                        upload,
                        input_dir=app_settings.input_dir,
                        max_size_bytes=app_settings.max_upload_size_bytes,
                    )
                )
        except HTTPException:
            for stored in stored_uploads:
                stored.path.unlink(missing_ok=True)
            raise

        try:
            pipeline = get_pipeline()
            registry = get_registry(pipeline)
            paths_to_process = []
            cached_records = []
            upload_results = []
            seen_hashes: set[str] = set()

            for stored in stored_uploads:
                if stored.sha256 in seen_hashes:
                    _remove_redundant_upload(stored, app_settings.input_dir)
                    upload_results.append(
                        UploadResult(
                            file_name=stored.original_file_name,
                            sha256=stored.sha256,
                            disposition="DUPLICATE_IN_BATCH",
                            message="Documento repetido no mesmo lote; somente uma cópia foi considerada.",
                        )
                    )
                    continue
                seen_hashes.add(stored.sha256)

                if registry is None:
                    paths_to_process.append(stored.path)
                    upload_results.append(
                        _upload_result(stored, "PROCESSED")
                    )
                    continue

                claim = registry.claim_document(
                    sha256=stored.sha256,
                    file_name=stored.path.name,
                )
                if claim.acquired:
                    paths_to_process.append(stored.path)
                    upload_results.append(
                        _upload_result(stored, "PROCESSED")
                    )
                elif claim.record is not None:
                    _remove_redundant_upload(stored, app_settings.input_dir)
                    cached_records.append(claim.record)
                    upload_results.append(
                        _upload_result(
                            stored,
                            "REUSED",
                            existing_file_name=claim.record.source_document.file_name,
                        )
                    )
                else:
                    _remove_redundant_upload(stored, app_settings.input_dir)
                    upload_results.append(
                        _upload_result(stored, "ALREADY_PROCESSING")
                    )

            result = (
                pipeline.process_batch(
                    paths_to_process,
                    existing_records=cached_records,
                )
                if paths_to_process
                else BatchProcessingResult(
                    records=cached_records,
                    report=build_exception_report(cached_records),
                )
            )
        except ProviderNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        return BatchUploadResponse(
            records=result.records,
            report=result.report,
            uploads=upload_results,
        )

    @application.post(
        "/api/documents/{document_id}/reevaluate",
        response_model=BatchUploadResponse,
    )
    async def reevaluate_document(document_id: str) -> BatchUploadResponse:
        match = DOCUMENT_ID_PATTERN.fullmatch(document_id)
        path = find_pdf_by_document_id(app_settings.input_dir, document_id)
        if match is None or path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        pipeline = get_pipeline()
        registry = get_registry(pipeline)
        if registry is not None:
            claim = registry.claim_document(
                sha256=match.group(1),
                file_name=path.name,
                force=True,
            )
            if not claim.acquired:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Este documento já está sendo processado.",
                )

        result = pipeline.process_batch([path])
        return BatchUploadResponse(
            records=result.records,
            report=result.report,
            uploads=[
                UploadResult(
                    file_name=path.name,
                    sha256=match.group(1),
                    disposition="REEVALUATED",
                    message="Documento reavaliado e nova versão adicionada ao histórico.",
                )
            ],
        )

    @application.get(
        "/api/documents/{document_id}/file",
        response_class=Response,
    )
    async def view_document(document_id: str) -> Response:
        path = find_pdf_by_document_id(app_settings.input_dir, document_id)
        if path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
        return Response(
            content=path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": (
                    "inline; filename=document.pdf; "
                    f"filename*=UTF-8''{quote(path.name)}"
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    return application


def _upload_result(
    stored: StoredUpload,
    disposition: Literal["PROCESSED", "REUSED", "ALREADY_PROCESSING"],
    *,
    existing_file_name: str | None = None,
) -> UploadResult:
    messages = {
        "PROCESSED": (
            "Documento novo; uma execução exclusiva da pipeline foi realizada."
        ),
        "REUSED": (
            "Documento já processado; resultado anterior reutilizado sem nova "
            "chamada à IA."
        ),
        "ALREADY_PROCESSING": (
            "Este conteúdo já está sendo processado por outra solicitação; "
            "nenhuma chamada duplicada à IA foi iniciada."
        ),
    }
    return UploadResult(
        file_name=stored.original_file_name,
        existing_file_name=existing_file_name,
        sha256=stored.sha256,
        disposition=disposition,
        message=messages[disposition],
    )


def _remove_redundant_upload(
    stored: StoredUpload,
    input_dir: str | Path,
) -> None:
    existing_copy = find_pdf_by_sha256(
        input_dir,
        stored.sha256,
        exclude=stored.path,
    )
    if existing_copy is not None:
        stored.path.unlink(missing_ok=True)


app = create_app()

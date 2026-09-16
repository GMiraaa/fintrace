from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.api.dependencies import ProviderNotConfiguredError, build_pipeline
from src.api.documents import find_pdf_by_document_id
from src.api.schemas import BatchUploadResponse, HealthResponse
from src.api.uploads import store_pdf_upload
from src.config import AppSettings
from src.logging_config import configure_logging
from src.pipeline.processor import ProcessingPipeline

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

        saved_paths = []
        try:
            for upload in files:
                saved_paths.append(
                    await store_pdf_upload(
                        upload,
                        input_dir=app_settings.input_dir,
                        max_size_bytes=app_settings.max_upload_size_bytes,
                    )
                )
        except HTTPException:
            for path in saved_paths:
                path.unlink(missing_ok=True)
            raise

        try:
            if application.state.pipeline is None:
                application.state.pipeline = pipeline_factory(app_settings)
            result = application.state.pipeline.process_batch(saved_paths)
        except ProviderNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        return BatchUploadResponse(
            records=result.records,
            report=result.report,
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


app = create_app()

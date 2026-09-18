from dataclasses import replace
import hashlib
from pathlib import Path

import httpx
import pymupdf
import pytest

from src.config import AppSettings
from src.main import create_app
from src.models.enums import ExceptionCategory, ProcessingStatus
from src.models.schemas import RoutingReason
from src.persistence import DocumentClaim
from src.pipeline.processor import BatchProcessingResult
from src.routing.report import build_exception_report

from .factories import valid_document_record


class StubPipeline:
    def __init__(self, registry=None) -> None:
        self.received: list[Path] = []
        self.artifact_repository = registry
        self.persisted_records = []
        self.persisted_reports = []

    def process_batch(self, paths, *, existing_records=()):
        self.received.extend(Path(path) for path in paths)
        records = list(existing_records)
        for path in paths:
            path = Path(path)
            record = valid_document_record()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            record.document_id = f"sha256:{digest}"
            record.source_document.sha256 = digest
            record.source_document.file_name = path.name
            records.append(record)
        report = build_exception_report(records)
        return BatchProcessingResult(records=records, report=report)

    def persist_record(self, record):
        self.persisted_records.append(record.model_copy(deep=True))
        if self.artifact_repository is not None:
            self.artifact_repository.store(record)

    def persist_report(self, report):
        self.persisted_reports.append(report.model_copy(deep=True))


class MemoryDocumentRegistry:
    def __init__(self) -> None:
        self.claims: dict[str, tuple[str, object | None]] = {}
        self.calls: list[tuple[str, bool]] = []

    def claim_document(self, *, sha256: str, file_name: str, force: bool = False):
        self.calls.append((sha256, force))
        current = self.claims.get(sha256)
        if current is None or (force and current[0] != "PROCESSING"):
            self.claims[sha256] = ("PROCESSING", None)
            return DocumentClaim(acquired=True, state="PROCESSING")
        state, record = current
        return DocumentClaim(acquired=False, state=state, record=record)

    def get_document(self, document_id: str):
        digest = document_id.removeprefix("sha256:")
        state, record = self.claims.get(digest, ("MISSING", None))
        return record.model_copy(deep=True) if state == "COMPLETED" and record else None

    def list_documents(self):
        return [
            record.model_copy(deep=True)
            for state, record in self.claims.values()
            if state == "COMPLETED" and record is not None
        ]

    def store(self, record):
        self.claims[record.source_document.sha256] = (
            "COMPLETED",
            record.model_copy(deep=True),
        )


def api_settings(tmp_path: Path) -> AppSettings:
    base = AppSettings.from_env(tmp_path)
    golden = tmp_path / "golden_records.csv"
    golden.write_text("placeholder", encoding="utf-8")
    return replace(
        base,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        golden_records_path=golden,
        max_upload_size_bytes=1024,
        gemini_api_key="test-key",
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


def api_client(settings: AppSettings, pipeline: StubPipeline) -> httpx.AsyncClient:
    app = create_app(settings, pipeline_factory=lambda _: pipeline)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


@pytest.mark.anyio
async def test_health_reports_provider_configuration(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    async with api_client(settings, StubPipeline()) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["provider_configured"] is True
    assert response.json()["golden_records_available"] is True


@pytest.mark.anyio
async def test_upload_stores_and_processes_pdf(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    pipeline = StubPipeline()
    async with api_client(settings, pipeline) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[
                ("files", ("aviso.pdf", b"%PDF-1.4\ntest", "application/pdf"))
            ],
        )

    assert response.status_code == 200
    assert pipeline.received[0].is_file()
    assert pipeline.received[0].parent == settings.input_dir
    assert response.json()["report"]["summary"]["processed"] == 1


@pytest.mark.anyio
async def test_upload_uses_unique_name_on_collision(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    pipeline = StubPipeline()
    upload = [("files", ("aviso.pdf", b"%PDF-1.4\ntest", "application/pdf"))]

    async with api_client(settings, pipeline) as client:
        first = await client.post("/api/documents/upload", files=upload)
        second = await client.post("/api/documents/upload", files=upload)

    assert first.status_code == 200
    assert second.status_code == 200

    assert pipeline.received[0].name == "aviso.pdf"
    assert pipeline.received[1].name != "aviso.pdf"


@pytest.mark.anyio
async def test_upload_reuses_completed_record_with_same_content(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    content = b"%PDF-1.4\nsame content"
    digest = hashlib.sha256(content).hexdigest()
    cached = valid_document_record()
    cached.document_id = f"sha256:{digest}"
    cached.source_document.sha256 = digest
    cached.source_document.file_name = "primeira_versao.pdf"
    registry = MemoryDocumentRegistry()
    registry.claims[digest] = ("COMPLETED", cached)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[("files", ("novo_nome.pdf", content, "application/pdf"))],
        )

    assert response.status_code == 200
    assert pipeline.received == []
    assert response.json()["uploads"][0]["disposition"] == "REUSED"
    assert response.json()["uploads"][0]["file_name"] == "novo_nome.pdf"
    assert (
        response.json()["uploads"][0]["existing_file_name"]
        == "primeira_versao.pdf"
    )
    assert response.json()["records"][0]["document_id"] == f"sha256:{digest}"
    assert (settings.input_dir / "novo_nome.pdf").is_file()


@pytest.mark.anyio
async def test_concurrent_duplicate_does_not_run_pipeline(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    content = b"%PDF-1.4\nalready processing"
    digest = hashlib.sha256(content).hexdigest()
    registry = MemoryDocumentRegistry()
    registry.claims[digest] = ("PROCESSING", None)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[("files", ("copia.pdf", content, "application/pdf"))],
        )

    assert response.status_code == 200
    assert pipeline.received == []
    assert response.json()["records"] == []
    assert response.json()["uploads"][0]["disposition"] == "ALREADY_PROCESSING"


@pytest.mark.anyio
async def test_duplicate_content_inside_batch_is_processed_once(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    registry = MemoryDocumentRegistry()
    pipeline = StubPipeline(registry)
    content = b"%PDF-1.4\nsame content"

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[
                ("files", ("primeiro.pdf", content, "application/pdf")),
                ("files", ("segundo.pdf", content, "application/pdf")),
            ],
        )

    assert response.status_code == 200
    assert len(pipeline.received) == 1
    assert len(list(settings.input_dir.glob("*.pdf"))) == 1
    assert [item["disposition"] for item in response.json()["uploads"]] == [
        "PROCESSED",
        "DUPLICATE_IN_BATCH",
    ]


@pytest.mark.anyio
async def test_upload_rejects_path_traversal(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    async with api_client(settings, StubPipeline()) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[
                (
                    "files",
                    ("../escape.pdf", b"%PDF-1.4\ntest", "application/pdf"),
                )
            ],
        )

    assert response.status_code == 400
    assert not (tmp_path / "escape.pdf").exists()


@pytest.mark.anyio
async def test_upload_rejects_non_pdf_signature(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    async with api_client(settings, StubPipeline()) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[("files", ("fake.pdf", b"not a pdf", "application/pdf"))],
        )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_document_file_is_served_inline_by_content_hash(
    tmp_path: Path,
) -> None:
    settings = api_settings(tmp_path)
    settings.input_dir.mkdir(parents=True)
    content = b"%PDF-1.4\ntest document"
    pdf = settings.input_dir / "aviso.pdf"
    pdf.write_bytes(content)
    document_id = f"sha256:{hashlib.sha256(content).hexdigest()}"

    async with api_client(settings, StubPipeline()) as client:
        response = await client.get(f"/api/documents/{document_id}/file")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.anyio
async def test_document_file_rejects_unknown_or_invalid_id(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    settings.input_dir.mkdir(parents=True)

    async with api_client(settings, StubPipeline()) as client:
        invalid = await client.get("/api/documents/not-a-hash/file")
        unknown = await client.get(
            f"/api/documents/sha256:{'f' * 64}/file"
        )

    assert invalid.status_code == 404
    assert unknown.status_code == 404


@pytest.mark.anyio
async def test_document_preview_is_rendered_as_png(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    settings.input_dir.mkdir(parents=True)
    pdf = settings.input_dir / "aviso.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "FinTrace preview")
        document.save(pdf)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()

    async with api_client(settings, StubPipeline()) as client:
        response = await client.get(
            f"/api/documents/sha256:{digest}/preview"
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.anyio
async def test_operator_can_force_document_reevaluation(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    settings.input_dir.mkdir(parents=True)
    content = b"%PDF-1.4\ndocument to reevaluate"
    digest = hashlib.sha256(content).hexdigest()
    pdf = settings.input_dir / "aviso.pdf"
    pdf.write_bytes(content)
    cached = valid_document_record()
    cached.document_id = f"sha256:{digest}"
    cached.source_document.sha256 = digest
    registry = MemoryDocumentRegistry()
    registry.claims[digest] = ("COMPLETED", cached)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            f"/api/documents/sha256:{digest}/reevaluate"
        )

    assert response.status_code == 200
    assert pipeline.received == [pdf]
    assert registry.calls[-1] == (digest, True)
    assert response.json()["uploads"][0]["disposition"] == "REEVALUATED"


@pytest.mark.anyio
async def test_reevaluation_rejects_document_already_processing(
    tmp_path: Path,
) -> None:
    settings = api_settings(tmp_path)
    settings.input_dir.mkdir(parents=True)
    content = b"%PDF-1.4\nprocessing reevaluation"
    digest = hashlib.sha256(content).hexdigest()
    (settings.input_dir / "aviso.pdf").write_bytes(content)
    registry = MemoryDocumentRegistry()
    registry.claims[digest] = ("PROCESSING", None)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            f"/api/documents/sha256:{digest}/reevaluate"
        )

    assert response.status_code == 409
    assert pipeline.received == []


@pytest.mark.anyio
async def test_operator_can_approve_document_after_review(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    record = valid_document_record()
    record.processing_status = ProcessingStatus.REVIEW_REQUIRED
    record.review.required = True
    record.review.reasons = [
        RoutingReason(
            code="MANUAL_CHECK_REQUIRED",
            category=ExceptionCategory.REVIEW_EXCEPTION,
            message="Operator confirmation is required.",
        )
    ]
    record.exceptions = record.review.reasons.copy()
    registry = MemoryDocumentRegistry()
    registry.store(record)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            f"/api/documents/{record.document_id}/approve"
        )

    assert response.status_code == 200
    approved = response.json()["records"][0]
    assert approved["processing_status"] == "ACCEPTED"
    assert approved["review"]["required"] is False
    assert approved["manual_review"]["approved"] is True
    assert approved["manual_review"]["previous_status"] == "REVIEW_REQUIRED"
    assert approved["manual_review"]["acknowledged_reasons"][0]["code"] == (
        "MANUAL_CHECK_REQUIRED"
    )
    assert response.json()["report"]["summary"]["human_review"] == 0
    assert response.json()["report"]["summary"]["accepted"] == 1
    assert response.json()["report"]["documents"][0]["manually_approved"] is True
    assert len(pipeline.persisted_records) == 1
    assert len(pipeline.persisted_reports) == 1


@pytest.mark.anyio
async def test_manual_approval_rejects_document_outside_review(tmp_path: Path) -> None:
    settings = api_settings(tmp_path)
    record = valid_document_record()
    registry = MemoryDocumentRegistry()
    registry.store(record)
    pipeline = StubPipeline(registry)

    async with api_client(settings, pipeline) as client:
        response = await client.post(
            f"/api/documents/{record.document_id}/approve"
        )

    assert response.status_code == 409
    assert pipeline.persisted_records == []


@pytest.mark.anyio
async def test_upload_rejects_oversized_file(tmp_path: Path) -> None:
    settings = replace(api_settings(tmp_path), max_upload_size_bytes=8)
    async with api_client(settings, StubPipeline()) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[
                (
                    "files",
                    ("large.pdf", b"%PDF-1.4-too-large", "application/pdf"),
                )
            ],
        )

    assert response.status_code == 413

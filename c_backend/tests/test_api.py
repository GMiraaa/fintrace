from dataclasses import replace
import hashlib
from pathlib import Path

import httpx
import pytest

from src.config import AppSettings
from src.main import create_app
from src.pipeline.processor import BatchProcessingResult
from src.routing.report import build_exception_report

from .factories import valid_document_record


class StubPipeline:
    def __init__(self) -> None:
        self.received: list[Path] = []

    def process_batch(self, paths):
        self.received.extend(Path(path) for path in paths)
        record = valid_document_record()
        record.source_document.file_name = self.received[-1].name
        report = build_exception_report([record])
        return BatchProcessingResult(records=[record], report=report)


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

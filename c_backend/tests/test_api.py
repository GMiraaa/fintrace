from dataclasses import replace
import hashlib
from pathlib import Path

import httpx
import pytest

from src.config import AppSettings
from src.main import create_app
from src.persistence import DocumentClaim
from src.pipeline.processor import BatchProcessingResult
from src.routing.report import build_exception_report

from .factories import valid_document_record


class StubPipeline:
    def __init__(self, registry=None) -> None:
        self.received: list[Path] = []
        self.artifact_repository = registry

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

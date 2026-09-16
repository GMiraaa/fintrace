from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from src.config import AppSettings
from src.main import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_invalid_batch_does_not_leave_partially_saved_uploads(
    tmp_path: Path,
) -> None:
    settings = replace(
        AppSettings.from_env(tmp_path),
        input_dir=tmp_path / "input",
        max_upload_size_bytes=1024,
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/documents/upload",
            files=[
                ("files", ("valid.pdf", b"%PDF-1.4\ntest", "application/pdf")),
                ("files", ("invalid.pdf", b"not a pdf", "application/pdf")),
            ],
        )

    assert response.status_code == 400
    assert not list(settings.input_dir.glob("*.pdf"))

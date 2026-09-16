from typing import Any

from src.persistence import ArtifactRepository
from src.pipeline.processor import ProcessingPipeline


class MemoryArtifactRepository:
    def __init__(self) -> None:
        self.artifacts: list[dict[str, Any]] = []

    def save_artifact(self, **artifact: Any) -> None:
        self.artifacts.append(artifact)


def accepts_artifact_repository(repository: ArtifactRepository) -> ArtifactRepository:
    return repository


def test_artifact_repository_contract_accepts_in_memory_implementation() -> None:
    repository = MemoryArtifactRepository()

    accepted = accepts_artifact_repository(repository)
    accepted.save_artifact(
        artifact_type="DOCUMENT_RECORD",
        file_name="notice.json",
        payload={"schema_version": "2.0"},
        document_id=f"sha256:{'a' * 64}",
        processing_status="ACCEPTED",
    )

    assert repository.artifacts[0]["file_name"] == "notice.json"


def test_pipeline_persists_same_payload_to_file_and_repository(tmp_path) -> None:
    repository = MemoryArtifactRepository()
    pipeline = ProcessingPipeline(
        preprocessor=object(),
        agent=object(),
        reference_repository=object(),
        output_dir=tmp_path,
        artifact_repository=repository,
    )

    pipeline._write_json(
        "notice.json",
        {"schema_version": "2.0", "value": "test"},
        artifact_type="DOCUMENT_RECORD",
        document_id=f"sha256:{'a' * 64}",
        processing_status="ACCEPTED",
    )

    assert (tmp_path / "notice.json").is_file()
    assert repository.artifacts[0]["payload"]["value"] == "test"

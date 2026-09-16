from __future__ import annotations

from typing import Any, Protocol


class ArtifactRepository(Protocol):
    def save_artifact(
        self,
        *,
        artifact_type: str,
        file_name: str,
        payload: dict[str, Any],
        document_id: str | None = None,
        processing_status: str | None = None,
    ) -> None: ...


class PostgresArtifactRepository:
    """Persiste cada JSON gerado como um artefato imutável em JSONB."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required for PostgreSQL persistence")
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL persistence"
            ) from exc
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_artifacts (
                    id BIGSERIAL PRIMARY KEY,
                    artifact_type VARCHAR(32) NOT NULL,
                    file_name TEXT NOT NULL,
                    document_id TEXT,
                    processing_status VARCHAR(32),
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_processing_artifacts_document_id
                ON processing_artifacts (document_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_processing_artifacts_created_at
                ON processing_artifacts (created_at DESC)
                """
            )

    def save_artifact(
        self,
        *,
        artifact_type: str,
        file_name: str,
        payload: dict[str, Any],
        document_id: str | None = None,
        processing_status: str | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_artifacts (
                    artifact_type,
                    file_name,
                    document_id,
                    processing_status,
                    payload
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    artifact_type,
                    file_name,
                    document_id,
                    processing_status,
                    Jsonb(payload),
                ),
            )

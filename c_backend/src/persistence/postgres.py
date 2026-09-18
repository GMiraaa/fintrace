from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.models.schemas import DocumentRecord


@dataclass(frozen=True)
class DocumentClaim:
    acquired: bool
    state: str
    record: DocumentRecord | None = None


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


class DocumentRegistry(Protocol):
    def claim_document(
        self,
        *,
        sha256: str,
        file_name: str,
        force: bool = False,
    ) -> DocumentClaim: ...

    def get_document(self, document_id: str) -> DocumentRecord | None: ...

    def list_documents(self) -> list[DocumentRecord]: ...


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
                CREATE TABLE IF NOT EXISTS documents (
                    sha256 CHAR(64) PRIMARY KEY,
                    document_id TEXT NOT NULL UNIQUE,
                    original_file_name TEXT NOT NULL,
                    processing_state VARCHAR(16) NOT NULL,
                    latest_processing_status VARCHAR(32),
                    latest_payload JSONB,
                    revision INTEGER NOT NULL DEFAULT 1,
                    processing_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    processed_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT ck_documents_sha256
                        CHECK (sha256 ~ '^[0-9a-f]{64}$')
                )
                """
            )
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
            connection.execute(
                """
                INSERT INTO documents (
                    sha256,
                    document_id,
                    original_file_name,
                    processing_state,
                    latest_processing_status,
                    latest_payload,
                    processed_at,
                    updated_at
                )
                SELECT DISTINCT ON (substring(document_id FROM 8))
                    substring(document_id FROM 8),
                    document_id,
                    COALESCE(
                        payload #>> '{source_document,file_name}',
                        file_name
                    ),
                    'COMPLETED',
                    processing_status,
                    payload,
                    created_at,
                    created_at
                FROM processing_artifacts
                WHERE artifact_type = 'DOCUMENT_RECORD'
                  AND processing_status <> 'FAILED'
                  AND document_id ~ '^sha256:[0-9a-f]{64}$'
                  AND payload ->> 'schema_version' = '2.0'
                ORDER BY substring(document_id FROM 8), created_at DESC
                ON CONFLICT (sha256) DO NOTHING
                """
            )

    def claim_document(
        self,
        *,
        sha256: str,
        file_name: str,
        force: bool = False,
    ) -> DocumentClaim:
        document_id = f"sha256:{sha256}"
        with self._connect() as connection:
            inserted = connection.execute(
                """
                INSERT INTO documents (
                    sha256, document_id, original_file_name, processing_state
                ) VALUES (%s, %s, %s, 'PROCESSING')
                ON CONFLICT (sha256) DO NOTHING
                RETURNING sha256
                """,
                (sha256, document_id, file_name),
            ).fetchone()
            if inserted is not None:
                return DocumentClaim(acquired=True, state="PROCESSING")

            if force:
                claimed = connection.execute(
                    """
                    UPDATE documents
                    SET processing_state = 'PROCESSING',
                        original_file_name = %s,
                        revision = revision + 1,
                        processing_started_at = NOW(),
                        processed_at = NULL,
                        updated_at = NOW()
                    WHERE sha256 = %s AND processing_state <> 'PROCESSING'
                    RETURNING sha256
                    """,
                    (file_name, sha256),
                ).fetchone()
                if claimed is not None:
                    return DocumentClaim(acquired=True, state="PROCESSING")

            row = connection.execute(
                """
                SELECT processing_state, latest_payload
                FROM documents
                WHERE sha256 = %s
                """,
                (sha256,),
            ).fetchone()
            if row is None:
                raise RuntimeError("document claim disappeared unexpectedly")
            state, payload = row
            record = None
            if state == "COMPLETED" and payload is not None:
                record = DocumentRecord.model_validate(payload)
            if state == "FAILED" and not force:
                retried = connection.execute(
                    """
                    UPDATE documents
                    SET processing_state = 'PROCESSING',
                        original_file_name = %s,
                        revision = revision + 1,
                        processing_started_at = NOW(),
                        processed_at = NULL,
                        updated_at = NOW()
                    WHERE sha256 = %s AND processing_state = 'FAILED'
                    RETURNING sha256
                    """,
                    (file_name, sha256),
                ).fetchone()
                if retried is not None:
                    return DocumentClaim(acquired=True, state="PROCESSING")
            return DocumentClaim(acquired=False, state=state, record=record)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT latest_payload
                FROM documents
                WHERE document_id = %s
                  AND processing_state = 'COMPLETED'
                """,
                (document_id,),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return DocumentRecord.model_validate(row[0])

    def list_documents(self) -> list[DocumentRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT latest_payload
                FROM documents
                WHERE processing_state = 'COMPLETED'
                  AND latest_payload IS NOT NULL
                ORDER BY processed_at, document_id
                """
            ).fetchall()
        return [DocumentRecord.model_validate(row[0]) for row in rows]

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

        source_document = payload.get("source_document")
        original_file_name = (
            source_document.get("file_name", file_name)
            if isinstance(source_document, dict)
            else file_name
        )
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
            if artifact_type == "DOCUMENT_RECORD" and document_id:
                sha256 = _sha256_from_document_id(document_id)
                if sha256 is not None:
                    state = (
                        "FAILED"
                        if processing_status == "FAILED"
                        else "COMPLETED"
                    )
                    connection.execute(
                        """
                        INSERT INTO documents (
                            sha256,
                            document_id,
                            original_file_name,
                            processing_state,
                            latest_processing_status,
                            latest_payload,
                            processed_at,
                            updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (sha256) DO UPDATE
                        SET processing_state = EXCLUDED.processing_state,
                            latest_processing_status = EXCLUDED.latest_processing_status,
                            latest_payload = EXCLUDED.latest_payload,
                            processed_at = NOW(),
                            updated_at = NOW()
                        """,
                        (
                            sha256,
                            document_id,
                            original_file_name,
                            state,
                            processing_status,
                            Jsonb(payload),
                        ),
                    )


def _sha256_from_document_id(document_id: str) -> str | None:
    prefix = "sha256:"
    digest = document_id.removeprefix(prefix)
    if not document_id.startswith(prefix) or len(digest) != 64:
        return None
    if any(character not in "0123456789abcdef" for character in digest):
        return None
    return digest

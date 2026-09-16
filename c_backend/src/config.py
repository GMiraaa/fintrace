from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppSettings:
    repository_root: Path
    app_env: str
    log_level: str
    backend_host: str
    backend_port: int
    cors_origins: tuple[str, ...]
    input_dir: Path
    output_dir: Path
    golden_records_path: Path
    max_upload_size_bytes: int
    ocr_language: str
    ocr_dpi: int
    native_text_min_chars: int
    llm_provider: str
    llm_basic_model: str
    llm_strong_model: str
    gemini_api_key: str
    database_url: str

    @property
    def llm_model(self) -> str:
        """Mantém compatibilidade com integrações que usam o nome antigo."""
        return self.llm_basic_model

    @classmethod
    def from_env(cls, repository_root: str | Path | None = None) -> AppSettings:
        root = (
            Path(repository_root).resolve()
            if repository_root is not None
            else Path(__file__).resolve().parents[2]
        )
        load_dotenv(root / ".env", override=False)

        return cls(
            repository_root=root,
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
            backend_port=_positive_int("BACKEND_PORT", 8000),
            cors_origins=tuple(
                item.strip()
                for item in os.getenv(
                    "CORS_ORIGINS", "http://localhost:5173"
                ).split(",")
                if item.strip()
            ),
            input_dir=_resolve_path(root, os.getenv("INPUT_DIR", "a_data/a_input")),
            output_dir=_resolve_path(
                root, os.getenv("OUTPUT_DIR", "a_data/b_output")
            ),
            golden_records_path=_resolve_path(
                root,
                os.getenv(
                    "GOLDEN_RECORDS_PATH",
                    "a_data/c_golden_records/golden_records.csv",
                ),
            ),
            max_upload_size_bytes=(
                _positive_int("MAX_UPLOAD_SIZE_MB", 20) * 1024 * 1024
            ),
            ocr_language=os.getenv("OCR_LANGUAGE", "por"),
            ocr_dpi=_positive_int("OCR_DPI", 300),
            native_text_min_chars=_non_negative_int(
                "NATIVE_TEXT_MIN_CHARS", 80
            ),
            llm_provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
            llm_basic_model=os.getenv(
                "LLM_BASIC_MODEL",
                os.getenv("LLM_MODEL", "gemini-3.5-flash-lite"),
            ),
            llm_strong_model=os.getenv(
                "LLM_STRONG_MODEL", "gemini-3.8-flash"
            ),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://fintrace:fintrace@localhost:5432/fintrace",
            ),
        )


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _non_negative_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value

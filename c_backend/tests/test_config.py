from pathlib import Path

import pytest

from src.config import AppSettings


def test_settings_resolve_paths_from_repository_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("INPUT_DIR", "custom/input")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "7")

    settings = AppSettings.from_env(tmp_path)

    assert settings.input_dir == tmp_path / "custom/input"
    assert settings.max_upload_size_bytes == 7 * 1024 * 1024


def test_settings_reject_non_positive_upload_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "0")

    with pytest.raises(ValueError, match="must be positive"):
        AppSettings.from_env(tmp_path)


def test_settings_support_separate_llm_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LLM_BASIC_MODEL", "modelo-basico")
    monkeypatch.setenv("LLM_STRONG_MODEL", "modelo-forte")
    monkeypatch.setenv("ENABLE_STRONG_LLM_FALLBACK", "false")

    settings = AppSettings.from_env(tmp_path)

    assert settings.llm_basic_model == "modelo-basico"
    assert settings.llm_strong_model == "modelo-forte"
    assert settings.enable_strong_llm_fallback is False

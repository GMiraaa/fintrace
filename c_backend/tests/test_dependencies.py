from dataclasses import replace
from pathlib import Path

from src.api import dependencies
from src.config import AppSettings


def test_basic_and_strong_models_receive_reference_function_calling(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).parents[2]
    settings = replace(
        AppSettings.from_env(repository_root),
        database_url="",
        gemini_api_key="test-key",
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        llm_provider="gemini",
    )
    configured_agents = []

    class RecordingAgent:
        def __init__(self, **configuration) -> None:
            configured_agents.append(configuration)

    monkeypatch.setattr(
        dependencies,
        "GeminiCorporateActionAgent",
        RecordingAgent,
    )

    dependencies.build_pipeline(settings)

    assert len(configured_agents) == 2
    basic, strong = configured_agents
    assert basic["toolbox"] is strong["toolbox"]
    assert basic["include_pdf_tools"] is False
    assert strong["include_pdf_tools"] is True
    assert "max_remote_calls" not in basic
    assert "max_remote_calls" not in strong

from src.agent.cascade import CascadingCorporateActionExtractor
from src.agent.deterministic import PythonCorporateActionExtractor
from src.agent.gemini import GeminiCorporateActionAgent
from src.agent.pdf_tools import build_pdfplumber_tools
from src.agent.preliminary import build_preliminary_validator
from src.agent.reference_tool import build_reference_lookup_tool
from src.agent.skill_loader import load_project_agent_skills
from src.config import AppSettings
from src.documents.preprocessor import DocumentPreprocessor
from src.pipeline.processor import ProcessingPipeline
from src.persistence import PostgresArtifactRepository
from src.tools.reference import GoldenRecordRepository


class ProviderNotConfiguredError(RuntimeError):
    pass


def build_pipeline(settings: AppSettings) -> ProcessingPipeline:
    if settings.gemini_api_key and settings.llm_provider != "gemini":
        raise ProviderNotConfiguredError(
            f"unsupported LLM provider: {settings.llm_provider}"
        )

    skill_text = load_project_agent_skills(settings.repository_root)
    reference_repository = GoldenRecordRepository.from_csv(
        settings.golden_records_path
    )
    reference_lookup_tool = build_reference_lookup_tool(reference_repository)
    artifact_repository = (
        PostgresArtifactRepository(settings.database_url)
        if settings.database_url
        else None
    )
    return ProcessingPipeline(
        preprocessor=DocumentPreprocessor(
            native_text_min_chars=settings.native_text_min_chars,
            ocr_language=settings.ocr_language,
            ocr_dpi=settings.ocr_dpi,
        ),
        agent=CascadingCorporateActionExtractor(
            python_extractor=PythonCorporateActionExtractor(),
            basic_agent=(
                GeminiCorporateActionAgent(
                    api_key=settings.gemini_api_key,
                    model=settings.llm_basic_model,
                    skill_text=skill_text,
                )
                if settings.gemini_api_key
                else None
            ),
            strong_agent=(
                GeminiCorporateActionAgent(
                    api_key=settings.gemini_api_key,
                    model=settings.llm_strong_model,
                    skill_text=skill_text,
                    reference_lookup_tool=reference_lookup_tool,
                    pdf_tools_builder=build_pdfplumber_tools,
                )
                if settings.gemini_api_key
                else None
            ),
            preliminary_validator=build_preliminary_validator(
                reference_repository
            ),
        ),
        reference_repository=reference_repository,
        output_dir=settings.output_dir,
        artifact_repository=artifact_repository,
    )

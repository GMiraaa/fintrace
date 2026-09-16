from pydantic import Field

from src.models.enums import ExtractionMethod
from src.models.schemas import StrictModel


class NormalizedPage(StrictModel):
    page_number: int = Field(ge=1)
    text: str
    extraction_method: ExtractionMethod
    native_text_length: int = Field(ge=0)
    ocr_applied: bool = False
    warnings: list[str] = Field(default_factory=list)


class NormalizedDocument(StrictModel):
    file_name: str = Field(min_length=1)
    source_path: str | None = Field(default=None, exclude=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    pages: list[NormalizedPage] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @property
    def extraction_methods(self) -> list[ExtractionMethod]:
        return list(dict.fromkeys(page.extraction_method for page in self.pages))

    def as_prompt_text(self) -> str:
        sections = []
        for page in self.pages:
            sections.append(
                f"--- PAGE {page.page_number} "
                f"[{page.extraction_method.value}] ---\n{page.text.strip()}"
            )
        return "\n\n".join(sections)

from pathlib import Path

import pytest

from src.documents.preprocessor import CorruptPdfError, DocumentPreprocessor
from src.models.enums import ExtractionMethod

DATA_DIR = Path(__file__).parents[2] / "a_data/a_input"


def test_native_pdf_does_not_invoke_ocr() -> None:
    def unexpected_ocr(*_args):
        raise AssertionError("OCR must not run for a native text page")

    preprocessor = DocumentPreprocessor(ocr_function=unexpected_ocr)

    document = preprocessor.preprocess(
        DATA_DIR / "01_energetica_vale_tiete_dividendo.pdf"
    )

    assert document.page_count == 1
    assert document.pages[0].extraction_method is ExtractionMethod.NATIVE_TEXT
    assert "Pagamento de Dividendos" in document.pages[0].text
    assert document.pages[0].ocr_applied is False


def test_scanned_pdf_invokes_ocr() -> None:
    calls = []

    def fake_ocr(image, language):
        calls.append((image.size, image.mode, language))
        return "TELECOM NORTE PARTICIPAÇÕES S.A.\nJuros sobre Capital Próprio"

    preprocessor = DocumentPreprocessor(ocr_function=fake_ocr)

    document = preprocessor.preprocess(DATA_DIR / "07_telecom_norte_jcp_SCAN.pdf")

    assert len(calls) == 2
    assert all(call[2] == "por" for call in calls)
    assert {call[1] for call in calls} == {"1", "L"}
    assert document.pages[0].extraction_method is ExtractionMethod.OCR
    assert document.pages[0].ocr_applied is True
    assert "Juros sobre Capital Próprio" in document.pages[0].text


def test_prompt_text_preserves_page_and_method() -> None:
    preprocessor = DocumentPreprocessor(ocr_function=lambda *_: "scanned content")
    document = preprocessor.preprocess(DATA_DIR / "07_telecom_norte_jcp_SCAN.pdf")

    prompt = document.as_prompt_text()

    assert "--- PAGE 1 [OCR] ---" in prompt
    assert "scanned content" in prompt


def test_corrupt_pdf_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nnot a valid pdf")

    with pytest.raises(CorruptPdfError):
        DocumentPreprocessor().preprocess(path)

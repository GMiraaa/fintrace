from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

from src.models.enums import ExtractionMethod

from .models import NormalizedDocument, NormalizedPage

OcrFunction = Callable[[Image.Image, str], str]


class DocumentProcessingError(RuntimeError):
    """Erro-base para falhas que impedem a normalização do documento."""


class CorruptPdfError(DocumentProcessingError):
    pass


class EmptyPdfError(DocumentProcessingError):
    pass


class OcrProcessingError(DocumentProcessingError):
    pass


class DocumentPreprocessor:
    def __init__(
        self,
        *,
        native_text_min_chars: int = 80,
        ocr_language: str = "por",
        ocr_dpi: int = 300,
        ocr_function: OcrFunction | None = None,
    ) -> None:
        if native_text_min_chars < 0:
            raise ValueError("native_text_min_chars must be non-negative")
        if ocr_dpi < 72:
            raise ValueError("ocr_dpi must be at least 72")
        self.native_text_min_chars = native_text_min_chars
        self.ocr_language = ocr_language
        self.ocr_dpi = ocr_dpi
        self.ocr_function = ocr_function or _tesseract_ocr

    def preprocess(self, path: str | Path) -> NormalizedDocument:
        pdf_path = Path(path)
        digest = _sha256(pdf_path)

        try:
            document = pymupdf.open(pdf_path)
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise CorruptPdfError(f"unable to open PDF: {pdf_path.name}") from exc

        try:
            if document.needs_pass:
                raise CorruptPdfError("password-protected PDFs are not supported")
            if document.page_count == 0:
                raise EmptyPdfError("PDF contains no pages")

            pages = [self._process_page(page) for page in document]
        finally:
            document.close()

        warnings = [
            warning
            for page in pages
            for warning in page.warnings
        ]
        return NormalizedDocument(
            file_name=pdf_path.name,
            source_path=str(pdf_path.resolve()),
            sha256=digest,
            page_count=len(pages),
            pages=pages,
            warnings=warnings,
        )

    def _process_page(self, page: pymupdf.Page) -> NormalizedPage:
        native_text = page.get_text("text").strip()
        native_length = len("".join(native_text.split()))
        page_number = page.number + 1

        if native_length >= self.native_text_min_chars:
            return NormalizedPage(
                page_number=page_number,
                text=native_text,
                extraction_method=ExtractionMethod.NATIVE_TEXT,
                native_text_length=native_length,
            )

        try:
            image = self._render_page(page)
            ocr_candidates = [
                self.ocr_function(candidate, self.ocr_language).strip()
                for candidate in _prepare_ocr_images(image)
            ]
            ocr_text = max(ocr_candidates, key=_ocr_text_score, default="")
        except Exception as exc:
            raise OcrProcessingError(
                f"OCR failed on page {page_number}"
            ) from exc

        warnings: list[str] = []
        if not ocr_text:
            warnings.append(f"Page {page_number} remained unreadable after OCR.")
            ocr_text = native_text

        return NormalizedPage(
            page_number=page_number,
            text=ocr_text,
            extraction_method=ExtractionMethod.OCR,
            native_text_length=native_length,
            ocr_applied=True,
            warnings=warnings,
        )

    def _render_page(self, page: pymupdf.Page) -> Image.Image:
        scale = self.ocr_dpi / 72
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            alpha=False,
            colorspace=pymupdf.csRGB,
        )
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tesseract_ocr(image: Image.Image, language: str) -> str:
    return pytesseract.image_to_string(
        image,
        lang=language,
        config="--oem 3 --psm 6",
    )


def _prepare_ocr_images(image: Image.Image) -> list[Image.Image]:
    grayscale = ImageOps.grayscale(image)
    contrasted = ImageOps.autocontrast(grayscale, cutoff=1)
    denoised = contrasted.filter(ImageFilter.MedianFilter(size=3))
    sharpened = denoised.filter(
        ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=3)
    )
    threshold = _otsu_threshold(sharpened)
    binary = sharpened.point(
        lambda pixel: 255 if pixel > threshold else 0,
        mode="1",
    )
    return [sharpened, binary]


def _otsu_threshold(image: Image.Image) -> int:
    histogram = image.histogram()
    total = sum(histogram)
    weighted_total = sum(index * count for index, count in enumerate(histogram))
    background_weight = 0
    background_sum = 0
    best_variance = -1.0
    best_threshold = 127

    for threshold, count in enumerate(histogram):
        background_weight += count
        if background_weight == 0:
            continue
        foreground_weight = total - background_weight
        if foreground_weight == 0:
            break
        background_sum += threshold * count
        background_mean = background_sum / background_weight
        foreground_mean = (
            weighted_total - background_sum
        ) / foreground_weight
        variance = (
            background_weight
            * foreground_weight
            * (background_mean - foreground_mean) ** 2
        )
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold
    return best_threshold


def _ocr_text_score(text: str) -> tuple[int, int, int]:
    useful_characters = sum(character.isalnum() for character in text)
    words = sum(len(word) >= 3 for word in text.split())
    replacement_characters = text.count("�")
    return useful_characters, words, -replacement_characters

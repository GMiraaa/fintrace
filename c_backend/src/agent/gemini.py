from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types

from src.documents.models import NormalizedDocument

from .schemas import AgentExtraction
from .toolbox import CorporateActionToolbox


class AgentProviderError(RuntimeError):
    pass


class AgentProviderUnavailableError(AgentProviderError):
    pass


class AgentStructuredOutputError(AgentProviderError):
    pass


class GeminiCorporateActionAgent:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        skill_text: str,
        toolbox: CorporateActionToolbox | None = None,
        include_pdf_tools: bool = True,
        max_remote_calls: int = 3,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ValueError("Gemini API key is required")
        if not model:
            raise ValueError("Gemini model is required")
        if max_remote_calls < 1:
            raise ValueError("max_remote_calls must be positive")
        self.model = model
        self.skill_text = skill_text
        self.toolbox = toolbox
        self.include_pdf_tools = include_pdf_tools
        self.max_remote_calls = max_remote_calls
        self.client = client or genai.Client(api_key=api_key)

    def extract(self, document: NormalizedDocument) -> AgentExtraction:
        return self._extract(document)

    def extract_for_consensus(
        self,
        document: NormalizedDocument,
        *,
        pass_number: int,
    ) -> AgentExtraction:
        focus = (
            "Independent consensus pass. Analyze the document from scratch without "
            "assuming another response is correct. "
            + (
                "Build the primary structured extraction."
                if pass_number == 1
                else "Recheck identifiers, dates, amounts, event classification, and evidence especially carefully."
            )
        )
        return self._extract(document, context=focus)

    def extract_with_context(
        self,
        document: NormalizedDocument,
        *,
        current: AgentExtraction,
        unresolved_fields: list[str],
    ) -> AgentExtraction:
        context = (
            "A previous extraction attempt left the fields below unresolved. "
            "Review the entire document, independently confirm existing values, "
            "and focus on those fields. Preserve explicit disagreements.\n"
            f"UNRESOLVED FIELDS: {unresolved_fields}\n"
            f"CURRENT EXTRACTION: {current.model_dump_json()}"
        )
        return self._extract(document, context=context)

    def _extract(
        self,
        document: NormalizedDocument,
        *,
        context: str | None = None,
    ) -> AgentExtraction:
        prompt = (
            "Extract the corporate action notice below. Return every schema field. "
            "Use null plus the most precise status when a value is unavailable. "
            "Evidence must be a verbatim excerpt from the cited page. Do not perform "
            "arithmetic validation or confidence scoring. Use a tool only when the "
            "normalized document does not provide enough information to verify the "
            "field reliably. Do not call tools for fields already supported by explicit "
            "document evidence. If lookup_golden_record is needed, call it at most once. "
            "Use its result only to detect disagreement; never present reference data "
            "as document evidence.\n\n"
            f"DOCUMENT: {document.file_name}\n\n{document.as_prompt_text()}"
        )
        if context:
            prompt = f"{prompt}\n\nESCALATION CONTEXT:\n{context}"
        tools: list[Callable[..., str]] = (
            self.toolbox.tools_for(
                document,
                include_pdf_tools=self.include_pdf_tools,
            )
            if self.toolbox is not None
            else []
        )
        if (
            self.include_pdf_tools
            and self.toolbox is not None
            and document.source_path
        ):
            prompt = (
                f"{prompt}\n\nPDFPLUMBER TOOLS: Use these tools only when the "
                "normalized text is insufficient, ambiguous, or loses table/layout "
                "relationships. Tool results are document evidence; cite the returned "
                "page number. Do not invent evidence from coordinates alone."
            )
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.skill_text,
                    response_mime_type="application/json",
                    response_schema=_gemini_response_schema(),
                    temperature=0,
                    tools=tools or None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=self.max_remote_calls,
                    ),
                ),
            )
        except Exception as exc:
            detail = _safe_provider_error_detail(exc)
            if _provider_is_temporarily_unavailable(exc):
                raise AgentProviderUnavailableError(
                    f"Gemini is temporarily unavailable ({detail})"
                ) from exc
            raise AgentProviderError(
                f"Gemini extraction request failed ({detail})"
            ) from exc

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, AgentExtraction):
            return parsed
        if parsed is not None:
            try:
                return AgentExtraction.model_validate(parsed)
            except Exception as exc:
                raise AgentStructuredOutputError(
                    "Gemini returned invalid structured output"
                ) from exc

        text = getattr(response, "text", None)
        if not text:
            raise AgentStructuredOutputError(
                "Gemini returned an empty structured response"
            )
        try:
            return AgentExtraction.model_validate_json(text)
        except Exception as exc:
            raise AgentStructuredOutputError(
                "Gemini returned invalid structured output"
            ) from exc


def _provider_is_temporarily_unavailable(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status_code in {408, 429, 500, 502, 503, 504}:
        return True
    error_name = type(error).__name__.lower()
    return isinstance(error, (ConnectionError, TimeoutError, OSError)) or any(
        marker in error_name for marker in ("timeout", "connection", "servererror")
    )


def _gemini_response_schema() -> dict[str, Any]:
    """Return the extraction schema without unsupported Gemini keywords.

    Pydantic emits ``additionalProperties: false`` for the strict extraction
    models. The GenerateContent API rejects that keyword even though strict
    validation remains useful when parsing the returned payload locally.
    """
    schema = AgentExtraction.model_json_schema()
    _remove_schema_keyword(schema, "additionalProperties")
    return schema


def _remove_schema_keyword(value: Any, keyword: str) -> None:
    if isinstance(value, dict):
        value.pop(keyword, None)
        for child in value.values():
            _remove_schema_keyword(child, keyword)
    elif isinstance(value, list):
        for child in value:
            _remove_schema_keyword(child, keyword)


def _safe_provider_error_detail(error: Exception) -> str:
    """Expose an actionable provider error without leaking credentials."""
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = getattr(error, "message", None) or str(error)
    detail = f"{type(error).__name__}"
    if status is not None:
        detail += f" status={status}"
    if message:
        sanitized = re.sub(
            r"(?i)((?:api[_-]?key|key|token)=)[^&\s]+",
            r"\1<redacted>",
            str(message),
        )
        detail += f": {sanitized[:500]}"
    return detail

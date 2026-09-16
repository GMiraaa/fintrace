from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from src.documents.models import NormalizedDocument

from .schemas import AgentExtraction


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
        reference_lookup_tool: Callable[..., str] | None = None,
        pdf_tools_builder: (
            Callable[[str | Path], list[Callable[..., str]]] | None
        ) = None,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ValueError("Gemini API key is required")
        if not model:
            raise ValueError("Gemini model is required")
        self.model = model
        self.skill_text = skill_text
        self.reference_lookup_tool = reference_lookup_tool
        self.pdf_tools_builder = pdf_tools_builder
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
            "arithmetic validation or confidence scoring. When identifiers are present "
            "and the lookup_golden_record tool is available, call it exactly once to "
            "check the extracted identity. Use the result only to detect disagreement; "
            "never present reference data as document evidence.\n\n"
            f"DOCUMENT: {document.file_name}\n\n{document.as_prompt_text()}"
        )
        if context:
            prompt = f"{prompt}\n\nESCALATION CONTEXT:\n{context}"
        tools: list[Callable[..., str]] = []
        if self.reference_lookup_tool is not None:
            tools.append(self.reference_lookup_tool)
        if self.pdf_tools_builder is not None and document.source_path:
            tools.extend(self.pdf_tools_builder(document.source_path))
            tool_requirement = (
                "This is an escalation: call at least one PDFPLUMBER tool before "
                "returning the final structure, choosing the operation that best "
                "addresses the unresolved fields. "
                if context
                else ""
            )
            prompt = (
                f"{prompt}\n\nPDFPLUMBER TOOLS: {tool_requirement}Use these tools when the "
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
                    response_schema=AgentExtraction,
                    temperature=0,
                    tools=tools or None,
                ),
            )
        except Exception as exc:
            if _provider_is_temporarily_unavailable(exc):
                raise AgentProviderUnavailableError(
                    "Gemini is temporarily unavailable"
                ) from exc
            raise AgentProviderError("Gemini extraction request failed") from exc

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

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from src.documents.models import NormalizedDocument, NormalizedPage
from src.models.enums import (
    EventType,
    FieldStatus,
    RatioKind,
    TaxTreatment,
)
from src.models.schemas import RatioValue

from .schemas import (
    AgentExtraction,
    ExtractedClassificationSignal,
    ExtractedEvidence,
    ExtractedField,
)

DATE_VALUE = r"(?P<value>\d{1,2}[/-]\d{1,2}[/-]\d{4})"
MONEY_VALUE = r"(?P<value>\d{1,3}(?:\.\d{3})*,\d+)"
PORTUGUESE_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


class PythonCorporateActionExtractor:
    """Extrai somente padrões explícitos e verificáveis no texto normalizado."""

    name = "python"

    def extract(self, document: NormalizedDocument) -> AgentExtraction:
        extraction = AgentExtraction()
        for page in document.pages:
            self._extract_identity(extraction, page)
            self._extract_event(extraction, page)
            self._extract_dates(extraction, page)
            self._extract_financials(extraction, page)
        return extraction

    def _extract_identity(
        self,
        extraction: AgentExtraction,
        page: NormalizedPage,
    ) -> None:
        first_line = next(
            (line.strip() for line in page.text.splitlines() if line.strip()),
            "",
        )
        if re.search(r"\bS\.?A\.?$", first_line, re.IGNORECASE):
            _set_if_unknown(extraction.issuer.name, first_line, page, first_line)

        _set_from_match(
            extraction.issuer.cnpj,
            _search(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", page.text),
            page,
        )
        _set_from_match(
            extraction.security.isin,
            _search(r"\bBR[A-Z0-9]{10}\b", page.text),
            page,
        )
        _set_from_match(
            extraction.security.ticker,
            _search(r"\b[A-Z]{4}\d{1,2}\b", page.text),
            page,
        )

        share_match = _search(
            r"(?:ação|acoes|ações)\s+(?P<value>ordinária|preferencial)",
            page.text,
            flags=re.IGNORECASE,
        )
        if share_match:
            share_class = (
                "ON"
                if _fold(share_match.group("value")) == "ordinaria"
                else "PN"
            )
            _set_if_unknown(
                extraction.security.share_class,
                share_class,
                page,
                share_match.group(0),
            )
        else:
            abbreviation = _search(r"\((?P<value>ON|PN)\)", page.text)
            if abbreviation:
                _set_if_unknown(
                    extraction.security.share_class,
                    abbreviation.group("value"),
                    page,
                    abbreviation.group(0),
                )

    def _extract_event(
        self,
        extraction: AgentExtraction,
        page: NormalizedPage,
    ) -> None:
        patterns = (
            (
                EventType.JCP,
                r"juros sobre (?:o )?capital pr[oó]prio|"
                r"remunera[cç][aã]o do capital pr[oó]prio",
            ),
            (EventType.BONUS_SHARES, r"bonifica[cç][aã]o em a[cç][oõ]es"),
            (EventType.REVERSE_SPLIT, r"grupamento de a[cç][oõ]es|\binplit\b"),
            (EventType.STOCK_SPLIT, r"desdobramento de a[cç][oõ]es|\bsplit\b"),
            (EventType.DIVIDEND, r"dividendos?(?:\s+intercalares?)?"),
        )
        for event_type, pattern in patterns:
            match = _search(pattern, page.text, flags=re.IGNORECASE)
            if not match:
                continue
            current = extraction.corporate_action.event_type
            if current.value is None:
                _set_if_unknown(current, event_type, page, match.group(0))
                extraction.corporate_action.classification_evidence.append(
                    ExtractedClassificationSignal(
                        supports=event_type,
                        rationale="Termo econômico explícito identificado pelo extrator Python.",
                        source=ExtractedEvidence(
                            page=page.page_number,
                            evidence=match.group(0),
                        ),
                    )
                )
            # A ordem prioriza a substância de JCP sobre um título de dividendos.
            if event_type is EventType.JCP:
                current.value = event_type
                current.status = FieldStatus.EXTRACTED
                current.sources = [
                    ExtractedEvidence(
                        page=page.page_number,
                        evidence=match.group(0),
                    )
                ]
            return

    def _extract_dates(
        self,
        extraction: AgentExtraction,
        page: NormalizedPage,
    ) -> None:
        dates = extraction.corporate_action.dates
        date_patterns = (
            (dates.approval_date, rf"Data de aprova[cç][aã]o[^\n]*\s+{DATE_VALUE}"),
            (
                dates.record_date,
                rf"Data-base(?: do grupamento)?[^\n]*\s+{DATE_VALUE}",
            ),
            (
                dates.ex_date,
                rf"(?:Data\s+[‘“\"']?ex[^\n]*|In[ií]cio da negocia[cç][aã]o grupada)"
                rf"\s+{DATE_VALUE}",
            ),
            (dates.payment_date, rf"Data de pagamento[^\n]*\s+{DATE_VALUE}"),
            (
                dates.credit_date,
                rf"Cr[eé]dito das a[cç][oõ]es bonificadas[^\n]*\s+{DATE_VALUE}",
            ),
        )
        for field, pattern in date_patterns:
            match = _search(pattern, page.text, flags=re.IGNORECASE)
            if match:
                _set_if_unknown(
                    field,
                    _parse_date(match.group("value")),
                    page,
                    match.group(0),
                )

        if dates.approval_date.status is FieldStatus.UNKNOWN:
            narrative_approval = _search(
                r"(?:reuni[aã]o|Assembleia Geral Extraordin[aá]ria)"
                r"(?:\s+realizada)?\s+(?:em|de)\s+"
                r"(?P<day>\d{1,2})\s+de\s+"
                r"(?P<month>[A-Za-zÀ-ÿ]+)\s+de\s+"
                r"(?P<year>\d{4})",
                page.text,
                flags=re.IGNORECASE,
            )
            if narrative_approval:
                _set_if_unknown(
                    dates.approval_date,
                    _parse_portuguese_date(narrative_approval),
                    page,
                    narrative_approval.group(0),
                )

        fraction_match = _search(
            rf"Per[ií]odo de ajuste de fra[cç][oõ]es[^\n]*\s+"
            rf"(?P<start>\d{{1,2}}/\d{{1,2}}/\d{{4}})\s+a\s+"
            rf"(?P<end>\d{{1,2}}/\d{{1,2}}/\d{{4}})",
            page.text,
            flags=re.IGNORECASE,
        )
        if fraction_match:
            evidence = fraction_match.group(0)
            _set_if_unknown(
                dates.fraction_period_start,
                _parse_date(fraction_match.group("start")),
                page,
                evidence,
            )
            _set_if_unknown(
                dates.fraction_period_end,
                _parse_date(fraction_match.group("end")),
                page,
                evidence,
            )

        not_disclosed = _search(
            r"data de pagamento ser[aá] [^.\n]*(?:definida|divulgada)[^.\n]*",
            page.text,
            flags=re.IGNORECASE,
        )
        if not_disclosed and dates.payment_date.value is None:
            _set_if_unknown(
                dates.payment_date,
                None,
                page,
                not_disclosed.group(0),
                status=FieldStatus.NOT_DISCLOSED,
            )

    def _extract_financials(
        self,
        extraction: AgentExtraction,
        page: NormalizedPage,
    ) -> None:
        financials = extraction.corporate_action.financials
        money_patterns = (
            (
                financials.gross_amount_per_share,
                rf"Valor bruto por a[cç][aã]o[^\n]*(?:\s*\([^\n]+\))?\s*R\$\s*{MONEY_VALUE}",
            ),
            (
                financials.net_amount_per_share,
                rf"Valor l[ií]quido por a[cç][aã]o[^\n]*(?:\s*\([^\n]+\))?\s*R\$\s*{MONEY_VALUE}",
            ),
            (
                financials.attributed_cost_per_share,
                rf"Custo atribu[ií]do[^\n]*\s*R\$\s*{MONEY_VALUE}",
            ),
        )
        monetary_match = None
        for field, pattern in money_patterns:
            match = _search(pattern, page.text, flags=re.IGNORECASE)
            if match:
                monetary_match = monetary_match or match
                _set_if_unknown(
                    field,
                    _parse_decimal(match.group("value")),
                    page,
                    match.group(0),
                )

        if monetary_match:
            _set_if_unknown(
                financials.currency,
                "BRL",
                page,
                monetary_match.group(0),
            )

        tax_match = _search(
            r"(?:IRRF na fonte|Imposto de Renda Retido na\s+Fonte)\s*(?P<value>\d+(?:,\d+)?)%",
            page.text,
            flags=re.IGNORECASE,
        )
        if tax_match:
            _set_if_unknown(
                financials.tax_rate_percent,
                _parse_decimal(tax_match.group("value")),
                page,
                tax_match.group(0),
            )

        dependent_tax = _search(
            r"al[ií]quota[^.]{0,300}(?:por benefici[aá]rio|condi[cç][aã]o do benefici[aá]rio)",
            page.text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        uniform_tax = _search(
            r"(?:incidir[aá]|reten[cç][aã]o de)\s+Imposto de Renda[^.\n]*",
            page.text,
            flags=re.IGNORECASE,
        )
        if dependent_tax:
            _set_if_unknown(
                financials.tax_treatment,
                TaxTreatment.TAX_DEPENDS_ON_BENEFICIARY,
                page,
                dependent_tax.group(0),
            )
        elif uniform_tax:
            _set_if_unknown(
                financials.tax_treatment,
                TaxTreatment.TAX_RULE_UNIFORM,
                page,
                uniform_tax.group(0),
            )

        ratio_match = _search(
            r"Propor[cç][aã]o\s+(?P<numerator>\d+)\s*:\s*(?P<denominator>\d+)",
            page.text,
            flags=re.IGNORECASE,
        ) or _search(
            r"Propor[cç][aã]o\s+(?P<numerator>\d+)\s+a[cç][aã]o nova para cada\s+"
            r"(?P<denominator>\d+)\s+a[cç][oõ]es(?:\s*\((?P<percentage>\d+(?:,\d+)?)%\))?",
            page.text,
            flags=re.IGNORECASE,
        )
        if ratio_match:
            event_type = extraction.corporate_action.event_type.value
            numerator = _parse_decimal(ratio_match.group("numerator"))
            denominator = _parse_decimal(ratio_match.group("denominator"))
            if event_type is EventType.REVERSE_SPLIT:
                numerator, denominator = denominator, numerator
            kind = (
                RatioKind.NEW_PER_EXISTING
                if event_type is EventType.BONUS_SHARES
                else RatioKind.RESULTING_PER_EXISTING
            )
            percentage = ratio_match.groupdict().get("percentage")
            _set_if_unknown(
                financials.ratio,
                RatioValue(
                    kind=kind,
                    numerator=numerator,
                    denominator=denominator,
                    percentage=(
                        _parse_decimal(percentage) if percentage else None
                    ),
                ),
                page,
                ratio_match.group(0),
            )


def _search(pattern: str, text: str, *, flags: int = 0) -> re.Match[str] | None:
    return re.search(pattern, text, flags | re.MULTILINE)


def _set_from_match(
    field: ExtractedField[Any],
    match: re.Match[str] | None,
    page: NormalizedPage,
) -> None:
    if match:
        value = match.groupdict().get("value") or match.group(0)
        _set_if_unknown(field, value, page, match.group(0))


def _set_if_unknown(
    field: ExtractedField[Any],
    value: Any,
    page: NormalizedPage,
    evidence: str,
    *,
    status: FieldStatus = FieldStatus.EXTRACTED,
) -> None:
    if field.status is not FieldStatus.UNKNOWN:
        return
    field.value = value
    field.status = status
    field.sources = [
        ExtractedEvidence(page=page.page_number, evidence=evidence.strip())
    ]


def _parse_date(value: str) -> date:
    day, month, year = (int(part) for part in re.split(r"[/-]", value))
    return date(year, month, day)


def _parse_decimal(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def _parse_portuguese_date(match: re.Match[str]) -> date:
    month_name = _fold(match.group("month"))
    month = PORTUGUESE_MONTHS[month_name]
    return date(
        int(match.group("year")),
        month,
        int(match.group("day")),
    )


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()

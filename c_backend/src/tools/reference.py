from __future__ import annotations

import csv
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from src.models.schemas import (
    ReferenceConflict,
    ReferenceRecord,
    ReferenceValidation,
)

from .normalization import (
    normalize_cnpj,
    normalize_isin,
    normalize_issuer,
    normalize_share_class,
    normalize_ticker,
)

REQUIRED_COLUMNS = {
    "emissor",
    "cnpj",
    "isin",
    "ticker",
    "classe",
    "segmento_listagem",
    "status",
}

Normalizer = Callable[[str | None], str | None]

FIELD_NORMALIZERS: dict[str, Normalizer] = {
    "issuer": normalize_issuer,
    "cnpj": normalize_cnpj,
    "isin": normalize_isin,
    "ticker": normalize_ticker,
    "share_class": normalize_share_class,
}

CONFLICT_CODES = {
    "issuer": "REF_ISSUER_CONFLICT",
    "cnpj": "REF_CNPJ_CONFLICT",
    "isin": "REF_ISIN_CONFLICT",
    "ticker": "REF_TICKER_CONFLICT",
    "share_class": "REF_SHARE_CLASS_CONFLICT",
}


class GoldenRecordRepository:
    def __init__(self, records: list[ReferenceRecord]) -> None:
        self.records = records
        self._ensure_unique_identifiers()

    @classmethod
    def from_csv(cls, path: str | Path) -> GoldenRecordRepository:
        csv_path = Path(path)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            columns = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - columns
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise ValueError(f"golden records missing columns: {missing_list}")

            records = [
                ReferenceRecord(
                    issuer=row["emissor"].strip(),
                    cnpj=row["cnpj"].strip(),
                    isin=row["isin"].strip(),
                    ticker=row["ticker"].strip(),
                    share_class=row["classe"].strip(),
                    listing_segment=row["segmento_listagem"].strip(),
                    status=row["status"].strip(),
                )
                for row in reader
            ]

        if not records:
            raise ValueError("golden records file is empty")
        return cls(records)

    def lookup(
        self,
        *,
        issuer: str | None = None,
        cnpj: str | None = None,
        isin: str | None = None,
        ticker: str | None = None,
        share_class: str | None = None,
    ) -> ReferenceValidation:
        observed = {
            "issuer": issuer,
            "cnpj": cnpj,
            "isin": isin,
            "ticker": ticker,
            "share_class": share_class,
        }
        normalized = {
            field: FIELD_NORMALIZERS[field](value)
            for field, value in observed.items()
        }

        matches = {
            field: self._matching_indexes(field, value)
            for field, value in normalized.items()
            if value is not None
        }

        selected_index, identity_conflict = self._select_record(matches)
        if identity_conflict:
            candidates = sorted(
                set().union(*(matches.get(field, set()) for field in ("isin", "cnpj")))
            )
            return ReferenceValidation(
                exact_match=False,
                conflicts=[
                    ReferenceConflict(
                        code="REF_STRONG_IDENTIFIER_CONFLICT",
                        field="identity",
                        expected="ISIN and CNPJ must identify the same record",
                        observed={"isin": isin, "cnpj": cnpj},
                    )
                ],
                possible_matches=[self.records[index] for index in candidates],
            )

        if selected_index is None:
            return ReferenceValidation(
                exact_match=False,
                possible_matches=self._possible_matches(normalized.get("issuer")),
            )

        record = self.records[selected_index]
        matched_by: list[str] = []
        conflicts: list[ReferenceConflict] = []

        for field, raw_value in observed.items():
            normalized_value = normalized[field]
            if normalized_value is None:
                continue
            reference_value = getattr(record, field)
            normalized_reference = FIELD_NORMALIZERS[field](reference_value)
            if normalized_value == normalized_reference:
                matched_by.append(field)
            else:
                conflicts.append(
                    ReferenceConflict(
                        code=CONFLICT_CODES[field],
                        field=field,
                        expected=reference_value,
                        observed=raw_value,
                    )
                )

        return ReferenceValidation(
            exact_match=bool(matched_by) and not conflicts,
            matched_by=matched_by,
            reference_record=record,
            conflicts=conflicts,
        )

    def _matching_indexes(self, field: str, value: str | None) -> set[int]:
        if value is None:
            return set()
        normalizer = FIELD_NORMALIZERS[field]
        return {
            index
            for index, record in enumerate(self.records)
            if normalizer(getattr(record, field)) == value
        }

    @staticmethod
    def _select_record(matches: dict[str, set[int]]) -> tuple[int | None, bool]:
        strong_nonempty = [
            matches[field]
            for field in ("isin", "cnpj")
            if matches.get(field)
        ]
        if len(strong_nonempty) > 1:
            intersection = set.intersection(*strong_nonempty)
            if len(intersection) == 1:
                return next(iter(intersection)), False
            if not intersection:
                return None, True

        if strong_nonempty:
            candidates = set.union(*strong_nonempty)
            if len(candidates) == 1:
                return next(iter(candidates)), False

        for field in ("ticker", "issuer"):
            candidates = matches.get(field, set())
            if len(candidates) == 1:
                return next(iter(candidates)), False
        return None, False

    def _possible_matches(self, issuer: str | None) -> list[ReferenceRecord]:
        if issuer is None:
            return []
        scored = []
        for record in self.records:
            normalized_reference = normalize_issuer(record.issuer)
            if normalized_reference is None:
                continue
            score = SequenceMatcher(None, issuer, normalized_reference).ratio()
            if score >= 0.72:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].issuer))
        return [record for _, record in scored[:3]]

    def _ensure_unique_identifiers(self) -> None:
        for field in ("isin", "cnpj", "ticker"):
            normalizer = FIELD_NORMALIZERS[field]
            seen: dict[str, str] = {}
            for record in self.records:
                normalized = normalizer(getattr(record, field))
                if normalized is None:
                    continue
                if normalized in seen:
                    raise ValueError(
                        f"duplicate {field} in golden records: "
                        f"{getattr(record, field)}"
                    )
                seen[normalized] = record.issuer


def lookup_reference(
    repository: GoldenRecordRepository,
    *,
    issuer: str | None = None,
    cnpj: str | None = None,
    isin: str | None = None,
    ticker: str | None = None,
    share_class: str | None = None,
) -> ReferenceValidation:
    return repository.lookup(
        issuer=issuer,
        cnpj=cnpj,
        isin=isin,
        ticker=ticker,
        share_class=share_class,
    )

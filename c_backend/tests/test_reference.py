from pathlib import Path

import pytest

from src.models.schemas import ReferenceRecord
from src.tools.reference import GoldenRecordRepository, lookup_reference


@pytest.fixture
def records() -> list[ReferenceRecord]:
    return [
        ReferenceRecord(
            issuer="Companhia Alfa S.A.",
            cnpj="11.111.111/0001-11",
            isin="BRALFAACNOR1",
            ticker="ALFA3",
            share_class="ON",
            listing_segment="Novo Mercado",
            status="ativo",
        ),
        ReferenceRecord(
            issuer="Companhia Beta S.A.",
            cnpj="22.222.222/0001-22",
            isin="BRBETAACNPR2",
            ticker="BETA4",
            share_class="PN",
            listing_segment="Nível 1",
            status="ativo",
        ),
    ]


@pytest.fixture
def repository(records: list[ReferenceRecord]) -> GoldenRecordRepository:
    return GoldenRecordRepository(records)


def test_exact_match_uses_all_provided_fields(
    repository: GoldenRecordRepository,
) -> None:
    result = lookup_reference(
        repository,
        issuer="COMPANHIA ALFA SA",
        cnpj="11.111.111/0001-11",
        isin="BRALFAACNOR1",
        ticker="alfa3",
        share_class="Ação ordinária",
    )

    assert result.exact_match is True
    assert result.reference_record is not None
    assert result.reference_record.ticker == "ALFA3"
    assert set(result.matched_by) == {
        "issuer",
        "cnpj",
        "isin",
        "ticker",
        "share_class",
    }
    assert result.conflicts == []


def test_isin_selects_record_and_exposes_ticker_conflict(
    repository: GoldenRecordRepository,
) -> None:
    result = lookup_reference(
        repository,
        isin="BRALFAACNOR1",
        ticker="BETA4",
    )

    assert result.exact_match is False
    assert result.reference_record is not None
    assert result.reference_record.ticker == "ALFA3"
    assert result.matched_by == ["isin"]
    assert result.conflicts[0].code == "REF_TICKER_CONFLICT"


def test_strong_identifiers_cannot_select_different_records(
    repository: GoldenRecordRepository,
) -> None:
    result = lookup_reference(
        repository,
        isin="BRALFAACNOR1",
        cnpj="22.222.222/0001-22",
    )

    assert result.exact_match is False
    assert result.reference_record is None
    assert result.conflicts[0].code == "REF_STRONG_IDENTIFIER_CONFLICT"
    assert {match.ticker for match in result.possible_matches} == {"ALFA3", "BETA4"}


def test_fuzzy_issuer_only_suggests_possible_match(
    repository: GoldenRecordRepository,
) -> None:
    result = lookup_reference(repository, issuer="Compania Alfa")

    assert result.exact_match is False
    assert result.reference_record is None
    assert result.possible_matches[0].ticker == "ALFA3"


def test_unknown_reference_returns_no_match(
    repository: GoldenRecordRepository,
) -> None:
    result = lookup_reference(
        repository,
        isin="BRUNKNOWN000",
        ticker="XXXX3",
    )

    assert result.exact_match is False
    assert result.reference_record is None
    assert result.possible_matches == []


def test_duplicate_strong_identifier_is_rejected(
    records: list[ReferenceRecord],
) -> None:
    duplicate = records[1].model_copy(update={"isin": records[0].isin})

    with pytest.raises(ValueError, match="duplicate isin"):
        GoldenRecordRepository([records[0], duplicate])


def test_csv_requires_all_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("emissor,cnpj\nCompanhia Alfa,123\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        GoldenRecordRepository.from_csv(csv_path)


def test_project_golden_records_are_loadable() -> None:
    path = Path(__file__).parents[2] / "a_data/c_golden_records/golden_records.csv"
    repository = GoldenRecordRepository.from_csv(path)

    assert len(repository.records) == 12
    result = repository.lookup(isin="BRTIETACNOR3", ticker="TIET3")
    assert result.exact_match is True
    assert result.reference_record is not None
    assert result.reference_record.issuer == "Energética Vale do Tietê S.A."

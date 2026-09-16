import json
from pathlib import Path

from src.agent.reference_tool import build_reference_lookup_tool
from src.tools.reference import GoldenRecordRepository


def test_reference_tool_returns_serialized_validation() -> None:
    root = Path(__file__).parents[2]
    repository = GoldenRecordRepository.from_csv(
        root / "a_data/c_golden_records/golden_records.csv"
    )
    tool = build_reference_lookup_tool(repository)

    result = json.loads(
        tool(
            issuer="Banco Meridional do Brasil S.A.",
            cnpj="60.111.222/0001-55",
            isin="BRBMRDACNPR7",
            ticker="BMRD4",
            share_class="PN",
        )
    )

    assert result["exact_match"] is True
    assert "isin" in result["matched_by"]
    assert result["reference_record"]["ticker"] == "BMRD4"

from src.tools.normalization import (
    normalize_cnpj,
    normalize_isin,
    normalize_issuer,
    normalize_share_class,
    normalize_ticker,
)


def test_normalize_issuer_handles_accents_and_corporate_punctuation() -> None:
    first = normalize_issuer("COMPANHIA SIDERÚRGICA PARANAENSE S.A.")
    second = normalize_issuer("Companhia Siderurgica Paranaense SA")

    assert first == second == "companhia siderurgica paranaense sa"


def test_normalize_cnpj_preserves_leading_zeroes() -> None:
    assert normalize_cnpj("08.777.666/0001-33") == "08777666000133"


def test_normalize_market_identifiers() -> None:
    assert normalize_isin(" br-tietacnor3 ") == "BRTIETACNOR3"
    assert normalize_ticker(" tiet 3 ") == "TIET3"


def test_normalize_share_class_aliases() -> None:
    assert normalize_share_class("Ação ordinária") == "ON"
    assert normalize_share_class("preferencial") == "PN"
    assert normalize_share_class("PNB") == "PNB"


def test_normalizers_preserve_missing_values() -> None:
    assert normalize_issuer(None) is None
    assert normalize_cnpj(None) is None
    assert normalize_isin(None) is None
    assert normalize_ticker(None) is None
    assert normalize_share_class(None) is None

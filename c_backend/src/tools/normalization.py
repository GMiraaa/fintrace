import re
import unicodedata


def _remove_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _remove_accents(value).casefold().strip()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def normalize_issuer(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _remove_accents(value).casefold()
    normalized = re.sub(r"\bs\s*\.\s*a\s*\.?", " sa ", normalized)
    normalized = re.sub(r"\bltda\s*\.?", " ltda ", normalized)
    return normalize_text(normalized)


def normalize_cnpj(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def normalize_isin(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return normalized or None


def normalize_ticker(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return normalized or None


def normalize_share_class(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    aliases = {
        "on": "ON",
        "ordinaria": "ON",
        "acao ordinaria": "ON",
        "acoes ordinarias": "ON",
        "pn": "PN",
        "preferencial": "PN",
        "acao preferencial": "PN",
        "acoes preferenciais": "PN",
        "pna": "PNA",
        "preferencial a": "PNA",
        "pnb": "PNB",
        "preferencial b": "PNB",
        "unit": "UNIT",
        "units": "UNIT",
    }
    return aliases.get(normalized, normalized.upper().replace(" ", "_"))

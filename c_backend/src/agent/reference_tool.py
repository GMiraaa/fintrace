from __future__ import annotations

from collections.abc import Callable

from src.tools.reference import GoldenRecordRepository


def build_reference_lookup_tool(
    repository: GoldenRecordRepository,
) -> Callable[..., str]:
    def lookup_golden_record(
        issuer: str = "",
        cnpj: str = "",
        isin: str = "",
        ticker: str = "",
        share_class: str = "",
    ) -> str:
        """Valida identificadores de um ativo na base canônica do FinTrace.

        Args:
            issuer: Nome do emissor extraído do documento.
            cnpj: CNPJ extraído do documento.
            isin: ISIN extraído do documento.
            ticker: Código de negociação extraído do documento.
            share_class: Classe da ação extraída, como ON ou PN.

        Returns:
            Resultado JSON com correspondências, conflitos e possíveis registros.
        """
        result = repository.lookup(
            issuer=issuer or None,
            cnpj=cnpj or None,
            isin=isin or None,
            ticker=ticker or None,
            share_class=share_class or None,
        )
        return result.model_dump_json()

    return lookup_golden_record

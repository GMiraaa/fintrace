from datetime import date
from decimal import Decimal

from src.models.enums import (
    EventType,
    ExtractionMethod,
    FieldStatus,
    Origin,
    ProcessingStatus,
    TaxTreatment,
)
from src.models.schemas import (
    AuditableField,
    DocumentRecord,
    ReferenceRecord,
    ReferenceValidation,
    SourceDocument,
    SourceEvidence,
)


def document_field(value):
    return AuditableField(
        value=value,
        status=FieldStatus.EXTRACTED,
        origin=Origin.DOCUMENT,
        confidence=0,
        sources=[
            SourceEvidence(
                page=1,
                evidence=f"Evidence for {value}",
                extraction_method=ExtractionMethod.NATIVE_TEXT,
            )
        ],
    )


def valid_document_record() -> DocumentRecord:
    digest = "a" * 64
    record = DocumentRecord(
        document_id=f"sha256:{digest}",
        source_document=SourceDocument(
            file_name="notice.pdf",
            sha256=digest,
            page_count=1,
            extraction_methods=[ExtractionMethod.NATIVE_TEXT],
        ),
        processing_status=ProcessingStatus.ACCEPTED,
    )
    record.issuer.name = document_field("Companhia Alfa S.A.")
    record.issuer.cnpj = document_field("11.111.111/0001-11")
    record.security.isin = document_field("BRALFAACNOR1")
    record.security.ticker = document_field("ALFA3")
    record.security.share_class = document_field("ON")
    record.corporate_action.event_type = document_field(EventType.JCP)
    record.corporate_action.dates.approval_date = document_field(date(2026, 6, 1))
    record.corporate_action.dates.record_date = document_field(date(2026, 6, 16))
    record.corporate_action.dates.ex_date = document_field(date(2026, 6, 17))
    record.corporate_action.dates.payment_date = document_field(date(2026, 8, 14))
    record.corporate_action.financials.gross_amount_per_share = document_field(
        Decimal("0.1738420000")
    )
    record.corporate_action.financials.net_amount_per_share = document_field(
        Decimal("0.1434196500")
    )
    record.corporate_action.financials.tax_rate_percent = document_field(
        Decimal("17.5")
    )
    record.corporate_action.financials.tax_treatment = document_field(
        TaxTreatment.TAX_RULE_UNIFORM
    )
    record.corporate_action.financials.currency = document_field("BRL")
    reference = ReferenceRecord(
        issuer="Companhia Alfa S.A.",
        cnpj="11.111.111/0001-11",
        isin="BRALFAACNOR1",
        ticker="ALFA3",
        share_class="ON",
        listing_segment="Novo Mercado",
        status="ativo",
    )
    record.reference_validation = ReferenceValidation(
        exact_match=True,
        matched_by=["isin", "ticker"],
        reference_record=reference,
    )
    return record

# Evidence and uncertainty

## Evidence

Use the shortest excerpt that proves the value while retaining its meaning.
Record the page and extraction method supplied by the normalized document.
Do not fabricate page numbers or quote text not present in the normalized
document.

Issuer, CNPJ, ISIN, ticker, share class, event type, material dates, monetary
values, tax rates, currency, and ratios require evidence when extracted from
the document.

## Provenance

- `DOCUMENT`: explicitly supported by the notice.
- `REFERENCE`: supplied by the golden record, never by inference from the text.
- `DERIVED`: produced by a deterministic calculation.
- `UNKNOWN`: origin cannot be established.

The interpreting model normally emits document evidence. It may consult the
golden-record lookup tool to detect disagreement, but reference and derived
values are added only by backend tools.

## Absence and uncertainty

- `NOT_DISCLOSED`: the notice explicitly states that the issuer has not yet
  defined or disclosed the value.
- `NOT_APPLICABLE`: the field has no meaning for the classified event.
- `UNREADABLE`: the relevant region exists but cannot be read reliably.
- `AMBIGUOUS`: multiple interpretations remain plausible.
- `CONFLICT`: two explicit pieces of evidence disagree.
- `UNKNOWN`: none of the more precise states applies.

High confidence is compatible with `NOT_DISCLOSED`: confidence describes the
interpretation, not document completeness.

## Contradictions

Record both sides of a material contradiction. Do not resolve identity using
fuzzy name similarity alone. Do not resolve title/body event conflicts by title
precedence. Do not calculate dates or financial values in the interpretation
step; extract the inputs and leave validation to deterministic tools.

---
name: corporate-actions
description: Interpret Brazilian corporate action notices for FinTrace, preserving evidence, uncertainty, provenance, and conflicts. Use for dividend, JCP, bonus share, split, and reverse-split extraction; do not use it to replace deterministic validation.
---

# Corporate Actions

Interpret the entire normalized document, including title, body, tables, and
footnotes. Extract only information supported by document evidence.

## Required behavior

- Prefer the economic substance described in the body over the title alone.
- Preserve conflicting signals instead of silently choosing one.
- Return `UNKNOWN` when evidence does not support a classification or value.
- Return `NOT_DISCLOSED` when the issuer explicitly says a value will be
  defined or disclosed later.
- Never convert missing monetary values, dates, rates, or ratios to zero.
- Never present reference-enriched data as document-extracted data.
- Attach page-level evidence to every material extracted field.
- Escalate ambiguity, unreadable evidence, and material contradictions for
  deterministic routing after extraction.

When the `lookup_golden_record` tool is available, call it at least once and at
most twice after extracting the document identifiers. Use it only to identify
agreement or disagreement; never copy reference values into fields presented as
document extraction.
The backend repeats this lookup and remains authoritative. Do not perform date
ordering, arithmetic validation, confidence calculation, or final review
routing. Backend tools own those deterministic decisions.

Before classifying or extracting a notice, read:

- [Event identification](references/event-identification.md)
- [Evidence and uncertainty](references/evidence-and-uncertainty.md)

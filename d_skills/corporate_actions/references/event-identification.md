# Event identification

Classify from the combined evidence in the title, body, tables, tax language,
ratios, and declared legal or economic nature.

## Dividend

Typical evidence includes distribution of profits or reserves, a per-share
cash amount, record/ex/payment dates, and terms such as `dividendos`,
`dividendos intercalares` or `dividendos intermediários`.

Tax language does not by itself change a dividend into JCP. When tax depends on
the beneficiary or a monthly threshold, extract the stated gross amount but do
not infer one universal net amount.

## Juros sobre capital próprio (JCP)

Typical evidence includes `juros sobre o capital próprio`, `JCP`, remuneration
calculated over equity accounts, reference to the applicable JCP legislation,
imputation to mandatory dividends, withholding tax, or explicit gross and net
amounts.

A notice titled as dividends may still describe JCP in substance. In that
case, classify from the body evidence and preserve the title/body conflict.

## Bonus shares

Typical evidence includes capitalization of reserves or profits, issuance or
credit of new shares, a ratio such as one new share per existing shares, an
attributed tax cost, and treatment of fractions. Do not treat an attributed
tax cost as a cash payment per share.

## Reverse split

Typical evidence includes `grupamento` or `inplit`, consolidation of several
existing shares into fewer resulting shares, no change to total share capital,
and rules for fractions. Represent the ratio as resulting shares per existing
shares.

## Stock split

Typical evidence includes `desdobramento` or `split`, conversion of existing
shares into a larger number of resulting shares, generally without changing
total share capital. Represent the ratio as resulting shares per existing
shares.

## Other and unknown

Use `OTHER` only when the document clearly describes a corporate action that is
outside the controlled enum. Use `UNKNOWN` when the available evidence is
insufficient, unreadable, or materially contradictory.

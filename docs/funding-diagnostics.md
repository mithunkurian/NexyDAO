# Settlement and funding diagnostics

The independent `funding-check` command records why broker funding is denied. It
cannot authorize funding or execution, even when CEO/committee votes or balances
appear favourable. It reads a fresh, signed exact-pin paper receipt and the current
owner policy; stale/wrong-pin evidence or a policy change fails without recording
a successful review. This is an engineering diagnostic, not a new investment agent.

```bash
# Use existing private pin, evidence key, DB and owner-policy environment settings.
python3 -m nexydao broker-state
python3 -m nexydao funding-check
```

The result includes receipt/policy fingerprints, ledger revision, expiry, negative
currency labels, cash-field disagreements, unresolved settlement evidence and
explicit blocking codes. It is persisted in the existing SQLite `funding_reviews`
table and survives restart. It contains no balances, account IDs or raw broker text,
and is excluded from agent decision memory. It makes no OpenAI calls, broker writes,
FX conversions or imports of broker capital/positions. Repeated reviews append
records; they never replenish the existing API budget or modify funding state.

## Receipt version 2

The collector now preserves the exact total `SettledCashByDate` observations in
the private signed receipt, bounded to 40 currencies/4096 characters each and a
131072-byte complete receipt. Segment variants and BASE aggregates are never
combined to create spendable USD cash. Duplicate schedules, changed late schedules,
invalid currencies and oversized receipts fail safely and preserve the old file.
Version 1 receipts remain readable within their original expiry, but their missing
raw schedule cannot be reconstructed or treated as verified settlement evidence.

The diagnostic stores only a digest and redacted character shape of each schedule.
Unknown text is replaced with `unsupported_text`. Even a familiar numeric/date
shape is **syntax only**: the financial meaning, time zone, effective date and
relationship to pending settlements have not been independently established.
No date selection, T+n assumptions, holiday calculation or guessed numeric field
can convert these observations into settled cash. Funding remains denied.

## Negative currency cash investigation

The 12 October signed historical receipt identified negative SEK observations in
both CashBalance and TotalCashBalance. Historical evidence is not fresh funding
evidence. Positive cash in another currency never offsets that diagnostic. Matching
negative fields establish an observation, not whether its cause was a trade, FX,
commission, interest, transfer or a paper-account adjustment.

To establish the cause, obtain the paper-account Activity Statement including
**Statement of Funds** and the per-currency **Cash Report** for the period from a
known prior balance through the negative observation. Keep it private on the VM.
Do not share broker credentials or commit statements. A path may be supplied to
locate existing evidence; no statement importer or provenance certification is
implemented in this milestone. Owner notes or an agent's explanation cannot close
the funding block. No automatic deposit, reset, conversion or repayment is performed.

IBKR describes Statement of Funds as transaction-level cash activity by currency:
[official guide](https://www.ibkrguides.com/reportingreference/reportguide/statementoffunds_default.htm).
The Cash Report distinguishes ending cash and ending settled cash and provides
cash movement categories:
[official cash-report guide](https://www.ibkrguides.com/reportingreference/reportguide/cashreport.htm).
These references support the evidence needed; they do not explain this specific
account or document the Gateway `SettledCashByDate` serialization.

## Acceptance and open gates

### Subsequent statement observation · 13 October

After PR #9 merged (`694241b`), the owner signed into the paper reporting portal.
The displayed Activity Statement for 16 April–12 October was checked against
the private VM account pin. Its SEK Cash Report starts at zero and attributes
the entire ending debit to commissions. Two EUR/USD trades on 13 and 14
September carry those commissions in SEK; the trade total agrees with the cash
movement. The October-only statement carries the same debit forward unchanged.
This establishes a historical explanation from displayed broker evidence,
without claiming who initiated the trades or importing them into NexyDAO.

The statement reports margin capabilities and earlier USD debit interest. The
origin of the USD opening debit is not established. The broker's pre-existing
paper portfolio is separate from NexyDAO's $5,000 simulation ledger.

A manual browser-observation record, clearly labelled as a transcription, was
saved under the private VM runtime statements directory with mode 0600. The
HTML and CSV export attempts returned no downloadable file. No original export
has been archived, no statement importer has been implemented, and this note
does not change `negative_cash_cause` in previously recorded funding cases.
Historical ending settled cash does not resolve the fresh Gateway settlement
serialization or make current funding eligible. No API calls, orders, cash
conversions, balance resets or account-setting changes were performed.

The next gate must validate bounded statement input, account/period/currency
identity and cash arithmetic independently, retain private source provenance,
and account for fees in their charged currency before any funding permission.
The debit explanation alone does not resolve the debit or authorize execution.

### Original diagnostic acceptance

Release `d923b13` passed all 135 tests locally, on Ubuntu VM and in CI, including negative currency isolation, matching-but-denied
funding, unknown schedule text, bounded preservation, owner changes, stale receipts,
backward compatibility and durable reports without ledger/cost mutation. The fresh
13 October paper trial collected six cash rows, zero positions and four raw settlement
observations (three currencies plus BASE). The signed consumer and persisted denial
case passed; the case survived reopening SQLite. SEK negative cash remained observed,
CashBalance/TotalCashBalance agreed by currency, and the cause remained unresolved.
Schedule shapes resembled numeric-prefix/amount pairs, but their semantics were not
certified. The owner confirmed no statement is saved on the VM.
Ledger/revision and API costs were unchanged; receipt mode was 0600 and the host guard
verified. No OpenAI calls or broker writes occurred. An initial startup probe disconnected;
a spaced trial passed, leaving reliability open. Negative-cash cause, supported settlement
semantics, open orders/fills/fees/transfers, capital allocation/FX, stable account
observations and executor isolation remain open. This does not complete M3/M4.

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

135 local tests pass, including negative currency isolation, matching-but-denied
funding, unknown schedule text, bounded preservation, owner changes, stale receipts,
backward compatibility and durable reports without ledger/cost mutation. VM/CI and
fresh version 2 collection are pending. Negative-cash cause, supported settlement
semantics, open orders/fills/fees/transfers, capital allocation/FX, stable account
observations and executor isolation remain open. This does not complete M3/M4.

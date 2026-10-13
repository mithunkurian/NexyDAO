# Current paper capital allocation diagnostic

`allocation-check` defines a USD planning cap separately from the whole paper
account. It is an operator diagnostic with no agent tools, broker reservations,
orders, conversions, balance resets or funding permission. It does not investigate
the owner's prior trades. Current negative currency cash remains a funding block.

## Install and run

Use Python 3.12 and the normal installation in `deployment.md`. No additional
dependencies are needed. Supply the existing protected account pin, evidence key,
owner policy and persistent DB settings through environment variables. Never commit
those files. The application does not automatically source `.env` files.

```bash
export NEXYDAO_ALLOCATION_USD=5000
export NEXYDAO_FEE_RESERVE_USD=50
python3 -m nexydao broker-access-check
python3 -m nexydao broker-state
python3 -m nexydao allocation-check
```

Run the last two commands consecutively: the signed cash/position receipt expires
60 seconds after collection starts. Missing, expired, wrong-account or tampered
evidence fails before recording a review. A fresh collection requires an owner
authenticated IB API paper Gateway on localhost port 4002 and a verified host guard.
These commands make no OpenAI requests. Use the existing persistent DB on the VM;
do not create a replacement DB to replenish the API budget or simulation capital.

The configured allocation must be positive and at most $5,000. Its USD fee reserve
must be positive and smaller than the cap. The default $50 reserve is an engineering
planning buffer, **not** a broker commission quote or investment strategy. Fee
amounts, charged currencies and reserves for other currencies still need validation.

## Meaning of the result

Coverage requires all three explicit USD observations: CashBalance,
TotalCashBalance and SettledCash. The lowest value must cover the allocation.
BASE aggregates, other currency balances, buying power and unparsed settlement
schedules cannot supply missing USD cash. Cash-field disagreement or negative
cash in any currency forces the planning ceiling to zero. Existing simulated
positions or unsettled proceeds require broader allocation accounting and also
force zero in this initial slice.

The allocation-side planning ceiling is the smaller of the cap and simulation
settled cash, minus retained API cost estimates/reservations and the fee buffer.
It is never spendable broker cash or an execution permit. Existing portfolio
exposure and drawdown safeguards still apply separately. A positive ceiling
cannot clear unknown open orders, pending fills, fees, transfers, settlement
semantics, allocation ownership or executor authorization.

Reviews persist in `allocation_reviews`, separate from agent memory and ledger
events. They retain configuration/policy/receipt fingerprints, revision, expiry,
coverage flags and blocking reasons; they omit broker balances and account IDs.
The transaction rechecks receipt expiry, owner policy and ledger revision before
commit. Ledger balances and API costs do not change. Existing `funding-check`
records retain their original interpretation; no historical denial is rewritten.

## Tests and Google Cloud trial

```bash
python3 -m unittest discover -s tests -q
```

The suite covers oversized/invalid caps, incomplete USD cash, foreign debits,
cost exhaustion, policy/expiry rollback and persistence without ledger/cost/memory
mutation. Deploy a tested Git archive into a new isolated VM release directory,
run the same offline suite there, then supply the existing private runtime paths
for a bounded paper trial. Preserve the original VM checkout and credential files.
There is no scheduler or service change in this milestone.

Open orders and reservation collection, authoritative current settlement semantics,
full multi-currency fee accounting, allocation ownership, stable account observations
and independent execution permits remain open. M3/M4 are incomplete; execution
remains unconditionally disabled.

# Read-only cash and position comparison

This slice adds account-specific currency observations and contract-based position
comparison. It does not import broker funds or holdings, convert currencies, submit
orders or certify full reconciliation. The $5,000 ledger remains a USD simulation.

## Operator commands

Use the existing local exact paper-account pin, private evidence key and ledger DB.
Do not paste credentials/account identifiers into command history or Git.

```bash
export NEXYDAO_BROKER_STATE_SNAPSHOT=/private/runtime/broker-state.json
python3 -m nexydao broker-access-check
python3 -m nexydao broker-state
python3 -m nexydao broker-reconcile
```

`broker-state` requires the verified host guard before connecting. `broker-reconcile`
loads the authenticated receipt without connecting or making OpenAI calls. Both
commands retain paper-only configuration and unconditional execution denial.
The receipt contains private cash/holdings and is atomically saved with mode 0600
on Unix; protect its directory and Windows ACLs. Balances/identifiers/symbols are
excluded from the CLI comparison output and agent prompts.

## Collection and validation

The collector supports only legacy protocol 178. The read-only layouts were checked
against official [IBKR API 10.51.01 source](https://interactivebrokers.github.io/downloads/twsapi_macunix.1051.01.zip).
After exact account identity validation it subscribes to that account's values and
waits for `accountDownloadEnd`. It records CashBalance, SettledCash and
TotalCashBalance with actual three-letter currencies. It excludes the aggregate
`BASE` row. Other value tags and unsolicited portfolio callbacks are not imported.
It unsubscribes, then separately requests positions and requires `positionEnd`.
Empty positions are valid only after that completion marker. There are no order
messages, comprehensive API samples, SDK dependency or automatic retries.

Cash/positions share one bounded deadline (default 15 seconds, configurable up to
60), at most 2,000 frames per phase, 120 cash rows and 200 position rows. Account
changes, malformed/duplicate rows, conflicting late cash updates and incomplete
downloads fail without overwriting the previous receipt. Unsupported protocol or
position metadata also fails. Security types within the metadata bounds are retained
as observations; anything other than STK is flagged, never authorized.

HMAC validation binds the source, version, account hash, completion markers, currency
rows, contract IDs, quantities and times. Expiry is 60 seconds after collection
**starts**, covering both downloads. Missing, altered, expired or future receipts
fail. A local signature is not an IBKR signature; signing-key OS isolation remains
an independent future gate. Sequential downloads are not an atomic broker snapshot.
The report always states `observation_atomic: false`.

See [IBKR account values](https://www.interactivebrokers.com/docs/tws-api/doc/account-portfolio-data/account-updates/account-value-keys)
and [cash summary definitions](https://www.interactivebrokers.com/docs/tws-api/doc/account-portfolio-data/account-summary/account-summary-tags).
Account-update subscriptions can conflict with another client's subscription; run
these manual trials without another account collector. Broker notifications are
still handled strictly; unknown notifications stop collection.

## What the comparison establishes

The consumer first replays internal simulation accounting. It compares any explicitly
observed USD SettledCash with the simulation's settled cash and reports only
`match`, `differs` or `USD_not_observed`. It does not assume a currency is present
with zero cash, substitute buying power or base-currency totals, or use FX estimates.
If any observed currency lacks a CashBalance/SettledCash pair, coverage is incomplete.
Negative observations and unsupported/short positions are flagged.

Positions match only by exact contract ID, currency and quantity. An unbound
simulation contract cannot match just because the symbol agrees. All broker account
positions are compared with all simulated positions; no strategy/subaccount ownership
mapping is assumed. Extra broker holdings or a larger paper cash balance can produce
expected differences. These reports do not mutate the ledger or select investments.

Even if the observed cash and positions match, `broker_reconciliation`,
`broker_funding_verified`, `broker_balances_imported` and `execution_authorized`
remain false. Open orders/reservations, fills/fees/transfers, dedicated capital
allocation, FX accounting and a stable/atomic observation protocol are still missing.
No full M3 or M4 acceptance is claimed. A report references the ledger revision at
comparison time; future authorization must independently check freshness and revision.

## Testing and deployment

```bash
python3 -m unittest discover -s tests
```

120 tests passed locally, including closed read-only messages/cancellation, exact
pinning, both completion markers, stale/wrong-pin/tampered receipts, currency gaps,
duplicates, racing cash, negative balances and contract-based comparisons without
funding imports. VM/CI and fresh paper acceptance are pending for this implementation.
Deploy in a new isolated release as in [deployment instructions](deployment.md);
preserve the existing credential directory, persistent cost DB, private owner policy
and receipt key. No new credentials or packages are required.

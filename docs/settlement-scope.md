# Current settled-cash scope verification

The `$LEDGER-` account-update prefix identifies per-currency ledger entries when
the Gateway setting is enabled. Unprefixed keys can represent account aggregates;
the currency label alone does not prove ledger scope. See the
[official prefix documentation](https://www.interactivebrokers.com/docs/tws-api/doc/tws-settings/per-currency-account-value-prefix).
No Gateway setting is changed by this release.

## Receipt version 3

New cash/position receipts preserve `per_currency_scope_verified`. It is true only
if every included cash row arrived with the exact ledger prefix. Bare rows remain
private observations but cannot establish currency-specific settled cash. A late
bare cash row invalidates an otherwise verified scope window. Mixed/duplicate cash
observations continue to fail safely rather than selecting a favourable value.
Versions 1 and 2 remain readable within their original expiry; they lack scope
provenance and cannot prove spendable USD cash. A consumer never upgrades them by
guessing from labels or amounts. Funding and allocation checks enforce this rule.

## Explicit aggregate settlement query

`settlement-check` requests only the documented `SettledCash` summary tag, after
exact paper pin validation. The account-summary request and its cancellation are
fixed read-only messages. Unknown tags, changed accounts, wrong request/end markers,
duplicates, missing fields and nonfinite values fail closed. Results are bounded,
signed and saved privately with a 60-second observation TTL; failures preserve the
previous file. Account IDs/balances are not printed or sent to agents.

The query's scope is `account_summary_aggregate`, not a per-currency cash ledger.
Even a USD-labelled summary cannot supply USD ledger cash. It is not loaded into
the allocation evaluator or used to clear a funding block. Official request and
ledger examples: [IBKR Account Summary](https://interactivebrokers.github.io/tws-api/account_summary.html).
Gateway `SettledCashByDate` stays unparsed; its serialization/time semantics remain
unestablished. No inferred FX conversion, historical transaction investigation,
deposit, cash reset or broker reservation is performed.

## Installation, tests and Google Cloud trial

Use the normal Python 3.12 installation and existing protected runtime from
`deployment.md`. No extra dependency or actual credential is required. Deploy a
tested Git archive into a new isolated VM release and retain the existing DB/key/
pin/policy paths. Keep Read-Only API enabled on localhost paper Gateway. The CLI
verifies the host ingress guard before collecting either cash or settlement data.

```bash
python3 -m unittest discover -s tests -q
export NEXYDAO_SETTLEMENT_SNAPSHOT=/private/runtime/settlement-summary.json
python3 -m nexydao settlement-check
python3 -m nexydao broker-orders
python3 -m nexydao broker-state
python3 -m nexydao allocation-check
```

Configure the existing order and cash snapshot paths as before. The last three
commands must finish while both consumed receipts are fresh. The aggregate summary
is separate diagnostic evidence, never an allocation input. No paid API calls occur.

## Acceptance and remaining gates

All 170 tests pass locally. Scope tests cover bare USD aggregates, legacy receipts,
late scope changes and false flag types. Settlement-query tests cover fixed messages,
identity, request/tag/end validation, duplicates and safe redaction/preservation.
Ubuntu/CI and fresh broker acceptance are pending. Monetary reservation accounting
requires verified currency cash and complete order/fee coverage before it can reserve
funds safely. Those gates, settlement serialization, stable observations and executor
authorization remain open. M3/M4 are incomplete; execution remains disabled.

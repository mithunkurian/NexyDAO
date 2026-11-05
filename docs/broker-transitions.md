# Paired broker observation diagnostics

PR #35 adds a read-only D3 transition report over four existing public-key
receipts: opening/closing cash-position views and opening/closing execution views.
It compares observed changes with newly visible fills and linked commissions.
It does not query the broker, investigate prior owner transactions, import balances
or certify lifecycle reconciliation, funding, monetary reservations or execution.

## Operator input and freshness

```bash
python3 -m nexydao broker-transition-report \
  --before-state /private/opening-state.json \
  --before-executions /private/opening-executions.json
```

Closing paths must be explicitly configured in
`NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT` and `NEXYDAO_EXECUTIONS_SNAPSHOT`.
Use the existing independent `STATE_RECEIPT` and `EXECUTION_RECEIPT` public key
files/pins, prefixed with `NEXYDAO_`. No signing or legacy HMAC key is read.
All four original receipts must still be fresh at a common evaluation time after
the last signature verification. Original 60-second lifetimes remain unchanged;
there is no historical-expiry bypass, checkpoint refresh or automatic collection.
Thus this command supports a deliberately short observation interval only.

State schema 3 and execution schema 1 are mandatory. Each closing query must start
after its corresponding opening query completed and must advance in time. The
two opening queries must both finish before either closing query starts. Reversed,
identical or overlapping pairs fail. These rules do not make separate downloads
atomic or prove that a newly visible fill occurred between the state observations.

## Comparison rules

- Exact account identity, dedicated receipt domains, signature/pin, original schema,
  bounded regular files, completion flags and current freshness are verified.
- Full rows with the same execution hash must stay unchanged. A previously visible
  ID disappearing from the later rolling query suppresses fill arithmetic.
- Only IDs absent from the opening execution query contribute. Retained fills are
  not counted again. Each fill uses its incremental quantity and price, not its
  cumulative quantity or average price. Buy/sell signs and commission/rebate signs
  are retained. Cross-currency fees stay in their own currency; no FX netting occurs.
- Contract metadata must agree across both state and execution views. Corrections,
  pending price revisions and unsupported position instruments suppress fill
  arithmetic. Residual fields are null rather than a misleading zero when unavailable.
- Complete position downloads allow absent contract quantities to be compared as
  zero. Cash requires verified per-currency scope and an explicit `CashBalance`
  row in both states. A missing currency is never assumed zero, even if a row in
  the other state is zero. Fee currencies must also be observed in both views.
- Position deltas are compared with signed new fill quantities. CashBalance deltas
  are compared with signed fill notionals and linked fees. This is a numerical
  comparison only; it does not establish the broker's cash recognition/settlement
  timing. SettledCash is not reconstructed from fills. Calculations use a bounded
  100-digit local Decimal context to preserve tiny residuals independently of the
  process context; source amount/count bounds remain enforced by the loaders.

Output contains counts, scope flags, missing checks, evaluation/expiry times and
canonical payload hashes. It excludes account IDs, symbols, broker times, balance
amounts and fill details. Inputs and application DB are unchanged; no DB/provider/
socket is opened. Existing negative-cash, short-position, settlement-schedule and
incomplete settled-cash warnings remain visible even if numerical deltas match.

`visible_deltas_match` describes only these observed differences. An older fill
may become newly visible, equal/opposite unexplained events may cancel, and manual
activity, transfers, settlement, corporate actions and the query's historical
coverage remain unverified. Broker wall-clock text is not converted into an
invented execution epoch. Consequently `execution_interval_attribution_verified`,
`settled_cash_reconciled`, `account_observation_atomic`, `broker_reconciliation`,
`broker_funding_verified`, `reservation_amounts_verified`, `ledger_imported`,
`funding_authorized` and `execution_authorized` always remain false.

## Acceptance and remaining work

Twenty new tests cover buy/sell/rebate signs, incremental partial fills, retained
IDs, currency scope/missing rows, exact arithmetic, unexplained changes, mutated or
disappeared fills, corrections, pending prices, metadata/instruments, ordering,
freshness/account/schema, secret-free real CLI consumption, forgery/domain/pin
denials, unchanged input receipts, no application DB/provider/socket access and
expiry during verification. OpenSSL verification uses private temporary files as
in the existing public receipt loaders.
The existing account-audit tests now use a fixed fixture timestamp and clock,
removing a Windows cross-clock timing failure without relaxing production TTL or
future-time rejection. Windows: 409 tests, 402 passed/seven Unix-only skips.
Implementation `e2b6913` passed all 409 Ubuntu tests in isolated release
`releases/broker-transitions-e2b6913`, including the 20 new transition/public CLI
tests. Exact tested source archive SHA-256:
`b03f9dc3f2f3a00cef701463257f9ae5d673180acd610563ef8334bfa809a6b0`.

All fixtures are synthetic and generate temporary keys. No real account/history
queries, paid calls, host provisioning, production deployment or budget changes.
Full D2 coverage and D3 stable lifecycle reconciliation, protected broker-role
deployment, actual monetary reservations and funding acceptance remain open.

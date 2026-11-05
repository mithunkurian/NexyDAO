# Read-only execution and commission observations

PR #29 advances D2 with typed stock execution/fee observations and a dedicated
Ed25519 receipt domain. It does not close D2, reconcile the account, import fills,
reserve broker money or authorize orders. The owner's exclusion of further review
of prior transactions is preserved: development acceptance uses synthetic broker
sessions and generated fixture keys, not the account's transaction history.

## Wire scope and bounded completion

The reader requires the exact configured paper account, nonzero connection client
ID, localhost paper port 4002 and protocol 178. The CLI verifies the host ingress
guard before collection. Only handshake/start/accounts and one account-filtered
`reqExecutions` version-3 request are sent. Filter client ID 0 requests the API's
visible clients; it is not a client-0 connection or an order-binding request.
No place/modify/cancel/automatic-binding command is available.

The exact execution (32 fields), commission (8 fields) and request/end layouts
were checked against official
[API 10.51.01 client/decoder sources](https://interactivebrokers.github.io/downloads/twsapi_macunix.1051.01.zip),
archive SHA-256 `50a459ed09f0030df25125a177e57b69bdf576ec3a89fcb1f81fdff95bbf6316`.
The SDK source is a development reference, not a new runtime dependency or vendored
implementation. Unsupported layouts/instruments/models and unknown frames stop
collection rather than guess at fields.

The account is rechecked on observations. At most 50 stock fills and 50 fees are
accepted, with 2,000-frame phase limits and the configured total deadline (default
15 seconds, maximum 60). Exact request/end IDs are required. A commission can
precede its fill or follow `execDetailsEnd`; collection waits until every observed
execution has exactly one matching fee. Missing, duplicate or unmatched reports,
disconnects and timeouts fail without replacing the prior receipt. No default zero
fee or automatic retry is supplied.

IBKR describes Gateway executions as limited to its current trading day and
documents corrections as new execution IDs with changed final suffixes; see
[execution details](https://www.interactivebrokers.com/docs/tws-api/doc/order-management/execution-details).
The receipt deliberately claims only `api_visible_gateway_recent_query`, with
manual-order, transfer and account-reconciliation coverage all false. An empty
query does not establish absence of manual activity or complete history.

## Typed data and independent public verification

Each row includes contract ID, symbol, STK type, contract/execution exchanges,
currency, client/order/permanent IDs, BOT/SLD side, quantity, price, cumulative
quantity, average price, broker time, liquidation/liquidity values, pending-price
flag and linked commission/currency. Original execution IDs and their correction
groups are SHA-256 fingerprints, with the numeric correction sequence retained.
Raw frame digests support provenance; account names and order-reference/vendor
text are not published. Broker time is observed text, not a verified UTC clock.

Partial fills remain distinct. Correction versions are retained and flagged,
never netted or added together as final booked fills. Pending price revisions,
currency-mismatched fees and negative commission rebates remain observations.
Unused PNL/yield sentinel fields are not turned into accounting values. The local
validator rechecks bounded schemas, exact integer/boolean types, monetary strings,
positive fill quantities/prices, cumulative quantities, unique IDs and derived
flags. More instruments/currencies/accounting need separate acceptance.

Receipts use the dedicated `NexyDAO:broker-executions:ed25519:v1` domain and the
pinned public DER key. SEC/shadow signatures and HMAC downgrade/fallback are
rejected. The collector checks its signer before any broker connection. Public
consumers never open its private key, even if an obsolete signing-path setting is
present. Files are read without following a final symlink and with a 65,536-byte
limit; Unix writable-by-others/nonregular receipts are rejected. Receipt expiry is
60 seconds from collection start and checked again after signing before save.
Failed collection/signing leaves the prior file and its original TTL unchanged.

## Explicit operator commands

The optional collector requires a separately provisioned dedicated signing key,
public DER and independently pinned fingerprint. No production keys or services
are installed by this PR. Protect code, public pin/configuration and collector
identity independently; this local signature is not an IBKR-signed attestation.
Existing HMAC order/state readers remain unchanged and are not migrated here.

```bash
# Set the exact account and new execution public key/pin in protected configuration.
# Collector only: set NEXYDAO_EXECUTION_RECEIPT_SIGNING_KEY_FILE as well.
python3 -m nexydao broker-executions
# Public-only, local verification; no socket, provider or application DB:
python3 -m nexydao broker-executions-report
```

`NEXYDAO_EXECUTIONS_SNAPSHOT` selects the receipt; `NEXYDAO_OPENSSL_PATH` optionally
selects the protected absolute executable. The report prints counts and coverage/
risk flags, not row values/account identity. It always reports `ledger_imported:
false` and `execution_authorized: false`. These commands are not agent tools.
No real account query was run for this development acceptance.

## Acceptance and remaining D2 work

Sixteen tests cover exact read-only bytes, identity before query, reordered/late
fees, partial fills/corrections, empty limited scope, bounds, errors, duplicate/
missing events, typed schemas, freshness, signature/domain rejection, public-only
verification after deleting the private key, signer rejection before networking,
failed-save preservation and database/provider/socket-free report execution.
Local suite: 310 tests run, 304 passed and six Unix-only skips on Windows.
Ubuntu validation and exact tested commit/archive follow after acceptance.

D2 remains open for real read-only compatibility/coverage acceptance under an
appropriate data-access scope, typed open/completed orders and manual visibility,
transfers and remaining public-key receipt integration. D3 still owns lifecycle
reconciliation and actual monetary reservations; D1 funding is blocked. S3 cannot
certify those inputs simply because this new receipt verifies. No paid calls,
broker writes, history review, simulation mutation or execution-enabling change
is included.

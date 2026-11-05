# Typed stock order-prefix and status diagnostics

PR #30 extends D2's current open-order observation with typed stable fields and
public-key receipts, then connects them to allocation and cash/position diagnostics.
It does not decode the entire variable open-order message, establish reserved cash,
verify manual coverage, reconcile the broker account or permit orders.

## Protocol and observed fields

The existing single bounded `reqAllOpenOrders` query remains unchanged: exact paper
account pin, protocol 178, localhost paper port 4002, nonzero connection client ID,
fixed handshake/start/accounts/query bytes and exact `openOrderEnd`. There are no
new broker commands, binding, client-0 takeover or order writes. Legacy opaque
schema-1 collection/HMAC reads remain available through their existing commands.

The prefix offsets and 12-field order-status layout were checked against official
[API 10.51.01 client/decoder/OrderDecoder source](https://interactivebrokers.github.io/downloads/twsapi_macunix.1051.01.zip)
(archive SHA-256 `50a459ed09f0030df25125a177e57b69bdf576ec3a89fcb1f81fdff95bbf6316`).
No SDK source is shipped or installed as a dependency. IBKR describes this query
as a one-time observation and distinguishes manual-order binding and status
callbacks in its [open-order guide](https://www.interactivebrokers.com/docs/tws-api/doc/order-management/open-orders)
and [status guide](https://www.interactivebrokers.com/docs/tws-api/doc/order-management/order-status).

Only STK prefix observations are supported. The fixed first 26 fields establish
account, contract ID, symbol/type/currency/exchange, client/order/permanent IDs,
BUY/SELL, total quantity, order type, limit/auxiliary prices and time-in-force.
Missing/unset price sentinels become `null`, never a zero-price or cash assumption.
OCA presence is noted without interpreting exclusivity. References are hashes;
account text, held reasons, advanced vendor text and reference prose are omitted.

Advanced order fields after permanent ID are represented only by count and digest,
with `complete_order_layout_verified: false`. Their syntax, advanced conditions,
parent/transmit semantics, commissions, hidden amounts and completeness are not
validated. Synthetic fixtures deliberately exercise this partial scope; a valid
prefix is not proof of a structurally valid complete advanced-order message.
There is no inference of reserved cash from quantity times price.

Order-status callbacks retain status text, filled/remaining quantities, fill prices,
client/order/permanent/parent IDs and market-cap price. Status callbacks have no
account field. The reader links them only to account-pinned order cores using
client ID, order ID and a matching positive permanent ID. Status-only, zero-ID,
conflicting or missing callbacks cannot establish account identity. Different
clients can reuse an order ID. Reordering and duplicates are preserved as events,
not counted as unique orders. The report's distinct observed identity count is
not a claim of complete order count or resolved manual-order identity.

Derived flags identify unmatched statuses, identity aliases/conflicts, quantity
disagreement and multiple frame versions during the query. An identity link can
be complete while quantities disagree; neither flag establishes a stable snapshot.
Every typed callback binds a unique position in the original activity-digest list;
missing/duplicated indexes and altered derived flags are rejected. Up to 100
prefix and 100 status rows fit the original 200-activity limit; oversized messages,
receipts, unknown layouts and missing completion fail safely. No fallback to opaque
parsing occurs after opting into typed collection.

## Public-only receipts and operator use

The schema-2 envelope uses the dedicated
`NexyDAO:broker-open-orders:ed25519:v1` domain with a pinned public DER key. SEC,
execution, shadow and legacy/HMAC domains are not accepted. Signing capability is
checked before the broker query; signature, schema, scope and the 60-second TTL
from collection start are independently checked on read. Failed collection/signing
preserves the previous receipt and original expiry. No production key is provisioned.

```bash
# Configure the exact paper account and separate order public key/pin.
# Collector only: NEXYDAO_ORDER_RECEIPT_SIGNING_KEY_FILE is also required.
python3 -m nexydao broker-orders-typed
# Local public-only verification/report: no provider, DB, HMAC key or socket.
python3 -m nexydao broker-orders-report
```

`NEXYDAO_TYPED_ORDERS_SNAPSHOT` selects the typed file (the new commands default
to `data/broker-orders-typed.json`). Explicitly setting it also selects typed
evidence in `allocation-check` and `broker-reconcile`. Allocation then prefers it
over configured legacy order evidence; invalid/missing/stale typed input stops
without falling back. Reconciliation omits order evidence if this setting is absent.
Existing cash/state HMAC requirements remain unchanged, so this does not complete
all broker key isolation. Protect the public pin/configuration and code separately.

Allocation reviews persist typed-link diagnostics with the receipt digest/expiry,
and add specific blockers for incomplete identity links, ambiguity, quantity
disagreement or order changes. Any original activity still forces a zero planning
ceiling. Reconciliation reports the same provenance/link flags without importing
money or positions; open orders/reservations remain an explicit missing check.
Even an empty typed query leaves manual coverage, reservation verification,
account atomicity, funding and execution authority false.

## Acceptance and remaining work

Twenty new synthetic-session tests cover exact nonbinding request bytes, prefix/
status parsing, cross-client identity, duplicate/reordered/unknown callbacks,
quantity/version changes, schema/digest/index binding, expiry, public-only and
cross-domain verification, signer-before-query rejection, failed-save preservation,
host guard, database/provider/socket-free reports, typed-input preference without
fallback and conservative persisted allocation/reconciliation diagnostics.
Windows: 330 tests run, 324 passed and six Unix-only skips. Ubuntu and exact tested
commit/archive evidence follow after acceptance.

No account history, real broker query, paid call, runtime key, deployed service or
production budget is used in this development slice. D2 still needs complete order
semantics/visibility, transfers, remaining public-key migration and appropriate
real compatibility/coverage acceptance. D3 owns actual reservation/lifecycle
reconciliation. The authorizer cannot treat these diagnostics as accepted money
or account-wide evidence. D1 funding and S3/P5 execution gates remain open.

# Read-only API-visible orders

`broker-orders` sends one bounded `reqAllOpenOrders` request after exact-pin paper
identity validation, with a nonzero client ID. No submission, modification,
cancellation or client-0/automatic binding command is available. Unsupported
protocol, changed identity, unknown notifications, wrong/missing end markers and
oversized activity fail safely; failed collection preserves the old receipt TTL.

IBKR documents that this request does not bind orders:
[current official guide](https://www.interactivebrokers.com/docs/tws-api/doc/orders/modifying-orders).
API orders across clients are returned with an `openOrderEnd` terminator:
[official legacy retrieval guide](https://interactivebrokers.github.io/tws-api/open_orders.html).
An empty query does not prove all manual orders, other sessions, fills or reservations.

## Installation, tests and Google Cloud use

Use Python 3.12 and the existing protected runtime; no additional dependency or
credential is required. Keep Read-Only API enabled on paper Gateway. The CLI audits
the host guard before connecting. Follow `deployment.md` for isolated Git releases
and preserve the original VM checkout, credentials and persistent database.

```bash
python3 -m unittest discover -s tests -q
export NEXYDAO_ORDERS_SNAPSHOT=/private/runtime/broker-orders.json
python3 -m nexydao broker-orders
python3 -m nexydao broker-state
python3 -m nexydao allocation-check
```

Supply the existing evidence key, pin, owner policy, DB and cash snapshot settings.
Run the last three commands consecutively: both receipts expire 60 seconds after
their collection starts. A configured missing/invalid/stale order file stops the
review; an omitted setting reports missing evidence and forces zero planning
capacity. No timer, automatic retry loop, budget reset or capital import is added.

## Evidence limits

The private signed receipt contains scope, completion, account fingerprint, times
and up to 200 order/status frame digests. Variable layouts stay opaque; accounts,
quantities, prices and monetary reservations are not decoded. Duplicate callbacks
are possible, so frame count is not order count. Any activity blocks planning,
including status-only callbacks. Vendor text is never printed or sent to agents.

Allocation reviews bind both receipt digests/expiries and recheck them before
commit. Even empty API activity retains the broader open-orders/reservations
funding block. Manual coverage, reservation amounts, atomic state and authorization
remain false. Current negative cash and all owner rules still apply.

## Settlement investigation

The official `SettledCash` definition includes settlement, purchases, commissions,
taxes and fees: [EWrapper reference](https://interactivebrokers.github.io/tws-api/interfaceIBApi_1_1EWrapper.html).
It does not establish Gateway `SettledCashByDate` serialization, effective date or
timezone. This investigation did not establish those semantics. The schedule stays
unparsed; BASE conversion, other-currency credit or a numeric/date guess cannot
replace explicit USD settled cash. No past owner transaction investigation is added.

## Acceptance

All 160 tests pass locally, including request allowlists, identity-before-query,
scope/completion, frame bounds, signatures/duplicate JSON, expiry, stale-order
rollback and missing/nonempty order denial. An initial unrelated account-audit
fixture hit a clock boundary; the unchanged suite passed on rerun. VM/CI and fresh
paper acceptance are pending. Full order/reservation coverage, settlement semantics
and executor authorization remain open; M3/M4 are incomplete.

# Public cash/position receipts and cross-observation diagnostics

PR #31 adds a dedicated public-key cash/position receipt and a local three-receipt
diagnostic report. This advances D2/D3 without closing funding, lifecycle,
reservation, account-coverage or authorizer acceptance. There are no new wire
commands, broker writes, paid calls or automatic collection/scheduling.

## Public cash/position state

`state_receipts` reuses the existing exact-paper-account, protocol-178, bounded
cash/position collector and schema-3 validator. Its dedicated Ed25519 domain is
`NexyDAO:broker-cash-positions:ed25519:v1`. A public DER file and independently
configured SHA-256 pin are mandatory; SEC, order, execution, shadow and HMAC
signatures are not accepted in this path. Schema 1/2 are not promoted into the
new public envelope. Legacy HMAC commands and files remain available separately.

The collector checks its signer before networking, validates state before signing,
then rechecks the original 60-second TTL before publication. Failed collection or
signing preserves the previous receipt and expiry. The new receipt is bounded to
65,536 bytes (the signature helper also bounds the signed payload); a larger valid
legacy snapshot fails rather than being truncated or silently downgraded. Reads
use the existing bounded no-final-symlink/regular-file signature helper, including
Unix writable-by-others rejection. Consumers open only the pinned public key,
even if an obsolete private signing-path setting remains present.

State reports expose counts, currency-scope/pair completeness and negative-cash,
short-position, unsupported-instrument and unparsed-settlement flags. These are
observations, not legal eligibility, effective settled cash or usable capital.
No balance, position row, account name or raw settlement text is printed.

## Three independently verified inputs

`broker-observations-report` requires explicit state, typed-order and execution
snapshot paths and their three public key/pin configurations. It authenticates
each with its dedicated loader, then revalidates all schemas, exact account,
scope and freshness at one evaluation time after reading the last receipt.
Missing, swapped, stale or forged input stops without falling back to a legacy
receipt, dropping a source or returning a partial success. Its effective expiry
is the earliest of the three expiries. No provider, HMAC key, application database,
broker socket, signer, ledger mutation or import is needed.

Cross-checks compare contract ID/symbol/type/currency metadata, exact positive
permanent/client/order identities, buy/sell side and execution cumulative quantity
against observed order quantities. Fee currencies absent from observed cash are
flagged as missing evidence without inferring debt or converting currencies.
Conflicts may reflect changes between queries, aliases or incomplete observations;
they are review diagnostics, not proof of misconduct or overspending.

A fill absent from the current open-order query is counted as **unlinked**, not
automatically a conflict: completed orders need not remain open. Positions are
never equated with recent fills. Opening holdings, sells, corrected executions,
fees, transfers and broader observation coverage remain unknown. No fills are
summed or netted and no opening cash is reconstructed. Matching metadata, even
with overlapping observation windows, never establishes an atomic account view.

The report retains receipt-payload digests, earliest expiry, source reports and
explicit missing checks. Negative/missing currency cash, unparsed settlement,
unmatched order statuses, order changes, execution corrections and pending prices
remain visible blockers. Funding, reconciliation, atomicity, reservation/import
and execution-authority flags always remain false. The pure cross-check function
does not itself authenticate bytes: trusted callers must use the public loaders;
the CLI does so. Reports are not signed permits or IBKR-signed attestations.

## Explicit operator selection

Separately provision dedicated collector-only signer keys and protect code/public
pins/configuration. This PR installs no production key, account, service or timer.

```bash
# Collector only: state public key/pin and signing path must be configured.
python3 -m nexydao broker-state-public
# Public-only local state report:
python3 -m nexydao broker-state-report
# Require three explicit public snapshot paths/pins, collected within their TTLs:
python3 -m nexydao broker-observations-report
```

State settings: `NEXYDAO_STATE_RECEIPT_PUBLIC_KEY_FILE`,
`NEXYDAO_STATE_RECEIPT_PUBLIC_KEY_SHA256`, collector-only
`NEXYDAO_STATE_RECEIPT_SIGNING_KEY_FILE`, and optionally protected absolute
`NEXYDAO_OPENSSL_PATH`. The new state commands default to
`data/broker-state-public.json`.

Explicitly setting `NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT` also selects public state
for existing `funding-check`, `allocation-check` and `broker-reconcile`. Invalid
public state stops before opening their application audit DB; no HMAC fallback
occurs. These existing review commands may write audit records, as before.
Use `NEXYDAO_TYPED_ORDERS_SNAPSHOT` for public order diagnostics. A deliberately
configured legacy order or Web ledger still requires its private evidence key;
that legacy dependency is not bypassed by selecting public state. Legacy
`broker-state`, `broker-orders` and settlement collection still require their key.

The three-source report requires explicit `NEXYDAO_PUBLIC_BROKER_STATE_SNAPSHOT`,
`NEXYDAO_TYPED_ORDERS_SNAPSHOT` and `NEXYDAO_EXECUTIONS_SNAPSHOT`. It never runs the
collectors itself. Other broker receipt types and protected broker-role deployment
remain incomplete, so this is not full P5 key-isolation acceptance.

## Acceptance and remaining gates

Nineteen new tests cover public-only/obsolete-private-path verification, dedicated
domain/schema separation, forged/duplicate/swapped/missing/stale receipts, signer
preflight and failed-save preservation, post-read freshness rechecking, matching/
unlinked/conflicting observations, incomplete/negative cash and pending prices,
non-atomic windows, actual three-receipt reporting without secrets/DB/socket,
and public-state funding/allocation/reconciliation without weakening denials.
Windows: 349 tests run, 343 passed and six Unix-only skips. Ubuntu and exact tested
commit/archive evidence follow after acceptance.

All development inputs are synthetic sessions, fabricated accounts/holdings and
temporary signing keys. No owner account/history query or production runtime key,
budget, deployed service or simulation data is used. D2 still lacks full advanced
order/manual/transfer coverage and appropriate real compatibility acceptance.
D3 still needs lifecycle reconstruction, monetary reservations and remaining key
boundaries. D1 funding and S3 authorizer acceptance remain open. Matching this
diagnostic report cannot replace those independent gates.

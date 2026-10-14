# Item 1 — Current currency cash and reservation foundations

Status: **In progress**. This release provides a supported Web API reader and atomic
USD simulation planning holds. It does not certify broker funding, reserve broker
capital, implement full order lifecycle accounting or complete Item 1.

## Supported settlement source

IBKR documents per-currency `settledcash`, `cashbalance`, account identity and native
timestamps in its [Portfolio Ledger endpoint](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/portfolio/portfolio-ledger).
The reader uses only GET requests to three fixed paths on HTTPS `127.0.0.1:5000`:
SSO validation, portfolio accounts and the exact pinned paper account's ledger.
It checks paper login type, authenticated session time and a single exact account
before and after collection. No browser cookies, credentials, arbitrary URLs,
redirects, proxies, order routes or login automation are accepted.

TLS certificate and hostname verification are mandatory, using an explicit trusted
local CA file. Configure a certificate valid for IP 127.0.0.1; do not use an insecure
TLS option. The CLI also requires the root host guard to protect port 5000 against
non-loopback IPv4/IPv6 access. The upgraded guard remains compatible with existing
TWS collectors; the old guard cannot certify Web API protection.

The signed receipt stores only currency cash, native timestamps, session-scope
confirmation and an account fingerprint. It excludes BASE aggregates, credentials
and profile details. Duplicate JSON, missing cash, mixed accounts, stale/future or
millisecond timestamps and nonfinite/oversized numbers fail. Expiry is bounded by
collection start, the oldest native currency timestamp and remaining session time.
Failed collection preserves the previous receipt without refreshing it.

Allocation reviews can consume the optional signed ledger receipt. It must match
the TWS currency set and each reported cash balance; any mismatch forces zero
planning capacity. Negative cash from either source cannot be offset across
currencies. The new explicit source can establish missing currency settlement
without interpreting `SettledCashByDate`, but cannot clear order, fee, allocation
ownership or executor authorization gates. Both source expiries are rechecked
before a review commits. No cash is imported or converted.

## Simulation planning reservations

`sim-reserve` and `sim-release` are operator simulation fixtures, not investment
strategies or agent tools. A request binds a unique ID, proposal fingerprint,
symbol, notional and fee. Only explicitly USD-funded fees are supported in this
slice; foreign fees are rejected rather than converted or ignored.

SQLite transactions serialize reservations across connections. Notional and fees
reduce available simulation capacity; owner cash/position/exposure/drawdown limits,
retained API costs, the allocation cap and a fee buffer remain enforced. Active
holds count in Portfolio Manager/fill preflight. Holds do not spend cash or reduce
marked equity, and do not reserve broker funds. State changes increment the ledger
revision so outstanding decision snapshots cannot silently reuse old capacity.

Same-ID retries are idempotent; changed requests conflict. Holds survive restarts
and never release merely because evidence expires or a process crashes. Release
is an explicit simulation-only action. A released ID cannot become a new hold.
An event replay verifies hold state/payload integrity and rejects corruption.
This is local consistency, not administrator-resistant audit or OS isolation.
No simulated fill automatically consumes a hold; later execution/fill linkage is
a separate acceptance gate. `reserve_broker` is unconditionally unavailable.

## Installation, testing and Google Cloud trial

Owner login, tunnel recovery and certificate approval procedures are maintained in
the [owner maintenance SOP](owner-maintenance-sop.md).

Python 3.12 and the standard library suffice. Use `deployment.md` and retain the
existing private DB, owner policy, exact paper pin and receipt key. Never commit
actual configuration, broker credentials or certificates/private keys.

```bash
python3 -m unittest discover -s tests -q
# Install the updated root-owned host guard before starting a Web API listener.
python3 -m nexydao web-access-check
export NEXYDAO_WEB_CA_FILE=/private/runtime/web-gateway/cert.pem
export NEXYDAO_WEB_LEDGER_SNAPSHOT=/private/runtime/web-ledger.json
python3 -m nexydao web-ledger-check
python3 -m nexydao broker-orders
python3 -m nexydao broker-state
python3 -m nexydao allocation-check
```

Finish the consumed receipt collections/review while all evidence is fresh. A
configured missing or invalid Web receipt stops the review. Leave its setting
unset until the authenticated gateway trial is validated. There is no timer or
automatic retry loop. Agent decision memory excludes these records.

Example **offline simulation fixture**, never a broker order:

```json
{"id":"planning-fixture","proposal_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","symbol":"SPY","notional_usd":"100","fee_usd":"2","fee_currency":"USD"}
```

```bash
python3 -m nexydao sim-reserve --reservation /private/planning-fixture.json
python3 -m nexydao portfolio-report
python3 -m nexydao sim-release --reservation-id planning-fixture
```

Run fixtures only in a separate test database for operational validation. Do not
replace or replenish the real persistent DB. Live/broker execution remains disabled.

The Client Portal Gateway is distinct from TWS Gateway. Its official download is
linked by [IBKR](https://www.interactivebrokers.com/campus/trading-lessons/what-is-ibkrs-client-portal-api/).
For the small VM, use a bounded manual trial, protect logs/configuration, limit JVM
heap/direct memory and monitor memory/swap. Authentication is an owner action:
[IBKR FAQ](https://www.interactivebrokers.com/docs/web-api/authentication/cpgw/client-portal-gateway-faq)
states that automated authentication is unsupported and daily login is required.
That is an operations constraint, not a completed autonomy feature.

## Acceptance and checklist status

All 196 tests pass locally, including concurrent holds, restart persistence, explicit
release, fee-currency rejection, policy rollback, fill isolation, audit corruption,
fixed verified-TLS GETs, identity/freshness checks and cross-source disagreement.
Implementation `d229ac3` also passed all 196 tests on Ubuntu and in CI (run 103).
The mock receipt clock was corrected; production expiry checks remain strict.
On 14 October, the VM host guard was updated and verified to protect port 5000
for IPv4/IPv6. Ubuntu headless Java 17 was installed. The official Client Portal
Gateway runs as a bounded 45-minute trial with a 160 MB maximum heap, restricted
worker pools and protected local TLS configuration/key files. Certificate and
hostname verification passed with the explicit private certificate file.
The vendor listener binds 0.0.0.0, so the verified root kernel drop rule remains
mandatory. The VM system trust store was not changed. The owner explicitly approved
adding the exact localhost public certificate to the Windows current-user trust
store. No private key was imported. Default Windows-root TLS validation and hostname
checks passed, matching the approved fingerprint. The expired Gateway trial and
SSH tunnel were restored with the existing certificate. Browser refresh and paper
authentication require owner action.
Laptop access is an SSH tunnel on 127.0.0.1:15000 to VM localhost:5000.
The owner subsequently reported browser login success. Fixed API GETs returned
HTML HTTP 403; one honest NexyDAO User-Agent accounts diagnostic returned HTTP 401.
These observations do not establish the sole cause of 403 or verified API access.
Real Web API ledger acceptance is pending.
No actual capital/fee reservation or live permission has been granted.

Item 1 stays **in progress** until real current currency settlement is verified,
allocation ownership/fees and current debits are resolved, and actual monetary
reservation/release acceptance is complete. Simulation holds and a code merge do
not satisfy those remaining gates. No prior owner transaction investigation is added.

## Post-merge reader compatibility work

PR #15 is merged. The next implementation retains both paper-session and account
checks, but spaces SSO validation by 61 seconds and account queries by at least
5.1 seconds, respecting [IBKR's documented pacing limits](https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/).
The collection timeout is now 90 seconds (configurable 70–120); each HTTPS request
is capped at 15 seconds. Update a local `NEXYDAO_WEB_TIMEOUT_SECONDS=15` setting to
90 before using the new collector. It waits before collecting cash; native cash
and receipt freshness remain 60 seconds. Short sessions and changed identity fail.
No indefinite retry, login automation or brokerage-session takeover is introduced.

`web-pacing.sqlite3` is created mode 0600 beside the configured CA file. All CLI
collectors for this Gateway must use the same protected CA directory. Keep this
database across restarts; attempted requests, including failures, consume pacing
slots. SQLite coordinates concurrent processes; an early attempt is denied rather
than retried. Clock rollback also blocks. This is local coordination, not a broker
reservation or administrator-resistant security boundary; external/browser API
requests are outside its coverage. Protect the directory and provision Windows
ACLs separately. The collector never deletes pacing history to bypass a limit.

Requests identify themselves as NexyDAO, without a browser impersonation header.
HTTP 401 reports `web_authentication_required`; 403 reports `web_access_denied`;
429 reports `web_rate_limited`. Bodies, cookies and account identifiers are not
included in errors. The documented `success.value` SSO envelope is accepted only
when unambiguous; flat legacy identity remains supported. Neither format may omit
paper mode, expiry or a successful validation.

Implementation `1d97512` passed all 203 offline tests locally, on the Ubuntu VM
and in CI (run 112). The isolated VM release is `releases/web-1d97512`; existing
credentials, owner policy, capital ledger and API-budget database were retained.
The verified host guard still blocks non-loopback Gateway ports for IPv4/IPv6.
A spaced identified SSO diagnostic also returned HTTP 401. The owner has been
asked to refresh and authenticate the paper session. Authenticated acceptance is
pending; no receipt, funding permission or execution permission is claimed.

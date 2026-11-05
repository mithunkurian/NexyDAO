# NexyDAO milestone register

Recorded: 2026-10-11 (Europe/Stockholm).

Current checkpoint: **M2A — Read-only paper connectivity validated**.
Git marker: `milestone-2a-paper-connectivity`.

This marker records tested development code and a successful bounded VM trial.
It is not a production release, permission to execute orders, or evidence of returns.
PR #1, [PR #2](https://github.com/mithunkurian/NexyDAO/pull/2) and
[PR #3](https://github.com/mithunkurian/NexyDAO/pull/3), PR #4 and PR #5 are merged.
The historical Git marker remains unchanged; subsequent validation is recorded below.

## Progress against the roadmap

| Checkpoint | Status | Evidence / remaining acceptance |
| --- | --- | --- |
| M1: Architecture and auditable AI deliberation | VM AI cycle validated | Six paid role calls completed, cost reservations settled and memory persisted after reopening SQLite. |
| M2A: Read-only IBKR paper connectivity | Validated; PR #2 merged | Four summary fields retrieved; exact pin matched; deliberate wrong pin rejected before summary; private snapshot saved; connection closed. |
| M2B: Verified market evidence and research | Quote and initial SEC research validated; broader coverage pending | Quote-fed six-call cycle and SEC-fed eight-call research cycle passed. Narrative/cross-publisher verification remains pending. |
| M3: Portfolio Manager and simulated accounting | USD slice validated; broader scope pending | Persistent ledger/risk/marks and advisory manager tested. Seven paid calls passed with quote-free abstention. Positive quoted plans/nine-call flow tested offline; FX/tax/broker accounting open. |
| M4: Independent authorization and paper execution | Not implemented; execution disabled | Executor isolation, signed permits, kill switch, exposure reservations, replay/idempotency and partial-fill tests. |
| M5: Autonomous paper operations | Not implemented | Scheduling, recovery, alerts, outcome learning, sustained paper evaluation and net performance reporting. |

M2A is an early checkpoint within roadmap phase 2, not completion of the whole phase.
No percentage of overall completion is assigned: these phases differ substantially
in size and operational risk. The company is not yet autonomously investing.

## M2A validation record

- Application validation baseline: `af9fe642bfa1351154d08d69c98c44f93ed773a4`.
- 28 offline tests passed locally and on Ubuntu 24.04 / Python 3.12 on the VM.
  GitHub Actions passed for the baseline, including the offline demo.
- The real paper check negotiated TWS protocol 178, recognized exactly one regional
  `DU` paper account and retrieved NetLiquidation, TotalCashValue, AvailableFunds
  and BuyingPower. Account identifiers and values stay outside Git and agent prompts.
- Snapshot file permissions were 0600; the subscription was cancelled and the probe
  disconnected. No orders or OpenAI calls were made by this check.
- The owner confirmed Read-Only API and localhost-only connections enabled, port 4002.
  The separate VNC service was observed listening only on loopback and accessed via SSH.
- At the successful check, about 282 MiB RAM remained available. This is one short
  observation, not acceptance of sustained unattended operation on 1 GB.

## Open gates before wider integration

1. Verify independent VM/cloud ingress restrictions: Gateway's API socket was observed
   bound to a wildcard address despite the localhost connection setting.
2. Complete M2B research and source verification; a quote alone does not verify an investment thesis.
3. Test Gateway reconnection, daily/weekly authentication requirements, recovery and
   sustained memory/swap behavior before unattended operation.

The $5,000 simulated capital and 15% annual net return objective remain unchanged.
No measured investment return is available yet. Owner duties remain capital provision,
access control and intervention; the CEO owns routine company management within
independently enforced safeguards.

## Follow-on VM validation, 2026-10-11

Merged main `b435b10` was unpacked into an isolated trial release without modifying
the owner's existing repository or credential files. One paid cycle completed with
the CEO choosing `investigate`, two risk reviews and three committee votes. The run
ID was `3d27b450-2083-4125-ac93-c5f1cd97f187`. Six cost entries settled, with zero
unsettled reservations and cumulative estimated token cost **$0.00079860** at the
configured model rates. The persistent SQLite database retained memory after reopening.
The lifetime budget was $0.10; execution remained false. This validates deliberation
and accounting, not investment performance or verified market research.

The exact account pin was saved outside Git with mode 0600. The timed Gateway session
ended before a live pin/mismatch check completed; connection refusal is not evidence
of account rejection. The new market adapter's offline tests are separate from live
market acceptance. See [market evidence trial](market-evidence.md).

Quote adapter validation baseline: `abde107bbbf1944904bb0b14d9f97471e0b574cc`.
All 45 offline tests passed on Windows Python 3.12 and the Ubuntu VM; GitHub Actions
also passed. The isolated VM trial release has a private 32-byte receipt key. Its live
check found Gateway not connected, so no fresh receipt or live pin acceptance was
claimed. PR #3 remains a draft pending those operational checks and open-market
quote consumption. No additional paid AI cycle was run for the quote trial.

After the owner reconnected paper Gateway, client ID 91 successfully matched the
private exact pin and retrieved all four account summary fields. A separate deliberate
wrong-pin check returned `account_mismatch` before the summary request. No account ID
or balance was sent to models or committed. The quote check negotiated protocol 178,
resolved exactly one SPY SMART/USD stock contract and reached the live BidAsk
subscription. No fresh tick arrived within the 15-second deadline; the socket closed
without issuing a receipt. This is contract/connection validation, not fresh quote
acceptance or evidence that tick-by-tick entitlements are sufficient.

Some earlier connections disconnected before account identity; later spaced checks
passed. Reconnection reliability remains an open operational gate. PR #3 remains a
draft pending a fresh live receipt and an AI cycle consuming it. Execution remained
disabled throughout; the checks made no additional OpenAI calls.

## Live quote and AI acceptance, 2026-10-12

Implementation `abde107` successfully collected a fresh live SPY BidAsk observation
from the pinned paper account and verified the signed receipt before AI initialization.
The 60-second event-time expiry remained enforced before every role call and before
completion. Run `0b5996e0-3d11-48da-8cd2-84eab52123f3` completed six OpenAI calls,
two risk reviews and three committee votes. The CEO chose `investigate` and cited one
quote evidence item. Execution remained false; no order capability was added.

Estimated cycle token cost was **$0.00196425**. The persistent database now records
**$0.00276285** cumulative estimated costs across 12 calls, with zero unsettled
reservations, under the unchanged $0.10 lifetime budget. The completed run persisted
in memory after reopening SQLite. No credentials or account identifiers were output.

This passes PR #3's fresh-quote and quote-fed deliberation gates; it does not complete
M2B research, establish investment performance or approve execution. Earlier connection
attempts still disconnected before collection; a subsequent controlled check succeeded.
Gateway authentication and the private VNC tunnel required manual recovery after the
timed trial ended. Unattended recovery and sustained operation remain unvalidated.

## Research implementation, 2026-10-12

PR #3 merged as `bf94f8a`. The next branch implements fixed SEC submissions and
company-concept retrieval, signed typed observations and two independent researcher
reports ahead of the six-role review. Application code checks structured numeric
claims; thesis prose, forecasts and economic truth remain unverified. All 65 offline
tests passed locally. Live SEC/paid research acceptance awaits an operator-provisioned
identifying User-Agent and is not claimed. No additional paid research run has occurred.
Full narrative/cross-source verification, OS isolation and execution remain future gates.

Research implementation baseline: `184ed131a3fa392573037bfd21ee330034d88534`.
All 65 tests also passed on the 1 GB Ubuntu VM in an isolated release; the offline
demo denied execution and GitHub Actions passed. [PR #4](https://github.com/mithunkurian/NexyDAO/pull/4)
is a draft pending live SEC retrieval and paid eight-call acceptance. The VM check made
no SEC or OpenAI requests and did not alter the persistent application cost database.

Live SEC retrieval then passed with the operator contact stored privately: one issuer
and two signed typed observations were verified. The first paid research attempt
stopped on invalid candidate structure before CEO review after two settled calls.
Cumulative estimated cost became $0.00396210 over 14 calls, with no unsettled entries.
This is safety rejection, not a completed eight-call acceptance. The report schema now
bounds candidates to the available issuers, restricts symbol/reference enums to the
verified dataset and requires nonempty claims. All 66 local tests passed; live retest
is required. No contact identifier was committed or included in model context.

## Live research acceptance, 2026-10-12

Corrected implementation `c21c9988257d8382775fca64be20748f2ae2f7d5` passed all 66
offline tests on Windows and Ubuntu, and CI. The still-fresh signed live SEC receipt
was reused rather than retrieved again. Run `01ad46d4-0ba0-4d8f-ba55-d392a518df60`
completed eight OpenAI calls: opportunity and countercase reports (one candidate each),
CEO, two Risk Officers and three committee voters. Structured numeric claims matched
source observations; both report theses remained explicitly unverified. The CEO chose
`investigate`, and execution remained false.

Estimated successful cycle cost was **$0.00530400**. Persistent cumulative costs were
**$0.00926610** across 22 calls, including the two-call rejected attempt, with zero
unsettled reservations under the unchanged $0.10 lifetime budget. Completed memory
survived reopening SQLite. No contact, credentials or raw receipts were committed.
This passes the initial SEC research workflow's live gates, not all M2B verification,
investment quality, unattended reliability, portfolio accounting or order authorization.

## Owner-policy milestone, 2026-10-12

PR #4 merged as `6a4b604`. Binding owner constraints now supersede every agent:
no shorts, no leverage/borrowing, applicable US/Swedish legal compliance, and verified
Swedish ISK eligibility before any future live execution. Versioned configuration
supports additional rules and tighter limits. Policy changes stop active reviews;
legal/account verification remains unresolved and execution always denied.
Baseline `d34f605` passed 75 tests on the VM/CI and an offline policy/audit check.
A direct snapshot-construction guard adds another local passing test (76 total).
No paid API, live account changes or orders were made for this milestone.
Final implementation `ad1fe0d8afacd5c2609408a706975f8eef9b8d63` also passed all 76
tests on the VM and in CI. PR #5 is ready for code review; legal/account/holder/asset
eligibility and future authorization remain open gates, not agent-certified facts.

## USD portfolio implementation, 2026-10-12

PR #5 merged as `a0ea0b6`. The new branch seeds the $5,000 USD simulation once and
adds explicit operator fixture fills, unsettled sale proceeds, idempotent settlement,
fee-inclusive average basis, realized P&L, signed fresh bid marks and replay-based
internal reconciliation. API estimates/reserves reduce available funding and net
equity estimates. Portfolio Manager proposals add one advisory call before CEO review,
with quote citations and independent aggregate cash/concentration/exposure/drawdown
constraints. They never mutate positions or authorize orders. All 92 local tests
passed; VM/CI and paid manager acceptance are pending. FX/tax and broker reconciliation
are deliberately not represented as implemented. See `portfolio.md` for scope.

Implementation `4398122a482a443f67589d2ca7b28e0dc6764677` passed all 92 tests locally,
on Ubuntu/Python 3.12 VM and in CI. Paid run `5666cb3b-1f13-4b79-aca4-d296ad2d008b`
completed seven calls: Portfolio Manager, CEO, two risk reviews and three votes. No
fresh quote was supplied; the manager correctly proposed zero allocations, and the
CEO chose `investigate`. No fixtures/orders were produced; the ledger revision stayed
unchanged and $5,000 settled cash with zero positions was retained after reopening.
Internal reconciliation and completed memory persistence passed. Cycle estimate was
$0.00669150; cumulative $0.01595760 over 29 calls, zero unsettled reservations, under
the existing $0.10 lifetime budget. Positive quote-backed allocation and nine-call
coverage are offline-only; actual broker/FX/tax accounting and execution remain open.

## Broker ingress and account audit, 2026-10-12

PR #6 merged as `268f364`. Release `7cf7809` passed all 104 tests locally, on the
Ubuntu VM and in CI. A narrow root-owned nftables service was installed, enabled
and verified active. Its exact kernel rule drops non-loopback TCP packets to broker
and VNC ports for IPv4 and IPv6, preserving SSH and localhost traffic. A fresh SSH
tunnel connected after installation and returned the VNC protocol banner.
The first service attempt failed on Windows archive line endings; explicit Git
attributes corrected the Linux script/unit exports and the follow-up passed.

Signed summary validation is offline/VM tested: exact pin, 60-second expiry, HMAC,
bounded values, stale/altered/duplicate rejection and private reports. A fresh paper
account collection is pending owner Gateway authentication. Balances are never
imported into the $5,000 simulation; complete reconciliation remains false pending
settled cash, positions/contracts, orders, fills/fees and external transfers.
Cloud policy, boot recovery, sustained operation and OS separation are still open.
No additional OpenAI calls or orders were made. See `broker-access.md`.

Following owner authentication, the fresh paper-summary trial on release `7cf7809`
passed with client 95. Earlier probes stopped safely on notification 10141; no
warning allowlist, account checks or authorization controls were relaxed. Four
summary fields were collected, signed and consumed before expiry. A different
account pin and the exact 60-second expiry boundary both failed validation.
The receipt is private mode 0600, and simulation cash/unsettled cash/revision were
unchanged. USD summary coverage was incomplete; no negative summary values were
observed. This establishes the initial authenticated summary slice only, not USD
funding, complete reconciliation, reliable reconnection or execution readiness.
No OpenAI calls or orders were made in this trial.

## Per-currency cash and position comparison, 2026-10-12

PR #7 merged as `d59cd06`. Release `0ff1b3a` passed all 123 tests locally, on the
Ubuntu VM and in CI. The new operator-only collector uses account-specific updates,
exact paper pinning, separate cash/position completion markers, bounded data and
signed receipts expiring 60 seconds after collection starts. Comparison uses exact
contract/currency/quantity identities and internal simulation replay, without
importing any broker balances or positions. No OpenAI calls or orders were made.

Gateway discovery showed `$LEDGER-` currency cash tags and `SettledCashByDate`.
The exact ledger prefix is supported; the undocumented settlement schedule is marked
unparsed, never treated as current settled cash. A single global 2100 acknowledgement
is accepted only after the collector's completed cash subscription was cancelled,
including its documented optional empty advanced-error field. Active-subscription
errors, repeated acknowledgements and nonempty rejection details still stop collection.
AccountReady false, racing cash, duplicates and incomplete observations fail safely.

Initial live probes exposed unsupported field/acknowledgement layouts and failed
without issuing receipts. The corrected trial encountered an expired Gateway timer;
owner authentication and completed fresh paper receipt validation are pending.
Per-currency settled cash, orders/reservations, fills/fees/transfers, capital allocation,
FX and a stable snapshot protocol remain explicit open gates. Full broker
reconciliation, funding verification and execution remain false. See `reconciliation.md`.

After owner reauthentication, a spaced client 95 trial on `0ff1b3a` completed both
downloads: six cash rows across three currencies, zero broker positions. Receipt
signature/freshness/pin and the consumer comparison passed; wrong-account and exact
expiry checks failed. Private receipt mode was 0600, host protection verified, and
simulation state/revision and API cost accounting were unchanged. No OpenAI requests
or orders occurred. The initial post-login disconnect remains evidence that recovery
reliability is unfinished; no unattended recovery acceptance is claimed.

Broker and simulation both had zero positions; positive-position comparisons remain
offline tested only. Explicit per-currency SettledCash was absent, settlement schedule
unparsed, and a negative currency cash observation was flagged. Its cause must be
resolved before future funding approval; no borrowing/funding conclusion is inferred
from incomplete observations. No balances were converted/imported or altered. This
passes only the initial cash/position comparison slice, leaving full M3/M4 open.

## Settlement evidence and funding denials, 2026-10-13

PR #8 merged as `c501db3`. Release `d923b13` passed all 135 tests locally, on the
Ubuntu VM and in CI. Version 2 receipts preserve bounded raw settlement observations
privately without inferring spendable cash; version 1 remains valid within original
expiry. The independent operator funding review binds evidence/policy hashes,
expiry and ledger revision, stores only redacted diagnostic data, and denies funding
even when hypothetical balances match. It cannot issue an execution permit.

The fresh paper trial collected six cash rows, zero positions and four settlement
observations, then verified the receipt and recorded denial case
`5129c425-4901-48df-a042-171000c404d6`, which survived reopening SQLite. SEK remained
negative in cash observations; cash fields agreed by currency and the cause remained
unresolved. The owner confirmed no saved statement is available. Numeric-prefix
schedule shapes were observed, not certified as current settlement evidence.
Ledger/revision and API costs remained unchanged; receipt mode 0600 and host guard
verification passed; no OpenAI calls, funding imports, FX conversions or orders occurred.
The initial startup disconnect and successful spaced trial do not prove sustained
reconnection reliability. Statement evidence, settlement semantics, full broker
reconciliation and M3/M4 execution prerequisites remain open. See `funding-diagnostics.md`.

## Expanded SEC research advisory acceptance, 2026-10-29

Merged PR #17 (`c28a0ec`) passed all 202 tests in isolated Ubuntu release
`releases/research-c28a0ec`. A real bounded SEC check retrieved seven approved MSFT
concepts and verified the signed concept manifest, fact context and provenance.
Receipt mode was 0600; existing runtime configuration and signing key were retained.

After explicit owner approval, one nine-role advisory cycle completed under prompt
version 8: `27d62b74-5165-4f51-a98e-a94cc871679a`. Both research reports passed
numeric/context binding checks; Portfolio Manager abstained without a quote, CEO
chose `investigate`, and two risk officers plus three committee members reviewed.
Execution was denied. Simulation cash/revision remained unchanged; the completed
run persisted in memory after reopening the same SQLite database.

A private SQLite backup preceded the trial. Estimated cycle cost was $0.01362225;
cumulative estimated costs were $0.02957985 over 38 calls, no unsettled reservations,
under the unchanged $0.10 lifetime budget and recorded model rates. No IBKR calls,
orders, schedules, capital resets or prior-transaction investigation occurred.

This validates expanded SEC retrieval and the combined advisory abstention path.
Quote-backed allocations, narrative/cross-publisher verification, proposal revisions,
sustained operation, full P3 acceptance and all funding/execution gates remain open.
PR #16's authentication acceptance remains deferred. SSH access was separately
restored using an owner-created recovery key; only its public key was registered
through authenticated browser SSH, preserving existing keys and host pinning.

## P4 performance and stress reporting slice, 2026-10-29

Implementation `dbea8df` passed all 208 tests locally and in the isolated Ubuntu
release `releases/portfolio-risk-dbea8df`; the isolated local demo passed too.
The existing portfolio view now reconciles price P&L, recorded trading fees and
API estimates/reservations to the change in net equity. Hypothetical 10%/30%/50%
price shocks include holdings, fully deployed active planning holds and full
reserved fees. Stale marks produce unknown scenario totals. Reports do not mutate
cash, positions, holds or revision and cannot authorize execution.

The CLI report over a private SQLite backup of the persistent VM ledger reconciled
-$0.02957985 net P&L, entirely API expenses, to $4,999.97042015 net equity. The
original database was opened read-only for backup/verification. Original/copied
portfolio state and cost-entry counts remained unchanged. No paid call or broker
request occurred. FX/tax/corporate actions, liquidity/stress enforcement, broker
lifecycle accounting and full P4 acceptance remain open; PR #16 stays deferred.

## Atomic simulation hold/fill acceptance, 2026-10-29

Implementation `09be8e3` passed all 222 offline tests locally and in isolated Ubuntu
release `releases/held-fills-09be8e3`; the isolated local demo also passed. Tests
cover partial consumption, separate fee/notional budgets, conservative rounding,
legacy migration, release, replay evidence, concurrent consumption/retries and
rollback. Current owner-policy, funding and valuation checks remain in force.

A separate Ubuntu CLI fixture used a new simulation database to reserve $200
notional and $1 fee, then record a two-share buy. Cash became $4,799, the hold was
fully consumed and revision became 2. Same-fill retry and release of the consumed
hold left state/revision unchanged. Paid call count remained zero; execution stayed
disabled. No persistent runtime, credential, IBKR connection or broker write was
used. This validates simulation accounting, not broker fills, order authorization,
monetary reservations or complete P1/P2/P4 acceptance.

## Linked proposal revision offline acceptance, 2026-10-29

Implementation `4017611` passed all 234 tests locally and in isolated Ubuntu
release `releases/revisions-4017611`; the isolated local demo passed too. The
revision suite covers parent eligibility, bounded ancestry, hash/link checks,
fresh review stages, research/manager stage preservation, current policy/costs,
rejection of historical citations and retained costs after a failed revision.

A separate Ubuntu fixture used synthetic provider responses in a new database:
one completed root followed by a linked child with six fresh role calls. Its parent
hash/depth link and AI memory persisted after reopening SQLite; execution remained
denied. Paid call count stayed zero. No credentials, persistent runtime, broker
access or schedules were used. This is offline workflow acceptance, not paid model
acceptance, verified thesis prose, autonomous revisions or complete P3 acceptance.

## P5 controller egress foundation, 2026-11-05

Implementation `bd7ed90` passed all 243 tests locally and in isolated Ubuntu release
`releases/controller-guard-bd7ed90`, plus the isolated local demo. Both the existing
ingress audit and the new UID egress audit reject dormant tables. The guard script
passed Ubuntu shell syntax checking.

An explicitly authorized root test ran only in a separate network namespace. It
applied the installer's rule body for a fixture UID and denied all 14 protected
loopback TCP probes (ports 22, 4001, 4002, 5000, 5901, 7496, 7497 over IPv4/IPv6).
The operator/root UID and allowed control ports still connected; actual kernel
JSON passed the UID audit. No host account, service, firewall rule, persistent
runtime, credential, paid API or broker connection was used/changed.

This validates the guard mechanism in isolation. Real controller-account/service
installation, startup/boot/recovery acceptance, alternate egress boundaries,
signing-key separation, independent authorization and full P5 remain open.
Funding and execution stay disabled.

## Public-key SEC receipt offline acceptance, 2026-11-05

Implementation `0f27742` passed a 255-test suite locally (254 passed, one Unix-only
permission skip on Windows) and all 255 tests in isolated Ubuntu release
`releases/public-receipts-0f27742`. The isolated local demo also passed. Tests use
real Ed25519 fixture signatures to cover public-only consumption, payload/key/
algorithm tampering, no HMAC fallback, expiry/scope, duplicate JSON, pre-network
signer rejection, protected Unix paths and failed-publication preservation.

A separate Ubuntu fixture generated fresh test keys, signed a two-fact receipt,
deleted both private signing/HMAC secrets and verified with the pinned public key.
A synthetic nine-role advisory consumer cycle completed with zero paid calls and
execution denied. No production key, persistent runtime, SEC retrieval, broker
access or service/host-identity change occurred. Separate collector/consumer OS
identities, migration of other HMAC receipt types, live public-key acceptance and
complete P5 remain open.

## Collector/consumer publication acceptance, 2026-11-05

Implementation `df3860b` passed a 262-test local suite (257 passed, five Unix-only
Windows skips) and all 262 tests in isolated Ubuntu release
`releases/research-boundary-df3860b`. The isolated local demo passed too.

A root-controlled temporary `/run` fixture used distinct collector/consumer UIDs
with generated keys and synthetic facts. The collector signed/published a 0640
receipt under the required 2750 group-readable directory, and the consumer verified
two facts. Private-key reads and writes to receipt/directory/config/code were all
denied (five checks); consumer republication failed. No paid calls, persistent
runtime, production keys, host accounts/services or firewall changes occurred.
This validates S1's filesystem/publication mechanism, not actual service deployment,
boot/recovery, remaining receipt types or complete P5.

## SEC service installation and retained completion, 2026-11-05

Following explicit owner installation approval and PR #25 merge, the fresh SEC
roles/configuration/key, public evidence directory and controller UID guard were
installed. Initial starts/restarts succeeded, but the audit correctly failed when
inactive one-shot units returned zero process timestamps after unloading.
PR #26 implementation `ef4b840` retains active/exited completion state and checks it
alongside successful nonzero process timestamps. All 271 Ubuntu tests passed;
Windows passed 266 with five Unix-only skips. A narrow five-file repair verified
old source bytes, preserved keys/configuration and reran both starts/restarts.
All 12 operator audit checks passed. No paid API call, broker write, timer or
original runtime modification occurred. S2 closes on correction merge; S3 is next.
Other receipt types and boot/sustained recovery are explicitly unverified; full P5
and execution remain gated. Exact archive digests and limitations are recorded in
[the service audit](service-isolation-audit.md).

## Shadow paper permit protocol, 2026-11-05

PR #27 implementation `2b73201` passed 288 tests on Ubuntu; Windows passed 283
with five Unix-only skips. Seventeen protocol tests include public-only signature
verification, SEC/shadow domain separation, strict signed integer types, every
intent binding, owner-policy changes, expiry after verification, stopped/default/
rearmed epochs, replay across reopen, six concurrent redeemers with one winner,
capacity stop and unchanged execution locks. A valid shadow consumption explicitly
denies execution and broker submission. Test keys, fabricated account/contract and
synthetic digests were confined to isolated temporary fixtures; no paid calls or
production services/runtime data were changed.

S3 remains in progress: accepted broker/risk/review/reservation inputs and protected
independent signer/stop identities remain required. This protocol does not certify
those gates. See [scope, exact archive and limitations](paper-permits.md).

## External shadow owner authority and identity fixture, 2026-11-05

PR #28 implementation `4033bcd` passed all 294 Ubuntu tests; Windows passed 288
with six Unix-only skips. A temporary root-controlled `/run` tree separated the
signer's private test key (UID 65533), consumer ledger (UID 65534) and root-owned
policy/control/lock/code. Real permissions denied six consumer protected accesses,
five signer accesses and eight role control operations. Public-only consumption
succeeded; consumer minting, fresh-process replay, old epochs after re-arm and
consumption after owner stop failed. Root stop persisted across reopen. Corrupt,
world-writable and symlinked control were rejected. A held shared lock made stop
fail busy without claiming completion, then owner stop succeeded after release.

Only temporary test keys/state and fabricated intent/digests were used. No paid
calls, persistent accounts, services, firewall rules, existing runtime/budget or
broker operations were changed. This is shadow mechanism/identity-fixture evidence,
not deployed authorizer or hardened emergency-stop acceptance. S3 remains open
for accepted broker/risk/review/reservation inputs and protected deployment.
See [exact archive, acceptance and limitations](permit-authority-boundary.md).

## Typed execution/commission observation foundation, 2026-11-05

PR #29 implementation `f5ae699` passed all 310 Ubuntu tests; Windows passed 304
with six Unix-only skips. Sixteen new tests cover the protocol-178 account-filtered
read-only request, stock fill/fee parsing, exact identity/end/completion checks,
reordered and late commissions, partial fills/corrections, bounds, pending-price
and currency flags, dedicated Ed25519 signatures, public-only verification after
removing the signer, failed-save preservation and database/provider/socket-free
reporting. Wire layouts were checked against official API 10.51.01 source.

Tests use synthetic broker sessions, fabricated account/contract data and generated
temporary keys. No real query or owner transaction-history review occurred; no paid
calls, installed service, broker writes, production key/budget or simulation state
was changed. D2 remains open for live/coverage acceptance, order/manual/transfer
data and remaining public-key integration. S3, funding, reconciliation and execution
remain gated. See [exact tested archive and scope](execution-observations.md).

## Typed order-prefix/status diagnostic integration, 2026-11-05

PR #30 implementation `bf0ad13` passed all 330 Ubuntu tests; Windows passed 324
with six Unix-only skips. Twenty new synthetic-session tests cover stable stock
order prefixes, complete status-message decoding, exact positive-permanent/client/
order identity links, cross-client order-ID reuse, duplicates/reordering, unmatched
or conflicting status observations, quantity/version changes, activity-index/digest
binding, scope/freshness, dedicated Ed25519/public-only verification, cross-domain/
legacy rejection and failed-save preservation. Allocation persists receipt/link
provenance and blockers; cash/position reconciliation reports the same diagnostics.
Stale order evidence is rejected even with fresh state; activity stays zero-plan.

Advanced order fields are count/digest only and deliberately unverified. Synthetic
tails are not proof of complete open-order wire validity. Manual/reservation/full
account/atomic/funding/execution gates remain false. No real account query, owner
history review, paid call, deployed service or production runtime change occurred.
D2 still needs complete semantics/coverage, transfers and appropriate live/read-only
acceptance; D3 owns actual monetary reservations and lifecycle reconciliation.
See [exact archive, operator selection and limits](typed-order-visibility.md).

## Public cash/position and three-view diagnostics, 2026-11-05

PR #31 implementation `7b2b031` passed all 349 Ubuntu tests; Windows passed 343
with six Unix-only skips. Nineteen new tests verify dedicated-domain schema-3
cash/position receipts, public-only reads after signer deletion (including obsolete
private-path settings), signature/schema/domain/freshness rejection, signer
preflight and failed-save preservation. An actual three-signed-receipt report
verifies without signer/HMAC/provider/socket/application DB access, then rechecks
all input freshness after reading the last source. Identity, contract, side,
cumulative quantity, fee currency and non-atomic-window diagnostics were tested.
Unlinked fills are not automatically conflicts or position reconstructions.

Existing funding/allocation/reconciliation paths can explicitly select public
state without an HMAC key; no legacy fallback occurs on failure and denials remain.
All authority, import, actual reservation and account-reconciliation flags remain
false. Only synthetic sessions, generated temporary keys and private test audit
DBs were used. No owner account/history, production runtime key/budget, paid call,
broker write or deployed service changed. D2/D3, D1 funding and S3 remain open.
See [exact archive, selection rules and remaining gates](public-broker-observations.md).

## Incremental simulation risk and retained commitment limits, 2026-11-05

PR #32 final implementation `83e9f0a` passed all 362 Ubuntu tests; Windows passed
356 with six Unix-only skips. Thirteen new tests exercise binding 50% projected
stress/10% drawdown limits, upward boundary rounding, fee/API treatment, persistent
active caps/buffers, restart and concurrent writes, different-default non-relaxation,
partial hold-to-position conversion, legacy missing-context release/replan, corrupt/
orphan profiles and missing main tables with surviving audit evidence. New risk
is blocked without forcing sells or releasing encumbered funds. Actual monetary
reservations and broker execution remain disabled.

Only synthetic fills/quotes/holds, generated keys, API-cost estimates and isolated
test databases were used. No real account/history query, paid call, deployed
service or production runtime database changed. R4 remains open for market
liquidity/full aggregate acceptance; D3 still needs actual reservations/lifecycle
reconstruction. See [exact archive and model scope](commitment-risk.md).

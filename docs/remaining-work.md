# Remaining work and planned PR packages

Planning snapshot: 5 November 2026, Europe/Stockholm.

Estimate after PR #23: **about 15 further PRs (12–18 range)** across eight paper
workstreams. The [delivery baseline](delivery-plan.md) tracks finite packages and
scope changes. Live readiness is separate. Broker compatibility, source availability, security findings and
acceptance failures may need extra fixes or splits. Ongoing evaluation also takes
elapsed observation time; a PR merge cannot substitute for that evidence.
PR #14 documents completed acceptance and is separate from this future estimate.
PR #24 closed S1 after 262 Ubuntu tests and real two-UID acceptance. PR #25 merged,
and S2 passed real installation/startup/restart acceptance with merged PR #26's
bounded state-retention correction. **2/15 packages are closed**. PR #27 adds an
S3 shadow permit foundation; its separate authorizer/evidence integration remains
open. PR #28 adds external owner-control and a temporary separate-identity fixture.
PR #29 adds typed stock executions/linked fees with public-only receipt verification;
PR #30 adds order-prefix/status visibility and conservative diagnostic integration;
PR #31 adds public cash/position receipts and partial three-view cross-checks.
Full D2 data and D3 lifecycle/reservation acceptance remain open. **13 packages remain**;
PR #32 adds projected stress and retained simulation commitment envelopes; actual
reservations and market liquidity remain unverified.
PR #33 adds immutable quote-backed spread screening, leaving executable/full-book
liquidity unverified. PR #34 adds opt-in public-key market quotes without completing
broker-role deployment. PR #35 adds fresh paired state/execution delta diagnostics;
interval attribution and complete lifecycle acceptance remain open. Revised estimate:
PR #36 adds verified audit backups and inspection-only recovery inside O1 without
enabling recurring operation or closing its scheduling/alert/recovery gates.
PR #37 adds read-only health and local alerts; O1 commissioning remains open.
PR #38 adds finite maintenance-only scheduling ticks; activation/recovery remain open.
**13–14 further PRs after PR #38** (28–29 total after #23 versus the
original 12–18). Implementation/acceptance splits exceeded that estimate; project
scope has not grown. Remaining broker
receipt key migration is paired with D2/D3 integration, without dropping that gate
or increasing the baseline count. See [service audit scope](service-isolation-audit.md).

S1 connects Ed25519 receipt publication to distinct collector and consumer identities;
S2 adds actual protected SEC role services and startup audit. S3's independent
authorizer, signed permits/replay prevention and kill switch are next. Full P5
also requires the broker receipt/key boundaries tracked in D2/D3; see
[collector/consumer boundary](collector-consumer-boundary.md).

## Autonomous paper operation: eight workstreams

Checklist status: **P1 blocked/in progress; P3, P4 and P5 in progress**; P2 and P6–P8 planned (existing partial components
remain recorded in the development tracker). No package is struck off yet. After
each merge, link the PR and strike a package only when all its acceptance gates pass.

PR #15 merged P1 foundations: supported per-currency Web API reader, cross-source
cash matching, and atomic USD simulation planning holds. Real Web API acceptance,
current debit/fee funding, allocation ownership and broker monetary reservations
remain open. See [Item 1 implementation and acceptance](currency-reservations.md).

PR #16 remains draft while paper Web authentication and real ledger acceptance are
blocked. The owner reports a submitted IBKR support ticket with no reply as of
28 October. Defer that acceptance step and continue independent P3 research work,
then P4 simulation accounting/risk. This changes development order, not funding or
execution prerequisites. New work branches from merged `main`, without PR #16 changes.
The first P3 slice expands approved SEC concepts and binds claim reporting context;
PR #17 merged as `c28a0ec`. Its seven-fact real SEC retrieval, 202 Ubuntu tests and
nine-role paid advisory abstention path passed on 29 October. Simulation state was
unchanged and execution denied. Full P3 acceptance, quote-backed allocation,
broader sources and linked proposal revisions remain open; see [research evidence](research.md).

P4's first slice adds reconciled price/fee/API-cost attribution and portfolio-wide
hypothetical price shocks, including full deployment of active planning holds and
their fees. Implementation `dbea8df` passed all 208 tests locally and on Ubuntu;
a report over a private persistent-ledger backup reconciled without changing state.
These reports do not certify liquidity,
FX/tax accounting, broker reconciliation or complete P4 risk enforcement. See
[portfolio accounting and stress scope](portfolio.md).

The next P4 slice links operator simulation fills to planning holds atomically,
including partial consumption, separate notional/fee budgets and retry/replay
checks. Implementation `09be8e3` passed 222 tests locally/on Ubuntu and an isolated
CLI consumption/retry fixture. Real broker fill ingestion, order bounds/lifecycle, allocation ownership,
broker monetary reservations and full P1/P2/P4 acceptance remain open.

The next P3 slice adds bounded, explicitly requested linked advisory revisions.
Every applicable research/manager/review stage repeats against current inputs;
past decisions cannot supply current evidence or approval. Narrative verification,
broader sources, quote-backed allocation acceptance and autonomous revision
orchestration remain open. See [revision scope](proposal-revisions.md).
Implementation `4017611` passed 234 local/Ubuntu tests and an isolated six-review
synthetic revision fixture; live paid revision acceptance remains pending.

P5's first slice adds a dedicated controller UID egress guard, strict operator
audit and an offline sandboxed service template. Implementation `bd7ed90` passed
243 local/Ubuntu tests and a 14-probe isolated kernel fixture; real service
installation and full key/identity separation remain open. See
[controller isolation scope](controller-isolation.md).

The next P5 slice adds opt-in public-key verification for SEC receipts without
the consumer holding a signing secret. Collector signatures do not certify thesis
truth, other HMAC receipt types or OS isolation. See
[public-key receipt scope](public-key-research-receipts.md).
Implementation `0f27742` passed 255 Ubuntu tests and a generated-key, public-only
consumer fixture. Local Windows validation has 254 passes/one Unix-only skip.
Production deployment, separate OS identities and live acceptance remain open.

| Package | Remaining work | Acceptance before closing |
| --- | --- | --- |
| P1 · Current cash and reservations | Supported per-currency settled-cash source; fee currencies/buffers; allocation ownership; current negative-cash handling; atomic capital/fee reservations and release rules | Evidence is fresh, exact-account and scoped; USD/other currencies never offset unknown debits; missing evidence and concurrent overspending fail closed; no automatic FX conversion or debt repayment |
| P2 · Full broker reconciliation | Order account attribution, manual/session visibility, pending orders, fills, partial fills, commissions, transfers and stable account observations | Explain every current allocation cash/position change; pending/ambiguous activity blocks funding; restart/reconnect cannot lose commitments or double count capital |
| P3 · Research and full agent workflow | Broader approved sources, opportunity discovery, independent countercase, supported narrative/thesis claims and contradictions; full research/PM/CEO/risk/committee live advisory acceptance | Real evidence-backed proposals, revisions and abstentions pass through all reviews; unsupported claims/injections fail; persistent memory/costs and fresh quotes verified; no hardcoded trading signals |
| P4 · Portfolio-wide accounting and risk | Aggregate concentration/exposure, liquidity and stress checks; fees/FX and relevant corporate actions; marked net performance and cost attribution | Multiple concurrent proposals remain within owner limits; fees/API costs reduce available capital and measured returns; unsupported asset/currency/event stays blocked; no leverage/shorts |
| P5 · Independent security and authorization | Collector/controller/executor OS separation, protected keys and configuration, versioned policy, short-lived signed permits, owner access controls, kill switch and independent audit | Agents cannot access broker credentials or mint permits; wrong account/contract/amount, stale/forged/replayed permits and owner-policy changes fail; restart preserves a safe stop |
| P6 · Controlled paper executor | Paper-only submission, idempotency, price/quantity bounds, order lifecycle, reservation/fill linkage, cancel/recovery handling and reconciliation | P1/P2/P4/P5 gates pass first; narrow authorized paper trial passes; disconnect ambiguity, duplicate submissions, partial fills and crashes do not overspend or duplicate orders |
| P7 · Autonomous operations and VM reliability | Bounded scheduling, evidence refresh, budget/health alerts, daily/weekly reporting, Gateway reauthentication/recovery, backups/restores, log limits and 1 GB memory/swap testing | Repeated unattended paper cycles and recovery tests pass; authentication-required events alert the owner; no indefinite retries, silent failures, credential bypass or resource exhaustion |
| P8 · Sustained paper acceptance and outcome learning | Shadow/paper observation, abstention and downside review, investment outcome feedback, net cost/performance reporting and operational readiness review | Complete a declared observation period and failure scenarios; records reconcile; measured costs fit the mandate; feedback changes still need review; no claim that a short trial proves 15% annual returns |

Suggested dependencies: P1 → P2; P3 and P4 can progress alongside data work.
P5 is required before P6. P7's deployment foundations can start earlier, but order
scheduling waits for P6 acceptance. P8 requires the complete controlled paper flow.
Routine small documentation/acceptance updates should accompany their implementation
PR rather than each becoming a new numbered package.

## Live readiness: three additional packages

| Package | Remaining work | Acceptance before closing |
| --- | --- | --- |
| L1 · Swedish ISK and applicable legal eligibility | Independently verified account identity/type/country and instrument eligibility; applicable US/Swedish/EU requirements; enforceable extensions to owner rules | Login choice alone cannot certify eligibility; unverifiable or conflicting requirements block live access; unresolved legal/account questions require authoritative verification |
| L2 · Live access and capital controls | Explicit owner authorization, isolated live broker permissions, exact account pin, capital allocation, fees/FX, tighter initial operating limits and emergency stop | Paper credentials/configuration cannot silently switch to live; owner can revoke access; all independent gates must pass; no CEO/committee override |
| L3 · Limited live commissioning | Explicitly authorized small live deployment, actual settlement/fill reconciliation, alerts, incident recovery and staged scope review | Independently reviewed paper/security/eligibility acceptance first; reconcile each live outcome; stop on unexpected state; expand only after reviewed evidence and owner-authorized access scope |

Live work is a separately authorized phase, outside the current paper roadmap.
Completing these packages does not guarantee investment performance or legal
eligibility for every instrument. Unsupported scope stays disabled.

## Immediate blockers and owner involvement

The explicit SettledCash summary returned no row. Current per-currency USD settled
cash is not established; Gateway schedule serialization remains unverified. The
current SEK debit remains a funding block, regardless of its accepted prior cause.
Manual-order visibility, monetary reservations and full reconciliation are incomplete.
We will not investigate the owner's prior transactions further.

The owner supplies capital, controls access, sets overriding rules and intervenes.
Gateway authentication and any consequential funding/currency action remain owner
actions. Routine research, investment recommendations and company management belong
to the CEO within independently enforced limits. No live trading or new recurring
automation is authorized by this plan. Current execution remains disabled.

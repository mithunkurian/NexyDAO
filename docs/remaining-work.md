# Remaining work and planned PR packages

Planning snapshot: 13 October 2026, Europe/Stockholm.

Estimate: **8 substantial implementation PR packages to autonomous paper operation**,
then **3 separate live-readiness packages**. This is a scope estimate, not a promise
of exactly 11 PRs. Broker compatibility, source availability, security findings and
acceptance failures may need extra fixes or splits. Ongoing evaluation also takes
elapsed observation time; a PR merge cannot substitute for that evidence.
PR #14 documents completed acceptance and is separate from this future estimate.

## Autonomous paper operation: eight packages

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

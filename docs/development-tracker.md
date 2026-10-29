# NexyDAO — Development tracker

Updated: **29 October 2026 · Europe/Stockholm**

**Current checkpoint:** M2A validated; initial research and USD Portfolio Manager slices validated; host ingress guard verified.
**Next checkpoint:** Expanded SEC evidence and the nine-role advisory abstention path are validated. Continue P3's remaining evidence/revision work and P4 accounting/risk independently of the blocked Web ledger acceptance. PR #16 remains draft; the owner reports the IBKR support ticket was submitted and no reply received. P1 acceptance is deferred, not passed. Current debit/fee funding, broker allocation ownership and monetary reservations remain open. The owner excluded further investigation of prior transactions.
**Execution:** Disabled. **Operating mode:** Manual, bounded paper trials.

Human access/maintenance procedures: [owner maintenance SOP](owner-maintenance-sop.md).
It records what to do, why and when, including daily Web login while in use,
incident-triggered tunnel recovery and the current certificate renewal deadline.
It does not create a reminder or maintenance automation.

## Company brief

| Item | Current position |
| --- | --- |
| Capital | Persistent $5,000 USD simulation ledger; full FX/tax/broker accounting still pending |
| Objective | 15% annual net return; an objective, never a guarantee |
| Investment decisions | AI reasoning supported by verified evidence; no hardcoded trading strategy |
| Owner | Provides capital, controls access, sets binding owner constraints and intervenes when needed |
| CEO | Routine mandate, strategy, investment/research proposals, budget planning and performance oversight within enforced limits |
| Infrastructure | Ubuntu 24.04 VM, Python 3.12, 1 GB RAM + 1 GB swap; sustained operation still needs testing |
| Current AI roles | Six core calls; eight with research; seven with Portfolio Manager; nine with both |
| Autonomy | Research and seven-call advisory Portfolio Manager validated; scheduling, broader accounting and execution pending |

## Milestone board

Status key: **Validated** = acceptance evidence recorded; **In progress** = implemented work with open gates; **Planned** = not implemented.

| ID | Milestone | Status | Evidence / remaining acceptance |
| --- | --- | --- | --- |
| M1 | Architecture and auditable AI deliberation | **Validated** | Real six-call VM cycle; strict records; persistent memory; settled costs; execution denial |
| M2A | Read-only IBKR paper connectivity | **Validated** | Exact account pin matched; four summary fields; deliberate wrong pin rejected before summary |
| M2B | Verified market evidence and research | **In progress** | Quote component, typed SEC source checks and two-researcher cycle validated. Wider narrative/cross-publisher corroboration remains pending |
| M3 | Portfolio Manager and simulated accounting | **In progress** | USD ledger and advisory manager slice tested/VM-validated. Quote-backed allocations tested offline; FX/tax/corporate actions and actual broker reconciliation pending |
| M4 | Independent authorization and paper execution | **Planned; locked** | Isolated executor, signed permits, kill switch, exposure reservations and execution failure tests |
| M5 | Autonomous paper operations | **Planned** | Bounded scheduling, recovery, alerts, outcome learning and sustained performance evaluation |

No overall completion percentage is assigned: milestones differ substantially in scope.
Passing M2A does not mean NexyDAO is autonomously investing.

Remaining implementation estimate: **8 substantial PR packages to autonomous paper
operation**, followed by **3 separately authorized live-readiness packages**.
Compatibility/security fixes may add PRs; observation periods require real elapsed
time. See the [remaining-work checklist](remaining-work.md) for scope, dependencies
and acceptance criteria. Small documentation updates accompany those packages.

## Current work queue

### P4 simulation hold/fill linkage — 29 October 2026

Branch `codex/simulation-held-fills` adds opt-in operator fixtures for atomic buy
fill/hold consumption, separate notional/fee budgets, partial fills, terminal
consumption, replay validation and same-ID retries. Fresh valuation, current
funding and owner policy remain required; residual capacity releases explicitly.
The normal unlinked fill path remains available with all holds counted. No real
broker reservations, order submissions or autonomous agent mutation tools are
introduced. Local/VM acceptance is recorded with the implementation below.

### P4 reporting slice — 29 October 2026

Branch `codex/portfolio-risk-report` adds reconciled net-performance attribution
and three hypothetical portfolio-wide price shocks to the existing portfolio view.
Active planning holds include full assumed fee payment; expired marks produce
unknown scenario totals. Reports preserve cash, holds, revision and execution denial.
Implementation `dbea8df` passed all 208 offline tests locally and in isolated Ubuntu
release `releases/portfolio-risk-dbea8df`. A report over a private persistent-ledger
backup reconciled net equity and API expenses without changing state or call counts;
the original database was read in read-only mode. Full P4 accounting/risk remains open, including
FX/tax/corporate actions, liquidity/stress enforcement and broker-linked lifecycle
accounting. No paid call or broker request is required by this slice's offline tests.

### P3 development slice — 28 October 2026

Branch `codex/research-filing-context` starts from merged `main`, independently of
draft PR #16. It adds operator-selected approved SEC financial concepts, a signed
concept manifest and exact metric/unit/period/filing bindings in research claims.
At most nine filing facts preserve room for one quote. Missing fields, incomplete
provenance and scope changes fail closed. Legacy receipts retain their original scope.

All **202 offline tests passed locally**, including expanded seven-fact nine-role
advisory flow and wrong-context rejection before manager/CEO. The nine-role fixture
uses Portfolio Manager abstention without a quote; it does not validate an allocation.
PR #17 merged as `c28a0ec`. On 29 October, all 202 tests also passed in the isolated
Ubuntu release, and real SEC retrieval verified all seven selected MSFT filing
observations with a private signed receipt. After explicit owner approval, paid run
`27d62b74-5165-4f51-a98e-a94cc871679a` completed all nine roles with checked claim
contexts, Portfolio Manager abstention and CEO investigation. Estimated cycle cost
was $0.01362225; cumulative costs were $0.02957985 over 38 calls, zero unsettled,
under the unchanged $0.10 lifetime budget. Memory persisted after reopening SQLite;
simulation cash/revision stayed unchanged. Narrative verification, quote-backed
allocation, linked proposal revisions and complete P3 acceptance remain open.
P4 accounting/risk is the next independent workstream. Funding and execution stay
disabled; no broker requests or schedules were introduced by this validation.

| Task | Status | Acceptance condition |
| --- | --- | --- |
| E01 · Fresh SPY quote | **Validated · 12 Oct** | Fresh paper BidAsk observation received; exact pin, unique contract, signature and expiry verified |
| E02 · Quote-fed AI cycle | **Validated · 12 Oct** | Six role calls completed while evidence remained fresh; one quote citation; memory and settled costs persisted |
| E03 · PR #3 | **Merged** | Merge commit `bf94f8a`; local main synced; execution remains disabled |
| E04 · Research agents and approved sources | **Validated · 12 Oct** | Two live SEC observations and independent reports; eight-call cycle completed with tightened schema; initial safety rejection retained in audit |
| E05 · Research verification | **Partial; offline tested** | Typed numeric claim binding, source identity, signatures, freshness and contradictions. Prose/forecasts and cross-publisher corroboration remain unverified |
| O01 · Mandatory owner policy | **Validated implementation; 76 tests passed locally/VM/CI** | No shorts, leverage or borrowing; applicable US/Swedish compliance; Swedish ISK for future live execution. Versioned extensions and independent denial; legal/account/holder attestation pending |
| S01 · Independent broker ingress restriction | **Host guard validated; wider security gates open** | Kernel rule verified on VM for IPv4/IPv6; service enabled/active; SSH and loopback VNC preserved. Cloud policy, boot and OS isolation remain open |
| S02 · Gateway reconnection reliability | **Open** | Repeated controlled reconnects, authentication/restart behavior and failure recovery tested |
| S03 · Sustained 1 GB trial | **Open** | Observe memory/swap under repeated workloads and recovery; one successful short trial is insufficient |
| S04 · Collector/consumer OS separation | **Planned** | Separate service identities and protected configuration/key; compromised application code cannot forge collector receipts |
| P01 · Simulated ledger and Portfolio Manager | **USD slice validated; 92 tests locally/VM/CI** | Seven paid calls completed with safe quote-free abstention; persistent $5,000 funding unchanged. Positive quote-backed plans/nine-call combination tested offline; broader/live allocation coverage pending |
| X01 · Authorization and executor | **Locked until M4 acceptance** | Forged, stale and replayed permits; duplicate/partial fills; restarts and account mismatch all fail safely |
| A01 · Authenticated account summaries | **Initial summary slice validated; 104 tests locally/VM/CI** | Fresh four-tag receipt and consumer verified exact pin/HMAC; wrong pin and expiry rejected. USD summary incomplete; settled cash/positions/orders/fills and funding reconciliation remain open |
| A02 · Per-currency cash and contract positions | **Initial comparison slice validated; 123 tests locally/VM/CI** | Fresh signed six cash rows/three currencies and completed zero positions. Missing explicit SettledCash and negative currency observation flagged; full reconciliation/funding remain false |
| A03 · Settlement and currency funding | **Diagnostic slice validated; 135 tests locally/VM/CI; funding locked** | Fresh v2 receipt preserves four raw schedules privately, durable denial case; negative SEK still observed. Schedule semantics and transaction-level cause remain unverified; owner has no saved statement |

## Market-open validation session — completed

The manual session on **Monday, 12 October 2026** passed the quote and AI consumption
gates during the regular US equity session. The originally suggested window was
15:35 Stockholm / 09:35 New York. [NYSE calendar and trading hours](https://www.nyse.com/trade/hours-calendars).
No scheduled automation was created.

- [x] Owner reconnects Gateway using **IB API → Paper Trading** and confirms connected.
- [x] Collect one fresh SPY quote.
- [x] Verify receipt signature, pinned account, contract and event-time expiry.
- [x] Run one six-role AI cycle within the existing persistent API budget.
- [x] Confirm citations, six role records, durable memory, settled costs and execution denial.
- [x] Record live acceptance here and in the milestone register.

No fresh data means no verified receipt and no claim that this gate passed.
Quote verification validates an observation; full investment research still requires E04–E05.

## Validation log

| Date | Check | Recorded result |
| --- | --- | --- |
| 11 Oct 2026 | Real CEO/risk/committee cycle on VM | Six OpenAI calls completed; CEO chose `investigate`; no orders |
| 11 Oct 2026 | Memory and cost persistence | Database reopened successfully; six settled cost entries; zero unsettled reservations |
| 11 Oct 2026 | API token estimate | **$0.00079860** cumulative for the recorded cycle; configured lifetime budget **$0.10**; billing reconciliation remains separate |
| 11 Oct 2026 | Offline safeguards and evidence tests | **45 passed** on Windows and Ubuntu Python 3.12; implementation baseline `abde107` |
| 11 Oct 2026 | GitHub Actions | Passed on documentation head `8f96364`; [CI run](https://github.com/mithunkurian/NexyDAO/actions/runs/38127609232) |
| 11 Oct 2026 | Exact paper-account pin | Matched; all four account summary fields retrieved; private snapshot retained |
| 11 Oct 2026 | Wrong-pin test | `account_mismatch` rejected before a summary request |
| 11 Oct 2026 | Contract and quote trial | Protocol 178; one SPY SMART/USD contract resolved; live BidAsk subscription reached; no fresh tick within 15 seconds; no receipt issued |
| 11 Oct 2026 | Reconnection | Some earlier sessions disconnected before identity; later spaced checks passed; reliability remains open |
| 12 Oct 2026 | VNC/Gateway recovery | Restored localhost SSH tunnel and verified VNC protocol banner; owner reauthenticated paper Gateway after the timed trial ended |
| 12 Oct 2026 | Fresh live SPY quote | Protocol 178; pinned account; unique contract; fresh BidAsk observation and signed receipt verified |
| 12 Oct 2026 | Quote-fed AI cycle | Run `0b5996e0-3d11-48da-8cd2-84eab52123f3`; six calls, two risk reviews, three votes; CEO chose `investigate` and cited one evidence item; execution false |
| 12 Oct 2026 | Costs and memory | Cycle estimate **$0.00196425**; cumulative **$0.00276285** across 12 calls; zero unsettled reservations; completed run persisted after reopening SQLite |
| 12 Oct 2026 | Research implementation | 65 offline tests passed locally; eight-call workflow, independent contexts, claim rejection, source bounds and mocked costs. Not paid/live acceptance |
| 12 Oct 2026 | Research VM/CI | All 65 tests passed on Ubuntu/Python 3.12 in isolated release `184ed13`; offline demo denied execution; CI passed. No SEC or paid API requests |
| 12 Oct 2026 | Live SEC source | Private contact configured; MSFT ticker/CIK and two typed filing observations retrieved, signed and verified; contact excluded from prompts/Git |
| 12 Oct 2026 | Research safety stop | Initial attempt stopped before CEO on invalid candidate structure after two calls; cumulative **$0.00396210**, 14 calls, zero unsettled reservations. Not a completed research acceptance run |
| 12 Oct 2026 | Schema correction | Dataset-specific issuer/reference enums, candidate bounds and required nonempty claims added; 66 local tests passed; live retest pending |
| 12 Oct 2026 | Live research retest | Implementation `c21c998`; all 66 VM tests/CI passed. Run `01ad46d4-0ba0-4d8f-ba55-d392a518df60`: eight calls, two independent reports with one candidate each, two risk reviews, three votes; CEO chose `investigate`; execution false |
| 12 Oct 2026 | Research costs and memory | Successful cycle **$0.00530400**; cumulative **$0.00926610** over 22 calls including the failed attempt; zero unsettled reservations. Memory persisted after reopening |
| 12 Oct 2026 | Portfolio tests | Implementation `4398122`: 92 tests passed locally, Ubuntu VM and CI; ledger/concurrency/reconciliation and advisory seven/nine-call flows |
| 12 Oct 2026 | Paid Portfolio Manager | Run `5666cb3b-1f13-4b79-aca4-d296ad2d008b`: seven calls, zero allocations without fresh quotes; CEO `investigate`; no simulated fills, revision unchanged, execution false |
| 12 Oct 2026 | Portfolio costs/state | Cycle **$0.00669150**; cumulative **$0.01595760** over 29 calls; zero unsettled reservations. Memory persisted; $5,000 ledger funding seeded once and retained; internal reconciliation passed |
| 12 Oct 2026 | Host guard and account audit tests | `7cf7809`: 104 tests passed locally, Ubuntu VM and CI; no OpenAI calls |
| 12 Oct 2026 | Host guard deployment | Initial Windows archive line endings prevented service execution; Git attributes corrected. Final service enabled/active and exact kernel IPv4/IPv6 drop rule verified; SSH and loopback VNC preserved |
| 12 Oct 2026 | VNC recovery | Owner reported 10061; local tunnel had stopped. Restored localhost forwarding and verified VNC banner at `127.0.0.1:15901`; Gateway authentication and fresh account audit pending |
| 12 Oct 2026 | Fresh signed paper summary | Owner reauthenticated Gateway. Initial probes rejected notification 10141; spaced client 95 trial passed with no safeguard changes. Four summary tags and fresh HMAC receipt/consumer validated; USD rows incomplete, no negative values observed |
| 12 Oct 2026 | Account-audit safety checks | Wrong pin and exact 60-second expiry boundary rejected; private receipt mode 0600. Simulation cash/unsettled cash/revision unchanged; no balance import, no OpenAI calls, no execution |
| 12 Oct 2026 | Cash/position collector tests | `0ff1b3a`: 123 tests passed locally/Ubuntu VM/CI. Live metadata established exact `$LEDGER-` cash prefix and unparsed `SettledCashByDate`; narrowly scoped cancellation acknowledgement compatibility tested |
| 12 Oct 2026 | Cash/position trial status | Initial unsupported fields/acknowledgement stopped collection; corrected final trial could not connect after the 30-minute Gateway timer expired. Reopened login window; completed fresh receipt pending. No orders/OpenAI calls |
| 12 Oct 2026 | Fresh cash/position acceptance | `0ff1b3a`: owner reauthenticated; initial post-login disconnect, then spaced client 95 trial passed. Six cash rows/three currencies and completed zero positions; receipt and comparison validated; wrong pin/expiry rejected |
| 12 Oct 2026 | Funding observations and isolation | Explicit USD SettledCash absent, schedule unparsed, negative currency cash observed. Funding/full reconciliation remain false. Receipt 0600; ledger/revision/API costs unchanged; host guard verified; zero OpenAI calls/orders |
| 13 Oct 2026 | Funding diagnostic implementation | `d923b13`: all 135 tests passed locally, Ubuntu VM and CI; v1 compatibility, bounded signed schedule preservation, policy/expiry checks and independent persistent denials |
| 13 Oct 2026 | Fresh funding review | Six cash rows, zero positions, four settlement observations; signed v2 consumer passed. Case `5129c425-4901-48df-a042-171000c404d6` persisted after reopening. Negative SEK observed, cash fields agreed, cause unresolved; no saved statement available |
| 13 Oct 2026 | Safeguards and state | Funding/execution denied; ledger/revision/API costs unchanged; private receipt 0600; host guard verified; zero OpenAI calls/orders. Initial probe disconnected; spaced trial passed; sustained recovery remains open |

### Paper statement investigation · 13 October

The authenticated paper Activity Statement for 16 April–12 October was reviewed
in the portal. Its account matched the VM's exact private pin. The SEK Cash Report
starts at zero, reports commissions, and ends with a debit equal to the two
EUR/USD trade commissions on 13 and 14 September. This explains the historical
SEK debit; it does not authorize funding or change a diagnostic case.

A manually transcribed observation was saved privately on the VM with mode 0600.
HTML and CSV download attempts returned no downloadable artifact; an original
statement export has **not** been archived or authenticated by application code.
The account reports margin capabilities and earlier USD debit interest; the
origin of that earlier USD debit remains outside the available history.
Historical ending settled cash does not establish fresh spendable cash today.
The ledger, costs, account settings and unconditional execution denial were not
changed. The next implementation gate is bounded, exact-account statement
validation and independent funding reconciliation, including commissions by
their charged currency. M3/M4 remain incomplete.

Account identifiers, balances, credentials and receipt keys stay outside this tracker and Git.
No additional OpenAI calls were made by the read-only broker/quote checks.
No investment return has been measured.

## Pull requests and deployment

| PR | Scope | Current state |
| --- | --- | --- |
| [#1](https://github.com/mithunkurian/NexyDAO/pull/1) | Foundation, hierarchy, AI deliberation, records, memory, costs and safeguards | **Merged** |
| [#2](https://github.com/mithunkurian/NexyDAO/pull/2) | Read-only paper-account probe and milestone marker | **Merged** |
| [#3](https://github.com/mithunkurian/NexyDAO/pull/3) | Quote integrity/freshness adapter, tests and operational records | **Merged** |
| [#4](https://github.com/mithunkurian/NexyDAO/pull/4) | SEC observations, numeric claim verification and two research agents | **Merged — `6a4b604`** |
| [#5](https://github.com/mithunkurian/NexyDAO/pull/5) | Binding owner constraints above all agents | **Merged — `a0ea0b6`** |
| [#6](https://github.com/mithunkurian/NexyDAO/pull/6) | USD ledger and advisory Portfolio Manager | **Merged — `268f364`; limited USD slice, execution disabled** |
| [#7](https://github.com/mithunkurian/NexyDAO/pull/7) | Host ingress guard and authenticated account summaries | **Merged — `d59cd06`; full reconciliation pending** |
| [#8](https://github.com/mithunkurian/NexyDAO/pull/8) | Per-currency cash and contract position comparison | **Merged — `c501db3`; settlement and funding gates remain open** |
| [#9](https://github.com/mithunkurian/NexyDAO/pull/9) | Settlement evidence preservation and funding denial cases | **Merged — `694241b`; funding blockers remain unresolved** |
| [#10](https://github.com/mithunkurian/NexyDAO/pull/10) | Redacted paper statement findings and tracker update | **Merged — `09a974c`; documentation only** |
| [#11](https://github.com/mithunkurian/NexyDAO/pull/11) | Current-state capped USD allocation diagnostics | **Merged — `c2482e7`; fresh denial review persisted** |
| [#12](https://github.com/mithunkurian/NexyDAO/pull/12) | Nonbinding API-visible orders and combined allocation evidence | **Merged — `27053ee`; fresh scoped query and denial persisted** |
| [#13](https://github.com/mithunkurian/NexyDAO/pull/13) | Ledger cash scope and explicit settled summaries | **Merged — `84d79f8`; 170 tests passed locally/VM/CI; fresh ledger scope validated, settled-summary field absent** |
| [#14](https://github.com/mithunkurian/NexyDAO/pull/14) | Post-merge broker acceptance records | **Merged — e467a91; ledger scope validated, settlement evidence still incomplete** |

Development branch: `codex/currency-funding-reservations`.

Item 1 is **in progress**. The Web API's documented currency ledger is implemented
with mandatory TLS, fixed GET paths, paper/session/account checks, native freshness
and independent cross-source matching. Atomic USD simulation planning holds reduce
capacity and survive restarts without spending broker cash; foreign fees fail closed.
Implementation `d229ac3` passed all 196 tests locally, on Ubuntu and in CI (run 103).
The Web receipt fixture now anchors mock time behind the real consumer clock;
production freshness enforcement is unchanged. The VM host guard now independently
protects port 5000 for IPv4/IPv6. Ubuntu Java 17 was installed for the official
Client Portal Gateway. A bounded 45-minute trial is running with a 160 MB heap cap,
private local TLS files and restricted worker pools. Certificate/hostname validation
passed. The vendor listener binds 0.0.0.0; the verified kernel rule denies all
non-loopback TCP ingress. The VM's system trust store was not changed. With explicit
owner approval, the exact localhost certificate was added to the laptop's Windows
current-user trust store; public certificate only, no private key imported. A default
Windows-root TLS check passed and matched the approved fingerprint with hostname
verification enabled. The expired Web trial and laptop tunnel were restored using
the same certificate. Browser refresh and owner paper login remain pending.
The laptop tunnel exposes only 127.0.0.1:15000 and forwards to VM localhost:5000.
The API is unauthenticated; owner paper login is pending. No real Web ledger receipt
or broker funding acceptance exists yet. Tests used isolated databases; persistent
capital/API accounting was not reset or replaced. Item 1 stays in progress.
No package is struck off merely because a component merges. See
[Item 1 scope](currency-reservations.md) and [remaining checklist](remaining-work.md).

Settlement-scope slice: v3 receipts preserve per-currency ledger-prefix provenance;
legacy/bare aggregate rows cannot establish spendable USD. `settlement-check`
queries the explicit summary tag but never imports its account aggregate as ledger
cash. Implementation `11e632f` passed all 170 tests locally, on Ubuntu and in CI
(run 90). The previous Gateway trial expired; launcher restarted on VNC display 1.
Initial post-merge checks found Gateway running with all API ports closed. The owner
confirmed it had logged out and logged back in. Port 4002 then opened. The first
probe disconnected; a spaced retry completed the explicit summary request but
returned no SettledCash row, failing safely without saving a summary receipt.
A separate fresh v3 cash/order trial validated per-currency ledger scope: six cash
rows, zero positions and zero API-visible order activity frames. Review
`2bf4799a-3b22-42cf-bcc1-dd17a3412b22` persisted after SQLite reopening. Cash receipt
mode 0600 and host guard verified; ledger/revision/API costs unchanged. USD settled
cash still absent and SEK negative, so capacity/funding/execution remained zero/denied.
No OpenAI calls, broker writes or historical transaction investigation occurred.
Reservation amounts
remain unverified; no funding or execution permission is introduced.

Open-order slice: `broker-orders` performs one nonbinding API-visible query and
preserves bounded activity digests in a fresh signed receipt. Allocation reviews
bind this evidence; missing, stale or nonempty observations force zero planning
capacity. Empty API scope does not clear manual orders or reservations. All 160
tests passed locally, on Ubuntu and in CI (implementation `c896f75`, CI run 85).
Fresh trial: first probe disconnected; one spaced retry completed the API query
with zero activity frames, then collected six cash rows and zero positions.
Combined review `ba38fecc-50ea-42e2-b0eb-e32e65b96cb0` persisted after reopening;
both receipts were fresh at review. Order receipt mode 0600 and host guard verified;
ledger/revision/API costs unchanged; no OpenAI calls or broker writes.
Manual-order coverage, monetary reservations and atomic state remain false.
Settlement serialization remains unverified and unparsed; USD cash incomplete and
SEK negative, so capacity/funding/execution remained zero/denied. No historical
transaction investigation is added. Connection recovery remains an open gate.

Current allocation slice: `allocation-check` keeps the USD cap separate from
whole-account balances, subtracts API estimates and a configurable planning fee
buffer, and persists an independent denial review. Final implementation `09cc513`
passed all 147 tests locally, on Ubuntu and in CI (run 78). After owner paper login,
the first probe disconnected; one spaced retry collected six cash rows and zero
positions. Review `b699051f-7ba2-4839-8d7e-19f1933d4bb9` persisted after reopening
SQLite. Explicit USD cash remained incomplete and SEK remained negative, so the
planning ceiling was zero and funding/execution were denied. The $5,000 cap and
$50 planning fee buffer were recorded; neither reserves broker funds. Receipt mode
was 0600, host guard verified, and ledger/revision/API costs were unchanged.
No OpenAI calls or broker writes occurred. Sustained connection recovery remains open.
No original statement download or review of past transactions is required by this
slice. Current negative cash is still independently blocked. Open orders,
settlement semantics and actual allocation reservation remain future gates.
Historical Git marker: `milestone-2a-paper-connectivity` (unchanged).
Merged baseline `b435b10` and quote implementation `abde107` were tested in isolated
VM release directories. The existing VM repository and credential files were preserved.
The quote trial is not a production deployment or authorization to trade.

## Safeguards and responsibilities

- Agents have no filesystem, shell, credential or broker execution tools.
- Broker execution remains unconditionally denied, regardless of CEO or committee approval.
- Owner access control and intervention remain independent of agent decisions.
- Binding owner constraints outrank all agents; new rules require independent enforcement before investment authorization.
- Owner-policy baseline `d34f605` passed 75 VM/CI tests with a private policy file and retained audit hash; the added snapshot-construction guard brings local tests to 76.
- Final implementation `ad1fe0d` passed all 76 tests on the VM and in CI; no paid API or broker operations were performed.
- Paper-account identity and exact pin are checked independently before market requests.
- Signed receipts establish local integrity, not an IBKR signature or verified investment thesis.
- OS isolation, aggregate portfolio risk accounting and executor authorization remain explicit future gates.
- Routine business management belongs to the CEO; engineering implementation and testing are development work, not an additional investment-agent role.

## How this tracker is maintained

Update this page after a completed check, material blocker, PR merge or deployment.
Mark work **Validated** only when its acceptance evidence is recorded; keep historical
results and identify the tested commit. Do not replace the persistent cost database to
refresh its budget. This page is a maintained snapshot, not a background monitor or
an automatically synchronized ChatGPT Page.

Details: [milestone evidence](milestones.md) · [roadmap](roadmap.md) ·
[architecture](architecture.md) · [quote trial](market-evidence.md) · [research trial](research.md) · [portfolio trial](portfolio.md) · [owner policy](owner-policy.md) · [deployment](deployment.md).

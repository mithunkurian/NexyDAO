# NexyDAO — Development tracker

Updated: **11 October 2026 · Europe/Stockholm**

**Current checkpoint:** M2A validated; M2B quote adapter implemented, live acceptance pending.
**Next checkpoint:** Fresh quote → six-role AI deliberation → PR #3 ready for review.
**Execution:** Disabled. **Operating mode:** Manual, bounded paper trials.

## Company brief

| Item | Current position |
| --- | --- |
| Capital | $5,000 simulated starting capital; full portfolio accounting is not built yet |
| Objective | 15% annual net return; an objective, never a guarantee |
| Investment decisions | AI reasoning supported by verified evidence; no hardcoded trading strategy |
| Owner | Provides capital, controls access and intervenes when needed |
| CEO | Routine mandate, strategy, investment/research proposals, budget planning and performance oversight within enforced limits |
| Infrastructure | Ubuntu 24.04 VM, Python 3.12, 1 GB RAM + 1 GB swap; sustained operation still needs testing |
| Current AI roles | Six sequential calls: CEO, two Risk Officers, three committee voters |
| Autonomy | Scheduling, research discovery, portfolio management and execution are not yet operational |

## Milestone board

Status key: **Validated** = acceptance evidence recorded; **In progress** = implemented work with open gates; **Planned** = not implemented.

| ID | Milestone | Status | Evidence / remaining acceptance |
| --- | --- | --- | --- |
| M1 | Architecture and auditable AI deliberation | **Validated** | Real six-call VM cycle; strict records; persistent memory; settled costs; execution denial |
| M2A | Read-only IBKR paper connectivity | **Validated** | Exact account pin matched; four summary fields; deliberate wrong pin rejected before summary |
| M2B | Verified market evidence and research | **In progress** | Quote adapter, signatures, freshness and integrity tests implemented. Fresh live quote, AI consumption and research/source verification still pending |
| M3 | Portfolio Manager and simulated accounting | **Planned** | Positions, cash, FX, fees, fills, reconciliation and aggregate risk limits |
| M4 | Independent authorization and paper execution | **Planned; locked** | Isolated executor, signed permits, kill switch, exposure reservations and execution failure tests |
| M5 | Autonomous paper operations | **Planned** | Bounded scheduling, recovery, alerts, outcome learning and sustained performance evaluation |

No overall completion percentage is assigned: milestones differ substantially in scope.
Passing M2A does not mean NexyDAO is autonomously investing.

## Current work queue

| Task | Status | Acceptance condition |
| --- | --- | --- |
| E01 · Fresh SPY quote | **Waiting for live data** | Collector receives a fresh bid/ask observation, validates the contract and writes a signed receipt |
| E02 · Quote-fed AI cycle | **Waiting on E01** | CEO, both risk reviewers and all three voters complete while evidence remains fresh; audit and costs persist |
| E03 · PR #3 review readiness | **Waiting on E01–E02** | Live acceptance recorded, tests green, limitations documented; change draft to ready for review |
| E04 · Research agents and approved sources | **Planned** | Collect opportunities and source material with bounded access; agents cannot self-certify evidence |
| E05 · Research verification | **Planned** | Verify retrieval, timestamps, claim support and contradictions; reject fabricated citations, spoofing, injection and unsafe source access |
| S01 · Independent broker ingress restriction | **Open** | Verify VM/cloud enforcement prevents remote API access; Gateway was observed bound to a wildcard socket |
| S02 · Gateway reconnection reliability | **Open** | Repeated controlled reconnects, authentication/restart behavior and failure recovery tested |
| S03 · Sustained 1 GB trial | **Open** | Observe memory/swap under repeated workloads and recovery; one successful short trial is insufficient |
| S04 · Collector/consumer OS separation | **Planned** | Separate service identities and protected configuration/key; compromised application code cannot forge collector receipts |
| P01 · Simulated ledger and Portfolio Manager | **Planned after evidence work** | Reconcile the $5,000 portfolio, fees and proposals; independently enforce aggregate exposure and drawdown limits |
| X01 · Authorization and executor | **Locked until M4 acceptance** | Forged, stale and replayed permits; duplicate/partial fills; restarts and account mismatch all fail safely |

## Next validation session

**Suggested window:** Monday, **12 October 2026, 15:35 Stockholm / 09:35 New York**,
shortly after the scheduled regular US equity open. [NYSE calendar and trading hours](https://www.nyse.com/trade/hours-calendars).
This is a proposed manual session, not a scheduled automation.

- [ ] Owner reconnects Gateway using **IB API → Paper Trading** and confirms connected.
- [ ] Collect one fresh SPY quote; inspect data permissions if no usable quote arrives.
- [ ] Verify receipt signature, pinned account, contract and event-time expiry.
- [ ] Run one six-role AI cycle within the existing persistent API budget.
- [ ] Confirm citations, six role records, durable memory, settled costs and execution denial.
- [ ] Record results here and in the milestone register; make PR #3 ready only after acceptance.

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

Account identifiers, balances, credentials and receipt keys stay outside this tracker and Git.
No additional OpenAI calls were made by the read-only broker/quote checks.
No investment return has been measured.

## Pull requests and deployment

| PR | Scope | Current state |
| --- | --- | --- |
| [#1](https://github.com/mithunkurian/NexyDAO/pull/1) | Foundation, hierarchy, AI deliberation, records, memory, costs and safeguards | **Merged** |
| [#2](https://github.com/mithunkurian/NexyDAO/pull/2) | Read-only paper-account probe and milestone marker | **Merged** |
| [#3](https://github.com/mithunkurian/NexyDAO/pull/3) | Quote integrity/freshness adapter, tests and operational records | **Draft — live quote acceptance pending** |

Development branch: `codex/verified-market-evidence`.
Historical Git marker: `milestone-2a-paper-connectivity` (unchanged).
Merged baseline `b435b10` and quote implementation `abde107` were tested in isolated
VM release directories. The existing VM repository and credential files were preserved.
The quote trial is not a production deployment or authorization to trade.

## Safeguards and responsibilities

- Agents have no filesystem, shell, credential or broker execution tools.
- Broker execution remains unconditionally denied, regardless of CEO or committee approval.
- Owner access control and intervention remain independent of agent decisions.
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
[architecture](architecture.md) · [quote trial](market-evidence.md) · [deployment](deployment.md).

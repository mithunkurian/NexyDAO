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

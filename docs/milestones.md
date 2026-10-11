# NexyDAO milestone register

Recorded: 2026-10-11 (Europe/Stockholm).

Current checkpoint: **M2A — Read-only paper connectivity validated**.
Git marker: `milestone-2a-paper-connectivity`.

This marker records tested development code and a successful bounded VM trial.
It is not a production release, permission to execute orders, or evidence of returns.
PR #1 and [PR #2](https://github.com/mithunkurian/NexyDAO/pull/2) are merged.
The historical Git marker remains unchanged; subsequent validation is recorded below.

## Progress against the roadmap

| Checkpoint | Status | Evidence / remaining acceptance |
| --- | --- | --- |
| M1: Architecture and auditable AI deliberation | VM AI cycle validated | Six paid role calls completed, cost reservations settled and memory persisted after reopening SQLite. |
| M2A: Read-only IBKR paper connectivity | Validated; PR #2 merged | Four summary fields retrieved; exact pin matched; deliberate wrong pin rejected before summary; private snapshot saved; connection closed. |
| M2B: Verified market evidence and research | Quote adapter implemented; operational acceptance pending | Signed receipts, unique contract resolution, freshness and tampering tests. Live fresh quote/AI consumption, research agents and full source verification remain pending. |
| M3: Portfolio Manager and simulated accounting | Not implemented | $5,000 ledger, positions, cash/FX/fees, reconciliation, aggregate exposure and drawdown controls. |
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
2. Consume a fresh signed quote in a paid cycle; the no-quote baseline is validated below.
3. Complete M2B research and source verification; account balances alone are not investment evidence.
4. Test Gateway reconnection, daily/weekly authentication requirements, recovery and
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

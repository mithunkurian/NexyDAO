# NexyDAO milestone register

Recorded: 2026-10-11 (Europe/Stockholm).

Current checkpoint: **M2A — Read-only paper connectivity validated**.
Git marker: `milestone-2a-paper-connectivity`.

This marker records tested development code and a successful bounded VM trial.
It is not a production release, permission to execute orders, or evidence of returns.
PR #1 is merged; [PR #2](https://github.com/mithunkurian/NexyDAO/pull/2) is open for review
at the time this marker is recorded. The marker does not merge or deploy that PR.

## Progress against the roadmap

| Checkpoint | Status | Evidence / remaining acceptance |
| --- | --- | --- |
| M1: Architecture and auditable AI deliberation | Implementation delivered; PR #1 merged | CEO, two risk reviewers, three committee voters, structured records, SQLite memory and cost tracking, execution denial, offline tests. A paid end-to-end OpenAI cycle on the VM still needs operational validation. |
| M2A: Read-only IBKR paper connectivity | Validated; PR #2 awaiting merge | Gateway installed on the existing 1 GB VM; paper account namespace recognized; four summary fields retrieved; private snapshot saved; subscription cancelled and connection closed. |
| M2B: Verified market evidence and research | Not implemented | Contract/quote retrieval, timestamps/provenance/expiry, source verification, research agents and injection/fabricated-evidence tests. |
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

1. Pin the exact paper account locally and validate account mismatch rejection against
   the intended account. The smoke test used namespace recognition with the exact pin unset.
2. Verify independent VM/cloud ingress restrictions: Gateway's API socket was observed
   bound to a wildcard address despite the localhost connection setting.
3. Validate the real paid CEO/risk/committee cycle, audit persistence and recorded costs
   using locally provisioned credentials and a bounded budget.
4. Implement M2B verified market evidence; account balances alone are not investment evidence.
5. Test Gateway reconnection, daily/weekly authentication requirements, recovery and
   sustained memory/swap behavior before unattended operation.

The $5,000 simulated capital and 15% annual net return objective remain unchanged.
No measured investment return is available yet. Owner duties remain capital provision,
access control and intervention; the CEO owns routine company management within
independently enforced safeguards.

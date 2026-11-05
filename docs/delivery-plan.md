# Remaining delivery baseline

Baseline agreed after PR #23, 5 November 2026: **about 15 further PRs** to autonomous
paper operation, with a **12–18 PR range**. These are delivery packages within the
eight remaining workstreams, not eight individual PRs. The estimate excludes
real-money readiness and elapsed paper observation time.

The table keeps the scope finite and makes changes visible. A package may need a
split or a corrective PR when acceptance fails; record the reason and effect on
the estimate rather than silently growing this list. A merge does not close a
package until its recorded acceptance conditions pass. Slots do not impose strict
implementation order: independent work can proceed while broker access is blocked.

| Slot | Delivery package | Status at baseline |
| --- | --- | --- |
| S1 | SEC collector/consumer identity boundary, publication and protected configuration | In progress; next PR branch `codex/collector-consumer-boundary` |
| S2 | Remaining receipt/key isolation and real service startup/recovery acceptance | Planned |
| S3 | Independent policy authorizer, signed permits, nonce/replay checks and kill switch | Planned |
| D1 | Verified current cash, currencies/fees and funding gate closure | Blocked by broker acceptance |
| D2 | Full orders/fills/commissions/transfers and manual-activity visibility | Planned; partial readers exist |
| D3 | Broker cash/position lifecycle reconciliation and actual monetary reservations | Planned |
| R1 | Remaining research/quote-backed advisory and paid revision acceptance | Planned; initial live paths exist |
| R2 | Broader approved evidence and supported narrative/contradiction checks | Planned; typed SEC checks exist |
| R3 | Scoped FX/tax/corporate-action and portfolio accounting completion | Planned; USD simulation exists |
| R4 | Portfolio liquidity/stress enforcement and complete aggregate-risk acceptance | Planned; diagnostic reports exist |
| E1 | Narrow paper executor with permits, price/quantity bounds and idempotency | Locked until prerequisites |
| E2 | Execution ambiguity, partial fills, cancellation and crash/restart recovery | Locked until E1 |
| O1 | Bounded scheduling, health/alerts and tested backup/restore | Planned |
| O2 | VM/authentication reliability, resource limits and operational reporting | Planned |
| O3 | Sustained paper evaluation, outcome learning and readiness review | Planned; requires elapsed observation |

Current planning count: **0/15 packages closed after PR #23**. The next branch is
working on S1. S1 closes when its publication/permission mechanism passes local,
Ubuntu and two-UID acceptance and the PR merges. Real service installation and
startup/recovery acceptance belong to S2; live source/workflow gates also remain
explicit in their own workstreams. A successful S1 merge leaves about **14 PRs**
on this planning baseline, subject to the stated range and recorded scope changes.
The owner-facing overall progress estimate remains **approximately 45% (40–50%)**,
a subjective engineering guide rather than measured milestone completion or an
investment-readiness claim. Reassess it when material acceptance gates close.

Every PR handoff includes completed scope, validation evidence, remaining work,
blockers, the remaining delivery count and a labelled estimate/progress bar. Full
P1–P8 criteria remain in [remaining work](remaining-work.md). Real-money account,
eligibility, access and commissioning are a separate authorization/design phase.

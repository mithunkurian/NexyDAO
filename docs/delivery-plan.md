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
| S1 | SEC collector/consumer identity boundary, publication and protected configuration | Complete; PR #24 merged, 262 Ubuntu tests and two-UID acceptance |
| S2 | SEC role service deployment, protected configuration and bounded startup/restart audit | Complete; PR #25/#26 merged, all 12 installed audit checks passed |
| S3 | Independent policy authorizer, signed permits, nonce/replay checks and kill switch | In progress; PR #27 shadow protocol, PR #28 external owner control/identity fixture; accepted evidence and deployed authorizer still required |
| D1 | Verified current cash, currencies/fees and funding gate closure | Blocked by broker acceptance |
| D2 | Full orders/fills/commissions/transfers, manual visibility and public-key broker receipt integration | In progress; PR #29 fills/fees, PR #30 typed order-prefix/status diagnostics and public receipts; full semantics/coverage/transfers/live acceptance open |
| D3 | Broker cash/position lifecycle reconciliation, remaining broker key boundaries and actual monetary reservations | In progress; PR #31 public cash/position receipts and partial cross-observation diagnostics; lifecycle/monetary reservations/deployment remain open |
| R1 | Remaining research/quote-backed advisory and paid revision acceptance | Planned; initial live paths exist |
| R2 | Broader approved evidence and supported narrative/contradiction checks | Planned; typed SEC checks exist |
| R3 | Scoped FX/tax/corporate-action and portfolio accounting completion | Planned; USD simulation exists |
| R4 | Portfolio liquidity/stress enforcement and complete aggregate-risk acceptance | In progress; PR #32 projected-stress and persistent simulation commitment limits; market liquidity/full aggregate acceptance remain |
| E1 | Narrow paper executor with permits, price/quantity bounds and idempotency | Locked until prerequisites |
| E2 | Execution ambiguity, partial fills, cancellation and crash/restart recovery | Locked until E1 |
| O1 | Bounded scheduling, health/alerts and tested backup/restore | Planned |
| O2 | VM/authentication reliability, resource limits and operational reporting | Planned |
| O3 | Sustained paper evaluation, outcome learning and readiness review | Planned; requires elapsed observation |

Current planning count: **2/15 packages closed** after PR #26 merged, leaving
**13 delivery packages**. PR #27/#28 add a shadow permit foundation and temporary
identity/owner-control acceptance inside S3; they do not close S3 or reduce that
remaining count. PR #29 adds typed execution/fee observations inside D2 without
closing full D2 acceptance. PR #30 adds order-prefix/status visibility and diagnostic
integration, also without closing D2. PR #31 adds public state and three-view
cross-checks inside D3, without closing lifecycle/reservation acceptance.
PR #32 adds binding simulation stress and retained active-hold limits inside R4/D3,
without closing market-liquidity or actual monetary-reservation acceptance.
Updated estimate after PR #32: **13–18 further PRs**,
with 13 open delivery packages; this replaces the earlier 13-PR point estimate.
PR #26 was an additional
corrective PR inside S2: inactive one-shot services lost their systemd timestamps,
so retained successful completion state and stricter state checks were necessary.
S3 is split because funding/reconciliation and independent authorization inputs
are not yet accepted: PR #27 exercises the protocol without granting orders; its
remaining accepted-evidence integration and deployed identity acceptance stay open.
The correction, two S3 foundation slices and D2/D3 data foundations have consumed
nine PRs after #23 while closing two packages. At least one further PR per remaining
package projects 22 total after #23; allowing further integration/failure splits
gives about 22–27 total, beyond the original 12–18 range. The scope has not expanded;
the estimate underestimated implementation/acceptance splits. Report future changes
explicitly rather than count partial packages as complete.
Proceed with data acceptance before further signer deployment. Scope is unchanged. Boot/sustained recovery stay
in O2, and live advisory model gates stay in R1. Execution remains off.

Sequencing refinement on 5 November (no scope/count increase): remaining broker
receipt key migration is paired with D2/D3's broker-data schema integration. S2
delivers the SEC service boundary now; public-only broker evidence remains required
before full P5/executor acceptance. No key-isolation requirement is dropped.
The owner-facing overall progress estimate remains **approximately 45% (40–50%)**,
a subjective engineering guide rather than measured milestone completion or an
investment-readiness claim. Reassess it when material acceptance gates close.

Every PR handoff includes completed scope, validation evidence, remaining work,
blockers, the remaining delivery count and a labelled estimate/progress bar. Full
P1–P8 criteria remain in [remaining work](remaining-work.md). Real-money account,
eligibility, access and commissioning are a separate authorization/design phase.

## Engineering authorization

On 5 November the owner authorized routine NexyDAO PR uploads to the existing VM,
GitHub branch/PR publication, self-merging when checks pass and the change is
suitable, and continuation to the next development package. This preference
persists across these delivery steps. Before merging, verify the current head's
CI, applicable acceptance evidence, mergeability and blocking review state. This
engineering workflow does not itself grant broker execution or live-money access.

After reporting PR #25 merged, the owner explicitly authorized its previously
blocked root SEC installation. It created the scoped service identities, protected
paths, fresh collector key and UID guard. The bounded PR #26 state-retention repair
preserved that key/configuration and passed the complete operator audit. This is
not authorization for unrelated services or broker execution.

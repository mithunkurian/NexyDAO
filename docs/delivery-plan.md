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
| D3 | Broker cash/position lifecycle reconciliation, remaining broker key boundaries and actual monetary reservations | In progress; PR #31 public state/cross-checks and PR #35 fresh paired-delta diagnostics; interval attribution, lifecycle/reservations/deployment remain open |
| R1 | Remaining research/quote-backed advisory and paid revision acceptance | Planned; initial live paths exist |
| R2 | Broader approved evidence and supported narrative/contradiction checks | In progress. Verified SEC observations with conflicting values for the same issuer, metric, unit and reporting period stop advisory runs before model calls. Broader source coverage and narrative validation remain open. |
| R3 | Scoped FX/tax/corporate-action and portfolio accounting completion | Planned; USD simulation exists |
| R4 | Portfolio liquidity/stress enforcement and complete aggregate-risk acceptance | In progress; PR #32 stress/commitment limits, PR #33 immutable quote spread guard; executable depth/full-book liquidity and complete acceptance remain |
| E1 | Narrow paper executor with permits, price/quantity bounds and idempotency | Locked until prerequisites |
| E2 | Execution ambiguity, partial fills, cancellation and crash/restart recovery | Locked until E1 |
| O1 | Bounded scheduling, health/alerts and tested backup/restore | Accepted. The VM pilot reached its 24-attempt cap. All archives verified, the inspection restore and separate Gmail inbox test passed, and the timer was disabled after completion. |
| O2 | VM/authentication reliability, resource limits and operational reporting | In progress. The candidate pilot service and its resource limits passed an isolated Ubuntu test. Production cutover and boot acceptance remain open. |
| O3 | Sustained paper evaluation, outcome learning and readiness review | Planned; requires elapsed observation |

Current planning count: **3/15 packages accepted**, with **12 open** and no reliable
remaining PR count. S1 and S2 closed after PR #26. O1 closed after the bounded
pilot acceptance. PR #27/#28 add a shadow permit foundation and temporary
identity/owner-control acceptance inside S3; they do not close S3 or reduce that
remaining count. PR #29 adds typed execution/fee observations inside D2 without
closing full D2 acceptance. PR #30 adds order-prefix/status visibility and diagnostic
integration, also without closing D2. PR #31 adds public state and three-view
cross-checks inside D3, without closing lifecycle/reservation acceptance.
PR #32 adds binding simulation stress and retained active-hold limits inside R4/D3,
without closing market-liquidity or actual monetary-reservation acceptance.
PR #33 adds immutable quote/spread checks for prospective advisory risk, without
certifying executable depth or full-book liquidity. PR #34 adds opt-in market
public-key consumption and temporary role acceptance; production broker-key
deployment still remains open. PR #35 adds fresh paired state/execution delta
diagnostics without certifying interval attribution or closing D3. Updated estimate
after PR #39: **about 13 further PRs at minimum**,
with 13 open delivery packages; this replaces the earlier 13-PR point estimate.
PR #26 was an additional
corrective PR inside S2: inactive one-shot services lost their systemd timestamps,
so retained successful completion state and stricter state checks were necessary.
S3 is split because funding/reconciliation and independent authorization inputs
are not yet accepted: PR #27 exercises the protocol without granting orders; its
remaining accepted-evidence integration and deployed identity acceptance stay open.
The correction, two S3 foundation slices and D2/D3 data foundations have consumed
sixteen PRs after #23 while closing two packages. At least one further PR per remaining
package projects 29 total after #23, beyond the original 12–18 range. PR #39 consumes
the last split allowance from the previous 13–14 estimate without closing O1.
Thirteen remaining is now a baseline, with no contingency for further integration
or acceptance failures. The scope has not expanded;
the estimate underestimated implementation/acceptance splits. Report future changes
explicitly rather than count partial packages as complete.
Proceed with data acceptance before further signer deployment. Scope is unchanged. Boot/sustained recovery stay
in O2, and live advisory model gates stay in R1. Execution remains off.
While broker acceptance remains blocked, PR #36 advances O1's independent backup
and isolated restore work; PR #37 adds health and local alert diagnostics. Neither
enables a timer, notification delivery or recurring automation.
PR #38 adds finite maintenance-only scheduling ticks with durable claims and caps;
no daemon/timer, paid advisory scheduling or production activation is enabled.
PR #39 adds the owner's selected Gmail alert path with mocked SMTP validation.
Private credential provisioning, live delivery and activation remain separate.

Sequencing refinement on 5 November (no scope/count increase): remaining broker
receipt key migration is paired with D2/D3's broker-data schema integration. S2
delivers the SEC service boundary now; public-only broker evidence remains required
before full P5/executor acceptance. No key-isolation requirement is dropped.
Use accepted packages and specific remaining gates for owner-facing progress.
The earlier percentage and PR-count estimates are historical planning figures.

Every PR handoff includes completed scope, validation evidence, remaining work,
blockers and the accepted and open package counts. Full
P1–P8 criteria remain in [remaining work](remaining-work.md). Real-money account,
eligibility, access and commissioning are a separate authorization/design phase.

## Engineering authorization

On 5 November the owner authorized routine NexyDAO PR uploads to the existing VM,
GitHub branch/PR publication, self-merging when checks pass and the change is
suitable, and continuation to the next development package. This preference
persists across these delivery steps. Before merging, verify the current head's
CI, applicable acceptance evidence, mergeability and blocking review state. This
engineering workflow does not itself grant broker execution or live-money access.

The owner subsequently directed development to continue automatically after each
successful merge, without asking to start the next stage. Continue independent
authorized work and pause only for a necessary decision or external prerequisite.
At the end of each PR, report what shipped, verification results, the estimated
overall progress, packages complete and remaining, and the current estimate of
PRs left. Label estimates separately from verified completion.

After reporting PR #25 merged, the owner explicitly authorized its previously
blocked root SEC installation. It created the scoped service identities, protected
paths, fresh collector key and UID guard. The bounded PR #26 state-retention repair
preserved that key/configuration and passed the complete operator audit. This is
not authorization for unrelated services or broker execution.

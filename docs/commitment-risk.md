# Simulation commitment limits and projected stress enforcement

PR #32 makes two existing simulation safeguards binding on new risk: retained
allocation/fee-buffer limits for active holds, and a projected stress drawdown
check. It does not reserve broker money, authorize trades or complete R4/D3.

## Retained active-hold limits

Previously, a hold was checked against the allocation cap/fee buffer at creation,
but that context was not stored. For example, two $475 holds with a $50 buffer
leave the $4,000 cash floor exactly covered. A later $0.01 API estimate could let
a fill pass the ordinary cash floor while consuming that buffer. The new check
rejects that deployment and keeps holds, cash, positions and revision unchanged.

Each new hold now stores a separate `simulation_reservation_limits` record binding
its reservation ID, request digest, allocation cap, fee buffer and risk-model
version. Contexts are bounded, schema/hash checked and linked to the reservation;
malformed, duplicate-key, unknown-version or orphan records stop replay. The local
hash is an integrity check, not administrator-resistant evidence or a signed permit.

Snapshot summaries combine all active contexts exactly: the minimum of
`capital cap - fee buffer` bounds exposure/holds/API estimates, and the maximum
fee buffer protects settled available cash above the owner floor. Taking the
minimum cap and maximum buffer as a new pair would over-tighten some valid
combinations; this implementation preserves each original inequality.

Every new simulated buy, advisory allocation check and reservation considers the
active contexts. A different default configuration cannot relax an earlier active
hold. Reusing an active ID with changed limits is rejected rather than rewriting
its context. Closed requests remain history and idempotent; new plans must pass
current rules. New fills recheck current API estimates, cash and existing holdings
inside the ledger's write transaction. All other holds and unspent notional/fee
remainders continue to count. Retry of an identical already-recorded fill adds no
debit. Explicit releases remain possible and do not touch broker funds.

Legacy holds without saved contexts remain fully encumbered. Snapshot summaries
mark their limits incomplete; neither new risk nor deployment invents an old cap
or buffer. The operator may explicitly release/replan a legacy hold after reviewing
its existing simulation history. No auto-release, expiry, cash reset or replacement
of the real cost database occurs. Creating the new table does not populate missing
legacy contexts. Corrupt audit evidence still requires review before release.

## Projected stress guard

The version-1 guard uses the existing report's 50% simultaneous-price-decline
scenario and the existing 10% drawdown limit. For fresh-marked USD simulation
holdings, it considers current net equity/observed peak, current marked holdings,
fully deployed pending notional, proposed notional and full pending/proposed fees.
API estimates/reservations already deducted from equity are not deducted twice.
Projected loss rounds upward to the ledger's $0.00000001 quantum. Reaching or
exceeding 10% blocks incremental risk, even if current drawdown is below 10%.
The fixed model limit cannot be relaxed by altering a diagnostic report field.

This is a conservative scenario constraint, not a probability, return forecast,
liquidation guarantee or trading signal. Missing/expired held-position marks stop
new risk. Known fill/reservation fees are charged fully in the projection;
advisory allocation inputs without separately known fees still need independent
fee acceptance. Hold-to-position conversion credits only the validated fill's
notional and fee portions, preventing double stress counting while preserving
unused budgets. Sells/reductions and explicit releases are not blocked by this
new-risk stress test. Reports do not force liquidation or mutate limits/positions.

## Acceptance and remaining gates

Thirteen new tests cover stress before actual drawdown breach, boundary rounding,
full fee treatment, report-field non-relaxation, restart/API-cost erosion of the
buffer, active cap retention across raw/reserved buys and different defaults,
idempotent-ID changes, partial-fill budget conversion, legacy-context migration,
corrupt/orphan profiles, missing main tables with surviving audit evidence, exact
combined envelopes, concurrent cap enforcement and continued position reductions.
Windows: 362 tests run, 356 passed and six Unix-only
skips. Final implementation `83e9f0a` passed all 362 Ubuntu tests in isolated
release `releases/commitment-risk-83e9f0a`, including all 13 new acceptance tests.
Exact tested archive SHA-256:
`f96048e3d96c4937679783a38993687652268a350b17bed1022741336cd58691`.

All fills, holds, marks and API estimates in these tests are synthetic and use
separate temporary databases/keys. No paid calls, actual account/history query,
broker operation, production database/key or deployed service is changed.
R4 still needs market liquidity/price-impact evidence and complete aggregate-risk
acceptance; D3 still needs actual monetary reservations/lifecycle reconstruction.
Foreign-currency, tax and corporate-action accounting, broker coverage, protected
authorization and execution remain open gates. Existing broker reservation and
execution methods remain disabled.

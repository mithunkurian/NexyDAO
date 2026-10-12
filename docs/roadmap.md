# Development roadmap

See the [milestone register](milestones.md) for delivered checkpoints, validation
evidence and open acceptance gates. Current marker: M2A, read-only paper connectivity.
The [development tracker](development-tracker.md) records current tasks and next checks.

## 1 — Auditable deliberation (this PR)

Architecture, hierarchy, review workflow, real CEO/committee Responses API adapter,
two risk officers, strict records, SQLite memory, costs, execution denial, offline
tests/CI and small-VM instructions. Acceptance: persistence survives restart; budget
reservations work across connections; malformed/refused/incomplete outputs fail closed;
unknown evidence fails; veto/quorum checks hold; live mode and enabling execution fail;
even unanimous approval cannot send orders. A real six-call API cycle on the VM has
validated model access, memory and costs; offline tests require no credentials.

## 2 — Verified evidence and research

The first read-only account probe is implemented in `broker-check` (see
`ibkr-paper.md`): bounded account lookup/summary, local private snapshots, account
namespace/pin checks and offline safety tests. The quote adapter now implements
unique contract resolution, signed receipts and freshness enforcement; a fresh live
quote and its six-role AI consumption passed on 2026-10-12. The initial SEC research
adapter and two-agent workflow are implemented with offline tests; live acceptance,
broader source verification and broker/executor OS isolation remain unfinished.
See [research scope and operation](research.md).

Read-only IBKR paper data adapter and approved public-source adapters. Verify paper
account identity rather than assuming it from port. Record contract IDs, bid/ask,
currency, observation/retrieval times, raw content hashes, provenance and expiry.
Research agents discover opportunities; separate verification checks retrieval,
freshness, contradictions and claim support. Test fabricated citations, spoofing,
SSRF, prompt injection, market closures and unavailable data.

## 3 — Portfolio Manager and accounting

Add simulated positions, fills, cash, FX, fees and mark-to-market reconciliation.
Portfolio Manager proposes thesis-driven allocations and alternatives. CEO sets mandate
and accepts/revises strategy, plans operating budgets, and oversees performance and
costs; routine owner approval is not required. Revisions require fresh reviews. Independently enforce
aggregate exposure, concentration, cash reserve, drawdown and stress loss limits.
Evaluate diverse regimes and report net costs and performance against the objective.
No indicator-based order rules.

## 4 — Authorization and tested paper execution

Separate executor OS identity from agents. Executor alone gets broker connectivity.
Independently validated, versioned policies and short-lived signed permits bind account, proposal
hash, contract, quantity, limit price, expiry and unique nonce. Enforce kill switch,
fresh verified evidence, exposure reservation, idempotency and reconciliation.
Agent votes alone never mint permits. Test forged/stale/replayed permits, network
ambiguity, duplicates, partial fills, account mismatch, restarts and concurrent orders.
Security review and authorization acceptance checks precede narrowly authorized paper
orders. The owner grants or revokes broker/service access and can intervene; the CEO owns
routine business policy and investment decisions within independently enforced limits.
Execution remains disabled until all authorization acceptance checks pass.

## 5 — Autonomous paper operations

Bounded scheduled cycles, human alerts, evidence refresh, failure recovery, outcome
learning and independent audit. Sustained shadow/paper evaluation and cost reporting
precede broader scope. Real-money execution requires a separate design, review and
explicit authorization and is outside this roadmap.

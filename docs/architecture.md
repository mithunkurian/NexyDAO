# Architecture and decision workflow

NexyDAO has $5,000 simulated initial capital and a 15% annual net return objective,
never a guarantee. Milestone 1 leaves capital unchanged and sends no orders.
AI formulates theses; deterministic code enforces permissions and loss limits.
These safeguards are not trading signals or buy/sell strategies.

## Agent hierarchy

| Role | Responsibility and authority | Milestone |
|---|---|---|
| Human owner | Invests capital, controls access, sets binding constraints above all agents, intervenes when needed | All |
| AI CEO | Mandate, strategy, operating budgets, performance oversight and investment/research proposals | 1; fuller operations 3–5 |
| Research agents: opportunity, countercase | Independent ideas/challenges from typed filing facts; no direct source/network authority | Initial slice 2; eight-call live workflow validated |
| Portfolio Manager | Allocation proposals, alternatives, aggregate exposures | 3 |
| Risk Officer: capital | Independent loss, sizing and liquidity challenges | 1 |
| Risk Officer: evidence | Independent provenance and security challenges | 1 |
| Committee: investment, fiduciary, audit | Three independent advisory votes | 1 |
| Policy/execution service | Enforces permits, account restrictions and loss limits | Denial stub 1; complete 4 |
| Auditor | Outcomes and independent tamper-evident audit | SQLite 1; external 4 |

Risk officers cannot be overruled by the CEO. Each receives the proposal in a fresh
API call without the other officer's response. Committee members receive both reviews
but not one another's votes. Calls to the same model may share errors and biases;
logical separation does not establish statistical independence.

## Owner and CEO responsibilities

The owner's investment role means supplying capital to the company. Routine portfolio
investment decisions belong to the CEO and pass through independent risk and committee
review. The owner invests capital, grants/revokes access
(including credentials and service permissions), and intervene or stop operations when
needed. The owner can additionally set binding constraints that supersede every agent,
including the CEO. Routine strategy, budget planning and performance review still do
not require owner approval. See `owner-policy.md` for mandatory rules and extension.

The CEO owns the investment mandate, strategy, acceptable operating risk within the
enforced envelope, investment universe, operating budget planning, performance and cost
oversight, and coordination of research and portfolio work. The $5,000 simulated starting
capital and 15% annual net objective remain the initial company brief. The CEO must
account for uncertainty and may recommend changes through the review workflow.

CEO responsibility does not grant authority to change enforced capital limits, spending
ceilings, credentials, broker permissions, or execution locks. Business policy proposals
must satisfy independent validation before a future policy service adopts them; agents
cannot modify that service. The owner controls access and may intervene, without becoming
a routine investment approver. In milestone 1 the CEO expresses its responsibilities in
decision rationale; budget management and performance accounting are not yet implemented.

## Decision workflow

1. Controller verifies signed quote/SEC receipts or labels manual input unverified, and loads three recent completed records.
   Opt-in research runs two independent reports first; application code checks numeric claim bindings.
2. CEO proposes a decision, rationale, risks, citations and invalidation conditions.
3. Two risk officers independently pass, challenge or veto.
4. Three committee members independently approve, revise or reject.
5. Policy checks both risk passes, two-of-three committee approval, proposal sizing
   and cash reserve, then always denies execution in milestone 1.
6. SQLite records inputs, every stage, final status, schema/prompt versions, model,
   configured token rates, usage and estimated API cost. Demo runs are excluded from AI memory.

Failures terminate a cycle; partial decisions never become authorized. There is no
automatic resubmission loop. Future CEO revisions create linked new proposals and
repeat all reviews. Abstaining or asking for research is a valid outcome.

## Modules and boundaries

- `config`: immutable environment configuration; rejects live mode and execution flags.
- `provider`: fixed HTTPS Responses endpoint, no tools, no implicit retries.
- `records`: strict schema and local validation, including known citation IDs.
- `workflow`: sequential calls, bounded context and distinct role prompts.
- `store`: SQLite WAL audit, bounded memory, transactional lifetime budget reservations.
- `safety`: static capital envelope and unconditional execution denial.
- `cli`: offline demo fixture, real AI deliberation, cost inspection.
- `ibkr` / `market`: bounded read-only paper snapshots/quotes, local integrity and freshness checks.
- `sec`: fixed public filing endpoints, typed source observations and signed receipts.
- `research`: two independent reports, strict schemas and application-enforced numeric bindings.
- `owner_policy`: protected, versioned owner constraints, immutable cycle snapshot and independent cash/short/leverage preflight denial.

Models receive serialized data only. They have no credentials, shell, database,
filesystem or broker tools. An injected instruction may influence prose but cannot
open a broker socket or change policy. The controller owns the API key in process
memory; isolate its OS account. Local SQLite is durable, not tamper-proof against an
OS administrator. Separate executor identity and external audit are future work.

## Evidence and capital

Manual snapshots are unverified. Signed quote/SEC observations have narrowly scoped
source/integrity/freshness checks; researchers' structured numeric claims must match
typed facts. Prose, interpretations and forecasts remain unverified. See `research.md`.
An investment proposal always fails the evidence gate, even with unanimous approval.
No browser tools are enabled. Empty evidence should lead AI to hold or request research.
The offline demo is a labeled plumbing fixture, never an investment strategy.

The account view is empty simulated cash, not the IBKR balance. Illustrative safeguards
cap proposals at $500 and require $4,000 remaining cash. These must be revisited with
aggregate portfolio accounting before execution. No performance result is claimed.
Future net return accounting deducts broker fees, slippage and AI costs from marked equity.

## Costs, failure handling and limitations

API costs are separate from simulated capital. Configure positive rates for the selected
model. Cached input is conservatively estimated at the full input rate. Before each
call, SQLite atomically reserves a conservative UTF-8 byte bound for text input plus
4,096 tokens of overhead and the output cap. Reported usage settles the estimate.
Failures, missing usage and crashes retain reservations because billing is uncertain.
Usage exceeding the bound is recorded and stops the cycle for operator review.
This is an estimated local guard, not an authoritative billing cap; use independent
provider project controls too. Budget is lifetime per database and never resets itself.
Do not delete history to replenish budget. Reconcile unsettled costs against provider
billing before any operator adjustment.

A process crash may leave a run `running`; it is excluded from memory and never resumed
or executed. Review abandoned runs operationally. Audit history grows on disk; memory
sent to models is bounded. PaperBroker remains an execution-denial stub. Operator
commands have narrowly scoped read-only socket/source access; agents do not have
broker tools or order submission capability. The separate executor is future work.

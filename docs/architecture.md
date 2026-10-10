# Architecture and decision workflow

NexyDAO has $5,000 simulated initial capital and a 15% annual net return objective,
never a guarantee. Milestone 1 leaves capital unchanged and sends no orders.
AI formulates theses; deterministic code enforces permissions and loss limits.
These safeguards are not trading signals or buy/sell strategies.

## Agent hierarchy

| Role | Responsibility and authority | Milestone |
|---|---|---|
| Human owner | Mandate and approval of future execution policy releases | All |
| AI CEO | Strategy and investment/research proposals | 1 |
| Research agents | Opportunity discovery and source collection | 2 |
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

## Decision workflow

1. Controller loads bounded operator snapshots and three recent completed records.
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

Models receive serialized data only. They have no credentials, shell, database,
filesystem or broker tools. An injected instruction may influence prose but cannot
open a broker socket or change policy. The controller owns the API key in process
memory; isolate its OS account. Local SQLite is durable, not tamper-proof against an
OS administrator. Separate executor identity and external audit are future work.

## Evidence and capital

Snapshots are always unverified. URLs, timestamps and summaries are operator assertions;
the application does not retrieve sources or establish freshness and claim support.
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
sent to models is bounded. PaperBroker is a denial stub, not an IBKR adapter. No broker
credentials, socket calls or order submission capabilities exist in this milestone.

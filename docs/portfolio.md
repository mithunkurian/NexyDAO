# Portfolio Manager and USD simulation ledger

`portfolio` adds an AI Portfolio Manager before the CEO, two Risk Officers and three
committee voters: seven calls. `portfolio --with-research` adds the two researchers
first for nine calls. All roles receive the binding owner policy. The manager reasons
about incremental allocations, alternatives, aggregate holdings and uncertainty; no
indicator or hardcoded trading strategy creates decisions. CEO and independent review
remain necessary. Proposals never change positions or issue orders.

## Accounting scope

The persistent SQLite database seeds **$5,000 simulated USD cash exactly once**.
It tracks settled/unsettled cash, long stock quantities, fee-inclusive cost basis,
partial-sale realized P&L, fees, verified bid marks and a ledger revision. Each fill
is explicitly an operator-supplied **simulation fixture**, not an investment decision
or actual broker fill. No broker position/balance is imported. API estimates/reserves
from the existing lifetime cost ledger reduce available funding and reported net equity.
They are not an authoritative invoice or a broker cash debit.

USD monetary bookkeeping uses eight decimal places, conservatively rounding purchase
debits up and sale receipts down. Partial cost-basis removal rounds down; the final
sale removes the complete residual basis. Unique fill IDs prevent double counting;
conflicting retries fail. Atomic `BEGIN IMMEDIATE` updates serialize concurrent funding
checks. Reports use a consistent SQLite read transaction. Internal reconciliation replays
fills/settlement flags and rejects changed cash, positions, basis, fees or proceeds;
it is not broker reconciliation or protection against an administrator rewriting history.

Sale receipts are quarantined as unsettled cash until an explicit simulation settlement
step. No broker/calendar settlement timetable is assumed. This is a workflow for testing
accounting, not permission to spend actual unsettled proceeds. Unknown currency/FX,
CFDs, shorts and non-stock fixture types fail.

The `STK` wire classification is not proof that a product is unleveraged or ISK-eligible.
Actual instrument eligibility must be independently verified by the future executor;
current proposals/fixtures cannot authorize that exposure or certify eligibility.

Contributions, withdrawals, corporate actions, dividends, taxes, broker settlement calendars, FIFO/tax lots and FX accounting
are **not yet implemented**. Weighted-average basis is only a simulation accounting
choice, not an ISK tax calculation. Full M3 acceptance remains broader than this slice.

## Independent constraints

Application code checks incremental exposure against existing holdings, using the
larger of cost basis and fresh market value. Owner position/cash limits apply; default
maximum position is $500 and minimum cash reserve $4,000. Aggregate exposure is capped
at $1,000. Purchases stop at 10% drawdown from observed net-equity peaks. These are risk
constraints, not trading signals; they never generate a sell or authorize execution.
Fees and recorded API expenses/reserves count against funding. Unknown valuations
block new simulated buys/allocations. Sells can reduce owned quantity but cannot short.
Additional owner rules lacking independent enforcement keep investment denial in place.

Marks require a signed, fresh paper BidAsk receipt and bind the position's contract ID.
Changing contract identity fails. Expired/missing marks produce unknown valuation, not
an invented price. The observed peak is sampled at complete fresh marking events, not
an intraday high. Price appreciation can breach limits; the system reports/blocks new
risk and does not silently rebalance. The 15% annual net target remains an objective;
annual return is never extrapolated from a short trial. Net reports omit unimplemented
tax/FX costs and explicitly show incomplete models. Historical API expenses are included.

The manager must cite a fresh quote for each proposed allocation, reconcile its cash
target and satisfy current limits. Without quotes its schema requires abstention.
Research conclusions remain unverified. All models have no ledger/broker mutation tools.
Portfolio revision or owner-policy changes during review stop the cycle. Legal/ISK,
executor, permits and full research eligibility remain unresolved; execution is always
denied even after unanimous approval.

## Commands

Use the existing persistent `NEXYDAO_DB`. No extra runtime dependencies are needed.
No command resets the $5,000 capital or cost budget.

```bash
python3 -m nexydao portfolio-report
# Existing local API key/rates, owner policy and signed receipts apply:
python3 -m nexydao portfolio --research-evidence /private/sec-research.json
# Nine calls; collect short-lived quotes in a later separate cycle:
python3 -m nexydao portfolio --with-research --research-evidence /private/sec-research.json
# Seven calls with a fresh signed quote and optional signed filing evidence:
python3 -m nexydao portfolio --market-evidence /private/market-quote.json --research-evidence /private/sec-research.json
```

For explicit accounting fixture tests, prefer an isolated test database (never erase
the real persistent database). A bounded JSON file has exactly these fields:

```json
{"id":"fixture-buy-1","side":"buy","symbol":"TEST","quantity":"2","price":"100","fee":"1","currency":"USD","asset_type":"STK"}
```

```bash
python3 -m nexydao sim-fill --fill /path/to/fixture.json
# A separate sell fixture must reference only owned quantity:
python3 -m nexydao sim-settle --settlement-id fixture-sell-1
python3 -m nexydao portfolio-mark --market-evidence /private/market-quote.json
python3 -m nexydao portfolio-report
```

`sim-settle` requires the sale's fill ID, is idempotent and does not connect to a broker.
`portfolio-mark` requires configured `NEXYDAO_EVIDENCE_KEY_FILE`, exact paper-account
pin and matching `NEXYDAO_MARKET_SYMBOL`. Owner policy applies to all commands.
After a policy change, previously recorded fixtures remain history; new funding checks
use the new constraints. No live ISK account or access change is performed.

## Validation and deployment

Run `python3 -m unittest discover -s tests -v` and the offline demo. Tests cover persistent
initialization, rounding/basis/fees, settlement, idempotency, concurrent transactions,
marks/contracts/expiry, drawdown, internal reconciliation, changing state and seven/nine
call non-mutating workflows. Fixtures are not verified investment performance.
Deploy to an isolated release on the VM first, preserving credentials, owner policy,
source keys and the existing API cost database. Validate one paid Portfolio Manager
cycle and retain call/cost/memory results before marking operational acceptance.

On 2026-10-12, implementation `4398122` passed 92 tests locally/VM/CI and a paid
seven-call manager cycle with signed SEC observations. No quote was supplied, so
the manager abstained from allocations and the CEO investigated. Accounting state
did not change; funds, memory and internal reconciliation persisted. This validates
the abstention/review path, not a live quote-backed allocation or broker-fill process.

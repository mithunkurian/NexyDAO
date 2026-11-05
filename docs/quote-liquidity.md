# Quote-backed spread guard: partial liquidity screening

PR #33 adds a fixed spread screen to Portfolio Manager allocation checks and the
final CEO proposal's independent policy evaluation. It preserves the execution
lock and does not establish executable depth or full portfolio liquidity.

## Binding screen and frozen evidence

Each proposed investment symbol needs a cited fresh authenticated quote. Relative
spread `(ask - bid) / bid` must be at most 1% (100 basis points), a fixed version-1
conservative engineering guard, not a broker rule, trading signal or forecast.
Comparison uses decimal products rather than rounded ratios; the displayed ratio
rounds upward. Locked bid/ask prices can pass; crossed or flagged quotes cannot.

All available verified quotes for the proposed symbol apply, preventing selection
of only a tighter observation. Different contract IDs are ambiguous; an existing
position's contract must match. Missing/manual/unrelated citations do not support
the screen. Passing it creates neither a monetary reservation nor an order permit.

A frozen canonical byte snapshot captures trusted application quote views before
model calls. Freshness, contract/source URL, numeric/timestamp types, outer expiry
and normalized observation time are checked independently. Rechecks follow PM
reasoning, precede subsequent roles, guard final policy and precede cycle completion.
Semantic quote changes, removal, expiry swapping or changed trust labels stop the
cycle. Expiry after the last vote still prevents completion. Context/report edits
cannot raise the fixed threshold. There is no forced sale or automatic re-query.

This snapshot does not authenticate arbitrary evidence labels. Callers must use
application receipt loaders; manual evidence files cannot set `verified_quote`.
The existing HMAC market loader now rejects duplicate JSON fields/nonstandard
constants. Existing signed schema-1 quotes still load; their sanitized views add
`received_at` for independent freshness checks. Historical memory stays unverified.

## Why size is not a share-capacity limit

IBKR documents share-size and older compatibility behaviour in its
[streaming-data size notes](https://interactivebrokers.github.io/tws-api/market_data.html).
Its [tick-by-tick API](https://www.interactivebrokers.com/docs/tws-api/doc/md/live-ticks)
returns bid/ask size observations and flags. The receipt does not independently
attest active size-unit settings, executable depth, queue priority, persistence
of displayed size, fill probability or price impact. No assumed lot multiplier,
share-capacity limit or guaranteed size-times-price liquidity is inferred.

Reports always retain `size_units_verified`, `executable_depth_verified`,
`portfolio_exit_capacity_verified`, `market_liquidity_verified` and
`execution_authorized` as false. A narrow spread is one necessary screen on an
incremental advisory proposal. It cannot certify liquidation of the entire book,
pending holds, fees, stress liquidity or instrument/account eligibility. Full R4,
funding, protected authorization and broker execution remain open.

## Operator use

```bash
python3 -m nexydao quote-liquidity-report --market-evidence /private/signed-quote.json
```

This authenticates an existing quote with the exact account/symbol and protected
receipt key or public-key pin, then reports the partial screen. No application DB, provider, socket or
collector is invoked. PR #34 adds [optional public-key consumption](public-market-quotes.md)
through explicit market receipt mode selection. Normal advisory
workflows include the report and independently enforce it despite model prose or
positive votes. Empty plans/holds can remain valid when no new allocation passes.

## Acceptance and remaining gates

Fifteen new tests cover exact boundaries, locked quotes, unknown-depth scope,
references, conservative multiple-quote handling, contract identity, immutable/
mutated/expired observations, duplicate JSON, authenticated DB/provider/socket-free
reporting, PM early rejection, final policy despite positive votes, narrow advisory
cycles and expiry after the last vote. The between-call expiry fixture now advances
time at the first model return rather than counting clock reads; it still requires
only one role call. Windows: 377 tests run, 371 passed and six Unix-only skips.
Implementation `1796f81` passed all 377 Ubuntu tests in isolated release
`releases/quote-liquidity-1796f81`, including all 15 new spread/integrity tests.
Exact tested source archive SHA-256:
`aa34e70ada60ac56f93a7501192a10797cbc11a1d50d490e6840702caf3de512`.

All inputs use synthetic quotes/providers and temporary keys/databases. No owner
account/history query, subscription, paid call, deployed service or production data
is changed. Size-unit/venue/depth/price-impact acceptance, full-book exit liquidity,
market-key separation and real broker/funding/authorizer gates remain unresolved.

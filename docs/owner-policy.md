# Binding owner policy

The owner can set binding constraints in addition to providing capital, controlling
access and intervening. These constraints take precedence over the CEO, researchers,
Risk Officers, committee votes, memory and source material. Agents cannot edit policy.
Routine business decisions still belong to the CEO within the enforced envelope.
Owner instructions cannot authorize illegal conduct or bypass execution safeguards.

## Mandatory rules

1. No short selling. Future sales may only reduce verified owned long positions.
2. No leverage or borrowing. Purchases must be funded by available settled cash,
   including costs, in the relevant currency. Leveraged/inverse exposure is rejected
   conservatively; use of broker BuyingPower is not evidence of unborrowed cash.
3. Applicable US and Swedish legal requirements must be respected, including relevant
   cross-border/EU, broker, tax and instrument requirements. Agents cannot certify this.
4. Any future live execution must use an independently verified **Swedish ISK account**
   and comply with account and instrument eligibility requirements. No fallback to a
   general/margin account is permitted. Paper DU identity does not establish ISK status.

These are hard constraints, not trading signals. Current execution remains denied for
every proposal. Investment proposals also receive explicit unresolved legal/ISK reasons.
`cash_preflight` independently rejects oversized sells, borrowed/leverage exposure and
unfunded/cross-currency purchases; it is a pure precursor to future simulated accounting,
not an executor or permit issuer. Its inputs must ultimately come from verified state,
not agent declarations. It never authorizes execution, even when arithmetic checks pass.

## Adding rules

Copy [the template](../examples/owner-policy.json) into a protected location outside the
checkout, edit it as the owner, increment `policy_version`, then configure the file:

```bash
umask 077
mkdir -p "$HOME/.local/share/nexydao"
# Copy once; do not overwrite an existing owner policy:
cp -n examples/owner-policy.json "$HOME/.local/share/nexydao/owner-policy.json"
chmod 600 "$HOME/.local/share/nexydao/owner-policy.json"
export NEXYDAO_OWNER_POLICY_FILE="$HOME/.local/share/nexydao/owner-policy.json"
python3 -m nexydao owner-policy
```

Use a root/owner-managed, service-read-only file in hardened deployment; on Windows
provision owner-only write ACLs. Unix group/world writes are rejected. Model prompts
are not OS access controls; collector/executor separation remains a future gate.

Supported additions: `blocked_symbols`, a tighter `max_position_usd`, and a higher
`min_cash_reserve_usd` within the current $5,000 simulated envelope. These constraints
are checked by application code independently of votes. Rules requiring new checks
can be added as `additional_rules`, for example:

```json
[{"id":"exclude-tobacco","text":"Do not invest in tobacco businesses."}]
```

The rule reaches every agent but its industry classification is not implemented.
Any such additional rule adds an enforcement-pending investment denial. A prompt
promise is insufficient: implement and test a corresponding independent check before
that gate could be cleared. Free text is never evaluated as Python, shell or a URL.
These additions cannot relax the mandatory four rules or existing capital safeguards.

Absent configuration uses the mandatory built-in policy. A configured missing,
malformed, oversized or weakened policy fails before paid calls/database creation.
Immutable canonical bytes define the active policy; copies supplied to agents cannot
modify it. Each cycle records the full policy, version and SHA256. The file is rechecked
before each role call and before completion; a mid-cycle change stops further work.
Restart a fresh cycle after a policy change so all reviews use the same version.
Hash/version records identify policy; they are not cryptographic owner identity,
external tamper-proof audit or protection against a compromised administrator.

## Legal and ISK acceptance still required

No algorithm here determines universal legal compliance. Independent current legal,
tax, broker-account and instrument checks must be designed and tested before future
execution, with uncertainty causing denial. The system must also respect stricter
applicable rules rather than assuming only two countries' named laws matter.

[Skatteverket's permitted-assets guidance](https://www.skatteverket.se/privat/sjalvservice/svarpavanligafragor/investeringssparkonto/investeringssparkonto/vilkatillgangarkanjagsparaipainvesteringssparkontot.5.71004e4c133e23bf6db80001119.html)
describes eligible asset categories; it does not certify a particular account/instrument.
[IBKR announced Swedish ISK availability](https://investors.interactivebrokers.com/en/general/about/mediaRelations/10-6-25.php)
in September 2025. Your existing account type/API access and individual eligibility
have not been verified. Do not label an ordinary account ISK through configuration.
[SEC margin guidance](https://www.sec.gov/about/reports-publications/investorpubsmarginhtm)
describes borrowing mechanics; the owner prohibits them regardless of broker permissions.

No live account login, account conversion, funding or order execution is performed
by this milestone. Read-only paper/source trials remain available under owner policy.

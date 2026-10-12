# SEC research milestone

Two research agents produce independent opportunity and countercase reports from
bounded SEC filing observations. Reports go to the existing CEO, two Risk Officers
and three committee voters: **eight sequential OpenAI calls** for `research`, six for
ordinary `deliberate`. Both use the existing persistent cost ledger and lifetime budget.
No buy/sell indicators, automatic allocations or order commands are introduced.

## Scope and trust

The collector reads fixed HTTPS paths on `data.sec.gov`: issuer submissions and
US-GAAP `Assets` / `NetIncomeLoss` company concepts for one to three configured issuers.
It validates ticker-to-CIK association, taxonomy, concept, USD units, form, accession
and period dates. These concepts are a small source interface, not an investment
strategy. Agents reason within this universe; they cannot submit URLs or expand access.

The selected observation has the latest period end, then filing date, then duration
start; equal-context observations with differing values fail. Reporting periods are
retained, so a duration is not silently called a quarter. Filing age is at most 180
days and its period end at most 550 days before filing. Signed receipts expire after
24 hours; retrieval does not renew old filings' eligibility.

Only typed observations enter model context. Source names, labels, descriptions, HTML
and arbitrary prose are excluded. SHA256 digests record retrieved bytes. Local HMAC
integrity is not an SEC signature, an external audit or independent economic truth.

Researchers receive the same facts and prior memory, without each other's report.
Every candidate requires known evidence IDs, a matching issuer and exact numeric value
bindings. Fabricated structured claims stop before the CEO; incurred costs remain
recorded. Reports retain `thesis_verification: unverified`: prose, forecasts, valuation,
interpretations and extrapolated numbers are **not** certified. Risk and committee
review challenge conclusions; prior memory remains unverified. Agents may abstain.

This is a first research slice, not all of M2B. News, narrative claim verification,
cross-publisher corroboration, broader discovery, portfolio accounting and executor
isolation remain future work. Execution is always denied regardless of model approval.

## Access and bounds

The [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
describes public submissions/XBRL endpoints; no SEC login or API key is needed.
The [SEC bot guidance](https://www.sec.gov/about/webmaster-frequently-asked-questions)
asks callers to declare a User-Agent and shows a company/contact example. Configure
a real operator contact locally: the SEC receives it in HTTP headers. It is excluded
from agent context, logs and Git. This creates no account and sends no email.
Do not use a fictional contact for live testing.

Requests are serial with 0.5-second spacing: three per issuer, at most nine per check.
Avoid concurrent collectors; the process limit does not coordinate multiple machines.
All DNS answers must be public. The connection pins a resolved IP and TLS verifies the
fixed hostname. Proxies, redirects, custom taxonomies and compressed/non-JSON bodies
are rejected. Limits: 1 MB/source, 5,000 unit facts and 64 KB/receipt. Connection/socket
operations have 15-second timeouts; streamed reads share a 15-second deadline. OS DNS
resolver timeouts still apply. A 180-second collection budget is checked between
requests and before publication. No retries or fabricated fallback occur. Failures
preserve the prior receipt, whose freshness is checked before use.

## Installation and operation

Python 3.12, no new dependencies. Reuse the private 32-byte key from
[market setup](market-evidence.md), or provision a separate private research key.
Never commit keys or receipts. Unix key permissions are checked; provision Windows
owner-only ACLs separately. Supply these settings in process environment; the app
does not execute `.env` scripts. Microsoft is an issuer-mapping example, not a buy idea:

```bash
export NEXYDAO_RESEARCH_UNIVERSE='[{"symbol":"MSFT","cik":"0000789019"}]'
# Provision NEXYDAO_SEC_USER_AGENT as NexyDAO/version plus your real contact locally.
# Set NEXYDAO_EVIDENCE_KEY_FILE to the private key path.
export NEXYDAO_RESEARCH_SNAPSHOT="$HOME/.local/share/nexydao/sec-research.json"
python3 -m nexydao source-check
# Existing local OpenAI credentials, positive rates and persistent NEXYDAO_DB apply:
python3 -m nexydao research --research-evidence "$NEXYDAO_RESEARCH_SNAPSHOT"
python3 -m nexydao costs
```

Issuer/source settings are access boundaries controlled outside agents. Research and
investment judgment remains with the CEO and agents; scope proposals do not directly
change the collector. Never delete the cost database to replenish its budget.

`research` rejects `--market-evidence` so two extra calls do not consume quote validity.
Research first, then collect a quote and use `deliberate --market-evidence PATH
--research-evidence PATH`. Completed research is available in bounded AI memory.
That second cycle has six calls and cannot execute. Manual `--evidence` stays unverified.

## Acceptance and deployment

Run `python3 -m unittest discover -s tests -v` and the ordinary offline demo. Fixtures
and mocked HTTP/OpenAI do not establish real retrieval or paid eight-call acceptance.
Tests cover DNS/SSRF, redirects, source identity/body limits, contradictions, signatures,
expiry, fabricated claims, independent contexts, persistence, costs and execution denial.

Use an isolated trial release as in [VM deployment](deployment.md). Preserve existing
database, keys and credentials. Validate one real signed receipt, then one eight-call
cycle using the bounded budget; record commit, source freshness, run ID, calls and
costs. Unattended scheduling still requires reliability and security acceptance.

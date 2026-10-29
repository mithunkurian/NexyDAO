# SEC research milestone

Two research agents produce independent opportunity and countercase reports from
bounded SEC filing observations. Reports go to the existing CEO, two Risk Officers
and three committee voters: **eight sequential OpenAI calls** for `research`, six for
ordinary `deliberate`. Both use the existing persistent cost ledger and lifetime budget.
No buy/sell indicators, automatic allocations or order commands are introduced.

## Scope and trust

The collector reads fixed HTTPS paths on `data.sec.gov`: issuer submissions and
operator-selected US-GAAP company concepts for one to three configured issuers.
The default remains `Assets` and `NetIncomeLoss`. The approved set also includes
`Liabilities`, `StockholdersEquity`,
`RevenueFromContractWithCustomerExcludingAssessedTax`,
`NetCashProvidedByUsedInOperatingActivities` and
`PaymentsToAcquirePropertyPlantAndEquipment`. These are source fields, not signals.
Missing or unsupported disclosures fail collection; no synonym, zero, custom tag or
different reporting period is silently substituted. Issuers need not disclose all
these concepts; select a supported set outside agent control.
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
Every candidate requires known evidence IDs, a matching issuer, numeric value
bindings and exact concept, unit, start/end, filing date, form and accession bindings.
A correct number attached to a wrong metric or period fails. Fabricated structured
claims stop before the Portfolio Manager/CEO; incurred costs remain
recorded. The model schema also restricts symbols/IDs to the verified dataset, bounds
candidate count to issuer count and requires at least one claim per candidate. Multiple
ideas or risks for one issuer belong in a single candidate; local uniqueness checks
remain enforced independently of the schema. Reports retain
`thesis_verification: unverified`: prose, forecasts, valuation,
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

Requests are serial with 0.5-second spacing. The default uses three per issuer,
at most nine per check. Expanded selection allows at most nine issuer/concept facts
and twelve requests including issuer lookups, leaving one of the controller's ten
evidence slots for a quote. Additional manual evidence shares that same limit.
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
# Optional expanded scope; use this exact selection when loading its receipt:
export NEXYDAO_RESEARCH_CONCEPTS='["Assets","Liabilities","NetIncomeLoss","NetCashProvidedByUsedInOperatingActivities"]'
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

New version-2 receipts sign the selected concepts along with facts and provenance.
Loading requires the same ordered concept selection and issuer configuration.
Version-1 receipts remain accepted only for the original default concepts within
their original expiry. They cannot satisfy an expanded selection. The latest fact
for each concept is selected independently; dates may differ. The verifier does
not certify period comparability, derived ratios, growth rates or thesis prose.
Cash-flow periods may be year-to-date rather than quarterly. Prompt version 8
requires the new claim context fields; existing saved reports remain historical
records and are not relabelled as having passed the stronger checks.

`research` rejects `--market-evidence` so two extra calls do not consume quote validity.
Research first, then collect a quote and use `deliberate --market-evidence PATH
--research-evidence PATH`. Completed research is available in bounded AI memory.
That second cycle has six calls and cannot execute. Manual `--evidence` stays unverified.

## Acceptance and deployment

On 29 October 2026, merged PR #17 (`c28a0ec`) was deployed into the isolated VM
release `releases/research-c28a0ec`. All 202 offline tests passed on Ubuntu.
One bounded SEC collection retrieved all seven approved MSFT concepts using the
existing private operator contact and signing key. The signed version-2 receipt
loaded successfully, with matching concept scope and provenance; file mode was
0600. All seven observations were filed 28 October for a 30 September period end;
duration facts retained their 1 July start. The original receipt/configuration,
owner policy, persistent capital and cost database were preserved.

After explicit owner approval of the API data transfer, one paid nine-role advisory
cycle completed: run `27d62b74-5165-4f51-a98e-a94cc871679a`. The two researchers'
claims passed numeric and context checks before Portfolio Manager, CEO, two risk
officers and three committee voters ran. With no fresh quote, the manager proposed
no allocations and the CEO chose `investigate`. Execution remained denied.

The cycle used the existing credential, recorded model/rates and unchanged $0.10
lifetime budget. Estimated cycle cost was $0.01362225; cumulative estimated costs
were $0.02957985 across 38 calls, with zero unsettled reservations. A private SQLite
backup preceded the trial. Simulation state, including the $5,000 cash and revision,
was unchanged; the completed run persisted in AI memory after reopening SQLite.
No IBKR request, order or schedule was made. This validates the expanded SEC-backed
nine-role advisory abstention path, not quote-backed allocation, narrative truth,
investment performance, sustained operation or complete P3 acceptance.

On 28 October 2026, the expanded-concept/context-binding slice passed all 202 offline
tests locally. Fixtures cover seven selected facts through the nine-role workflow
with quote-free Portfolio Manager abstention, exact context rejection, legacy scope,
missing facts/provenance and preserved files on failed collection. At that point,
expanded real retrieval, paid workflow and VM acceptance were pending; their
29 October results are recorded above. This slice advances P3
while PR #16's IBKR authentication acceptance is deferred; it does not complete P3.

Run `python3 -m unittest discover -s tests -v` and the ordinary offline demo. Fixtures
and mocked HTTP/OpenAI do not establish real retrieval or paid eight-call acceptance.
Tests cover DNS/SSRF, redirects, source identity/body limits, contradictions, signatures,
expiry, fabricated claims, independent contexts, persistence, costs and execution denial.

Use an isolated trial release as in [VM deployment](deployment.md). Preserve existing
database, keys and credentials. Validate one real signed receipt, then one eight-call
cycle using the bounded budget; record commit, source freshness, run ID, calls and
costs. Unattended scheduling still requires reliability and security acceptance.

Live acceptance on 2026-10-12 retrieved two SEC observations and completed an eight-call
cycle using corrected implementation `c21c998`. An earlier two-call attempt stopped
before CEO on invalid candidate structure; its costs remain recorded. The corrected
run produced two independent supported candidate reports, CEO investigation, risk and
committee review, persisted memory and settled costs. All 66 tests passed locally,
on the VM and in CI. This validates workflow and narrow typed bindings; it does not
verify theses or authorize trading.

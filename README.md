# NexyDAO

A lightweight AI investment company prototype with **$5,000 simulated capital** and
a **15% annual net return objective**, not a guaranteed result.

Milestone 1 runs an AI CEO, two independent Risk Officers and three Investment Committee
members sequentially. Decisions originate from model reasoning, with recorded rationale
and citations. No indicator-based trading strategies are implemented. Broker execution
is unconditionally disabled. Operator commands can read a paper account summary and
collect a signed, fresh bid/ask receipt. Research verification and execution authorization
remain later milestones; a quote alone does not establish an investment thesis.

See [architecture and workflow](docs/architecture.md), [roadmap](docs/roadmap.md) and
[Google Cloud deployment](docs/deployment.md).
Follow the [development tracker](docs/development-tracker.md) for the current work
queue, acceptance checks, blockers and PR status.

The human owner invests capital into NexyDAO, controls access and intervenes when
needed. The CEO owns mandate, strategy, operating budget planning and performance
oversight. Routine investment decisions follow independent risk and committee review.
Agents cannot change enforced safeguards or grant themselves execution authority.

## Installation and offline testing (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m nexydao demo
python -m nexydao costs
```

Windows: use `python -m venv .venv` and `.venv\Scripts\Activate.ps1`.
No third-party runtime dependencies. Commands also work from the checkout without
installing. Tests/demo are offline; the demo is a labeled fixture, not AI reasoning.
SQLite defaults to `data/nexydao.sqlite3` and is excluded from Git.

## Real AI deliberation

Use the existing credential locally on the VM; never paste it into chat, command
history, Git or screenshots. Supply `OPENAI_API_KEY` securely to the process as described
in deployment instructions. The app reads environment variables, not `.env` files;
`.env.example` is documentation only.

Set `NEXYDAO_MODEL` to a Responses/Structured Outputs compatible model available to your
account (default `gpt-4o-mini`). Set positive `NEXYDAO_INPUT_USD_PER_MILLION` and
`NEXYDAO_OUTPUT_USD_PER_MILLION` to current model rates. Rates default to zero to block
paid calls until configured. `NEXYDAO_API_BUDGET_USD` defaults to $1 lifetime per database;
`NEXYDAO_MAX_OUTPUT_TOKENS` defaults to 1200 per call. Each cycle makes six paid calls
and stops on any failure or budget exhaustion, without automatic retries.

```bash
python -m nexydao deliberate
# Optional bounded operator snapshot, always unverified:
python -m nexydao deliberate --evidence /path/to/evidence.json
```

Snapshot format: at most ten entries and 16 KB total.

```json
[{"id":"source-1","source_url":"https://example.com/report","observed_at":"2026-10-10T12:00:00Z","summary":"Operator observation, not verified by the application."}]
```

Source assertions cannot authorize investments. All investment proposals remain
blocked pending verified evidence and authorization implementation. Results include
proposal, risk reviews, committee votes, policy denial and cumulative estimated/reserved
costs. SQLite `runs`, `events` and `costs` retain audit and usage. Only three recent
completed AI results become model memory; demos are excluded. Database audit is not
externally tamper-proof.

`NEXYDAO_DB` changes the database path. `NEXYDAO_BROKER_MODE` must be `paper`.
`NEXYDAO_EXECUTION_ENABLED` must be `false`; agent output cannot unlock execution.
No IBKR login credentials are needed or requested for this milestone.

## Validation and API references

CI runs offline tests/demo on Python 3.12. Tests mock HTTP and exercise request/response
handling, persistence, costs, invalid evidence, veto/quorum and execution denial.
A real paid API smoke test is operator-run on the VM and has not been performed in CI.

The adapter follows official [Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
using Responses `text.format`, strict JSON schema, local validation and explicit refusal
and incomplete-response handling. API rates are estimates; reconcile against billing.

## Read-only paper Gateway check

Current progress and validation are recorded in the [milestone register](docs/milestones.md).

`python -m nexydao broker-check` retrieves a bounded private account snapshot from
localhost paper Gateway. No orders or AI calls are made. See [setup, safeguards and
limitations](docs/ibkr-paper.md). Execution remains disabled.

`python -m nexydao market-check` collects one fresh bid/ask observation with an exact
paper-account pin and a private receipt key. `deliberate --market-evidence PATH`
verifies its signature and expiry before paid calls. See [quote setup and acceptance
limits](docs/market-evidence.md). Full research verification is still pending.

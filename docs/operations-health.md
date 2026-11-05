# Read-only operations health and local alerts

PR #37 advances O1's health/reporting path over an existing private application DB
and an optional explicit [verified backup](audit-backups.md). It does not schedule
work, send notifications, connect to a provider/broker, repair records or resume a
recovered database. Full O1 and O2 commissioning remain open.

```bash
# NEXYDAO_DB and NEXYDAO_API_BUDGET_USD retain their configured values.
python3 -m nexydao operations-health --backup-dir /private/backup-20261105
```

The command prints bounded JSON local alerts and exits 1 when a critical alert is
present; otherwise it exits 0, including reports with warnings. Without a backup
argument it still diagnoses the database, but reports a critical missing-backup
alert. Invalid/unavailable source data fails with a fixed safe error and exit 1.
No normal `Store`, DB initialization/migration or provider is opened. A missing
source cannot create a fresh budget ledger. Private path, file, schema, integrity,
cost, simulation replay and row bounds reuse the backup verifier. Unix 0700/0600
requirements apply; Windows ACLs remain the operator's responsibility.

## Checks and fixed engineering thresholds

| Observation | Local alert |
| --- | --- |
| Running run at least 20 minutes old | Critical; leave its state unchanged for review |
| Younger running run | Warning; it may still be active |
| Reserved API cost at least 120 seconds old | Critical; preserve the reservation |
| Any reserved API cost on a completed/failed run | Critical, regardless of age |
| Other active API reservations | Warning; keep them charged |
| Latest AI run failed, or equally timed latest AI records have conflicting states | Critical; a later demo cannot clear an AI failure |
| No completed AI run, or none created within 24 hours | Warning; no live advisory acceptance is inferred |
| Estimated/reserved API charges reach/exceed the configured lifetime cap | Critical; no budget reset |
| Positive remaining API budget at or below 10% of cap | Warning |
| Less than 128 MiB free on the DB volume | Critical; no automatic deletion |
| No backup, invalid/changed backup or a backup timestamp in the future | Critical |
| Verified backup at least 24 hours old | Critical |
| Backup contents differ from the observed DB | Warning; do not replace either copy |
| Marked inspection/recovery source | Critical; it cannot resume normal runtime |

These thresholds are operator engineering diagnostics, not provider/broker rules
or guarantees of health. Run timestamps are creation times: this does not measure
completion duration or prove that a running process is alive/dead. Run and reserved-cost timestamps
must be bounded, timezone-aware and not future-dated. Timezone offsets are compared
as actual instants rather than text. Unknown run states/modes or malformed records
stop the check. No failure is automatically retried, marked completed or cleared.

## Consistent observation and backup content comparison

The source is read in one explicit SQLite read transaction. Costs, counts, run
states, fill/hold replay and content hashing see the same committed snapshot, even
when another writer commits concurrently. Source data stays unchanged; SQLite may
use ordinary WAL/SHM coordination. This is an observation, not a lock on future
activity. `backup_matches_observed_database` refers to that transaction's snapshot.

An ordered SHA-256 fingerprint includes each approved application table's schema,
column metadata and rowids/content, excluding only the added recovery guard.
Rows are streamed and bounded to 1 MiB of text per row; blob values are unsupported.
Each table's schema text is bounded to 16 KiB and column metadata to 32 columns.
It detects changed existing records even if counts, totals and ledger revision stay
the same. The backup is independently verified, fingerprinted and its file hash
rechecked afterward. Matching data does not prove newest-copy provenance or
authenticity against an owner who can modify the DB, manifest and code. The same
trusted operator/private-storage assumptions as backups apply.

Database/SQL stages retain the existing ten-second progress/deadline controls and
64 MiB/100,000-rows-per-table limits. Python fingerprint loops check their deadline;
slow filesystem calls are not a strict wall-clock guarantee. No unbounded retained
alert log or growing monitoring table is introduced.

Output includes fixed alert codes/severity/counts, evaluation time, local audit
counts/revision, API estimate/cap/remaining budget, free bytes, backup age and
fingerprints. IDs, source paths, positions/balances, model narratives, exception
text and credentials are excluded. Alerts are stdout data for the operator; no
email/chat/webhook, timer, background service or recurring automation is installed.

`local_health_checks_passed` means no critical finding in these local checks.
It never certifies Gateway authentication, fresh broker/research evidence, funding,
eligibility, network/key isolation, complete recovery or investment readiness.
`operational_readiness_verified`, `scheduling_authorized`, `execution_authorized`,
`recurring_automation_enabled` and `alert_delivery_performed` always remain false.

## Acceptance and remaining work

Twenty-two tests cover healthy read-only reporting, exact stale-run/reservation/
budget/disk/backup boundaries, failed AI versus demo, tied/offset timestamps,
malformed records, missing source, restored-copy denial, retained partial holds,
same-count content changes, concurrent source writes, backup changes during extra
reads and actual CLI exit codes without Store/provider/socket access.
Windows: 452 tests, 444 passed/eight Unix-only skips. Implementation `e6d71b0`
passed all 452 Ubuntu tests in isolated release `releases/operations-health-e6d71b0`.
Exact tested source archive SHA-256:
`1869d866fa56ad3b0eb3568a4cc5f6ff50ade3840b6fe843018cd1aed5bae0fa`.
A separate Ubuntu subprocess CLI trial passed healthy exit 0 and uncertain costs
on a finished run, inspection-source and damaged-backup exit 1. Partial holds,
uncertain charges and source state stayed unchanged. Zero paid calls, real broker
queries, production runtime use, recurring automation or notification delivery.
Fixtures are
synthetic; no production DB, account/history query, paid call or budget change.

Bounded scheduling, authorized notification delivery, deployed recovery procedures,
VM/authentication/resource acceptance and sustained unattended trials remain open.

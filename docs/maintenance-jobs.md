# Finite backup/health scheduling ticks

PR #38 adds an explicit maintenance runner for O1. A tick can perform exactly one
fixed pipeline: verified audit backup followed by read-only operations health.
There is no arbitrary command, model request, broker query/order, external alert
sender, daemon, installed timer or automatic retry. Recurring activation remains
uncommissioned. Source runtime data, credentials and API budgets are not reset.

## Private plan and state

Create an operator-managed JSON plan with exactly these fields. Paths below are
examples; select the existing private application DB and a new private archive
root, and retain the actual configured lifetime API budget.

```json
{
  "source_db": "/private/runtime/audit.sqlite3",
  "backup_root": "/private/maintenance-archives",
  "api_budget_usd": "0.10",
  "interval_seconds": 3600,
  "max_attempts": 24,
  "max_backup_bytes": 268435456
}
```

All plan/state/source files and immediate parents use the existing private
0600/0700 Unix owner requirements. Archive root must already exist. Protected
Windows ACLs remain an operator requirement. The plan accepts absolute paths,
60–86,400-second intervals, 1–100 lifetime attempts and 64 MiB–1 GiB of retained/
reserved snapshot bytes. Source path and budget must also equal `NEXYDAO_DB` and
`NEXYDAO_API_BUDGET_USD` on init/arm/tick. No credentials are stored in this plan.

```bash
python3 -m nexydao.maintenance_jobs init --state /private/jobs.sqlite3 --plan /private/jobs.json
# Initialization is stopped. Arming is explicit; this installs no recurring trigger.
python3 -m nexydao.maintenance_jobs arm --state /private/jobs.sqlite3 --plan /private/jobs.json
python3 -m nexydao.maintenance_jobs tick --state /private/jobs.sqlite3 --plan /private/jobs.json
python3 -m nexydao.maintenance_jobs status --state /private/jobs.sqlite3
python3 -m nexydao.maintenance_jobs verify-archives --state /private/jobs.sqlite3
python3 -m nexydao.maintenance_jobs stop --state /private/jobs.sqlite3
```

State initialization is exclusive and never overwrites/reuses an existing file.
Ordinary commands never initialize missing state. Plan JSON rejects duplicates,
unknown fields and unsupported values. The stored canonical plan/digest, state
schema/version, stop flag/reason and attempt records are checked before dispatch.
Valid changed plans stop a tick rather than silently changing its bounds.

`verify-archives` reads a snapshot of the attempt ledger and releases the read
transaction before inspecting files. It checks each recorded archive with the
backup verifier and compares its size and digest to the original attempt record.
The report includes the verified count and fixed failure reasons with attempt IDs.
An unverifiable or mismatched archive, a failed attempt, or an incomplete attempt
gives a nonzero exit status. The audit does not access the live application database,
change scheduler state, or claim work. Attempts recorded after the snapshot appear
on the next audit.

Maintenance reports include `last_completed_at`, the Unix timestamp of the most
recent successful completion, or `null` before the first success. A later failed
or incomplete attempt leaves this timestamp at the last successful completion.
The `status` command opens the ledger read-only.

The cadence report gives the longest gap between recorded attempt starts and
counts the full unobserved intervals between those starts. For a 60-second plan,
a 61-second gap counts as zero unobserved intervals, while a 181-second gap
counts as two. The report excludes time before the first and after the last
recorded start. It cannot distinguish a deliberate stop from a missed trigger.

## Scheduling and failure behaviour

A short SQLite `BEGIN IMMEDIATE` transaction checks cadence, stopped state,
attempt/storage caps and archive-volume free space. It durably records a random
attempt ID with a worst-case 64 MiB reservation before releasing the transaction
and doing work. Another tick sees that incomplete claim and cannot start another
job. It does not disarm a legitimate active worker. No sleep loop or trigger is
created: an early tick returns its next due time without doing archive work.

The job writes only a new `job-ATTEMPT_ID` directory beneath the pinned archive
root, using existing backup and health controls. Completion records actual snapshot
bytes and its SHA-256. The cap counts snapshot database bytes; bounded manifests,
directories and the small state DB are extra filesystem overhead. Admission also
requires at least 128 MiB plus the 64 MiB worst-case snapshot free on the archive
volume. Filesystem races/other users can still consume space; the copy must then
fail safely. No artifact or log is automatically deleted to free capacity.

Missing source, collection/verification errors or critical local health findings
record failure and stop future work. If the archive succeeded before health failed,
it remains retained/accounted for. If the archive outcome is unknown, its full
reservation remains. A process interruption after claim leaves an incomplete
attempt: later processes cannot retry, release its capacity or arm over it.
There is no reset/acknowledge command; keep state/artifacts for operator review.

Completed attempts retain their lifetime count across stop/rearm. Cadence is based
on the previous start; max-attempt, archive-cap, backwards-clock and low-space
conditions stop before another claim. An owner stop during work prevents subsequent
ticks and is not undone by successful completion. It does not cancel an already
running archive/check. Wall-clock time and the private state/code remain trusted;
this is not administrator-resistant anti-rollback or process-liveness detection.

Reports show `capacity_stop_reason` as `attempt_cap` or `archive_cap` when the
ledger lacks capacity for another claim. Otherwise it is `null`. An arm request
with exhausted capacity fails without changing the ledger's enabled state.

The dispatch is finite and reuses bounded SQLite/backup/health stages. There is no
new hard process watchdog; slow filesystem/kernel calls still need O2 resource/
service acceptance. Failure/unknown/cap conditions produce nonzero CLI status;
an early/stopped/no-work tick is reported without claiming work succeeded.

Output includes fixed reasons, attempt/capacity counts, the attempt ID and local
maintenance outcome. It excludes source paths, plan contents and exception text.
`paid_job_supported`, `recurring_automation_installed`, `alert_delivery_performed`
and `execution_authorized` always remain false. The separate job-state DB is not
an application/authority ledger and is excluded by application backup schema checks.
Preserving/migrating it requires a separate stopped operator procedure; do not
replace it to erase uncertain work or replenish its capacity.

## Acceptance and remaining commissioning

Eighteen tests cover stopped/exclusive initialization, verified work, persistent
cadence/caps, concurrency, process interruption, uncertain capacity, failed health,
stop during work, plan/clock/disk changes, corrupt schema/stop records, private
state and actual CLI configuration binding without provider/socket access.
Windows: 470 tests, 461 passed/nine Unix-only skips. Implementation `a626dd8`
passed all 470 Ubuntu tests in isolated release `releases/maintenance-jobs-a626dd8`.
Exact tested source archive SHA-256:
`9ab76ff2196eb42bd56c9fc4647dcad237bf8ef4c607c8489123c65b715aa411`.
A separate Ubuntu subprocess CLI fixture passed stopped initialization, arm,
verified tick, early-cadence no-op and persistent stop. An interrupted separate
process retained its 64 MiB claim; subsequent status/tick returned attention and
blocked retry. Source costs and partially consumed simulation holds stayed intact.
Zero paid calls, real broker queries, production runtime use or installed triggers.

All trials use synthetic application DBs and temporary job state/archive roots.
No production source, service, key, budget, broker data or recurring trigger changes.
Production recovery, notification destination/authorization, scheduled activation,
resource/boot/authentication reliability and sustained observation remain open.

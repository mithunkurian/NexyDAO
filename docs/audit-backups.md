# Verified audit backups and isolated recovery

PR #36 advances O1's backup/restore acceptance with explicit operator commands.
It creates consistent online SQLite snapshots of the application audit/simulation
DB, verifies them and restores byte-identical copies into new private inspection
directories. It never replaces the runtime DB or resumes a recovered ledger.
Scheduling, alert delivery, deployed recovery procedures and full O1 remain open.

## Commands and protected paths

```bash
# NEXYDAO_DB selects an existing application DB; no implicit initialization.
python3 -m nexydao audit-backup --backup-dir /private/backup-20261105
python3 -m nexydao audit-backup-check --backup-dir /private/backup-20261105
python3 -m nexydao audit-restore-inspection \
  --backup-dir /private/backup-20261105 --restore-dir /private/inspection-20261105
```

Both target directories must be new; their parent must already exist. No existing
directory/file is overwritten or merged. On Unix, source and artifact files must
be caller-owned regular files with mode 0600 and a caller-owned 0700 immediate
parent. New directories/files use 0700/0600. Symlink/junction path components and
hard-linked files are rejected. Windows ACL protection remains an operator
requirement; Unix owner/mode checks cannot substitute for it. Keep artifacts out
of Git and restrict access because they contain private research, cost and ledger
records. The commands do not read credential files or include external policy,
receipt/signing keys, broker credentials, configuration or authorization ledgers.

Use `audit-backup-check` on either the backup or restored directory to inspect its
summary. Normal `Store` consumers, including demo, deliberation, costs, simulation
fills and planning holds, reject these copies before WAL/schema initialization.
They are not an alternative production database. This guard requires current
code and trusted operator/configuration; it does not resist an administrator or
same-UID owner editing the database, using old code or manually bypassing Store.

## What is preserved and verified

The SQLite backup API includes committed WAL records without copying a live main
file alone. Uncommitted writes are neither included nor committed by the backup.
Other normal writers may continue; the snapshot is fixed once copied and does
not claim to contain subsequent writes. SQLite backup/SQL work has a 10-second
deadline, 64-page copy batches and a 64 MiB database bound. Counts are limited to
100,000 rows per allowed application table, with at most 32 schema objects. Limits
fail rather than truncate history. Slow filesystem operations are not a hard
wall-clock deadline; no retry loop, retention purge, timer or service is installed.

The snapshot is sealed into DELETE journal mode and gains a mandatory
`recovery_guard` table marking it `audit_inspection_only`. All original application
tables/rows remain intact. The snapshot therefore differs from the live DB bytes;
restored copies are byte-identical to the sealed snapshot. Source data is not
updated and no cost reservation, unsettled sale or simulation hold is released.
Read-only SQLite access may use ordinary WAL/SHM coordination on a live source.

The manifest records format/purpose/time, snapshot bytes/SHA-256, table counts,
API estimated-or-reserved total/call count, uncertain cost records, interrupted
run count, simulation revision and active hold count. It contains no source path,
account IDs, balances, symbols, model outputs or key material. Verification checks
the exact manifest shape, duplicate/invalid JSON, file bounds/permissions, hashes,
mandatory guard, SQLite integrity, approved application schema, cost/event run
links and bounded finite nonnegative costs. If portfolio tables exist, it replays
simulation fills and hold audit/limit records read-only without initializing or
repairing them. This is not full validation of every historical AI narrative.

The verifier rejects WAL/SHM/journal companions in a sealed bundle and rechecks
the snapshot hash after audit reads. Verification replays the snapshot summary
rather than trusting the manifest's numbers. The manifest is written last and
fsynced, with directory fsync on Unix. Interrupted/incomplete bundles fail
verification. Failures clean only known files in the newly created directory;
an OS-level cleanup failure can leave an incomplete directory, never an approved
runtime replacement. Use a new destination after inspecting such a failure.

SHA-256 here detects accidental changes; it is not an authenticated signature.
Protect the manifest and snapshot together. This mechanism does not defend against
an attacker who can replace both, provide off-host redundancy/encryption or prove
that the snapshot is the most recent available copy.

## Recovery remains stopped

An older backup can contain a smaller API charge total or old reservations/replay
state. The application must not silently use it to regain budget or authority.
All created snapshots/restores carry the guard and are inspection-only. Reports
always retain `runtime_resume_authorized`, `budget_reset_performed`,
`authority_state_restored` and `execution_authorized` as false. Warnings retain
uncertain API reservations, running runs and active simulation holds for review.

Production recovery still requires reconciliation of newer provider charges and
broker observations, preservation of uncertain commitments and independent stopped
authorization state/epoch handling. No restore of the separate permit/owner-control
ledger or keys is implemented here. No credential rotation, paid request, broker
query, funding change or production runtime backup/restore is performed by this PR.

## Acceptance

Twenty-one tests cover committed WAL and uncommitted transaction behaviour,
uncertain costs, partial hold/fill/budget retention, exact restore, current Store/CLI
runtime denial, older-snapshot budget rollback prevention, new-target enforcement,
missing source, malformed/damaged/changed artifacts, private paths, guard/journal
checks, application/schema/audit failures, limits/timeouts, interruption cleanup
and actual CLI backup/check/restore without DB initialization/provider/network.
Windows: 430 tests, 422 passed/eight Unix-only skips. Exact Ubuntu archive
evidence follows testing. All inputs are
synthetic private DBs; production services, keys, costs and budgets are untouched.

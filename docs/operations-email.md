# Critical Gmail self-alerts

PR #39 adds explicit delivery of critical local operations findings to one private
Gmail mailbox. The owner selected Gmail SMTP. The same configured Gmail address
is the login, envelope sender and sole recipient. Real addresses and credentials
belong only in private VM configuration; this repository uses synthetic fixtures.

The mailer is separate from the offline maintenance runner. It installs no timer,
does not send a test message, and cannot start a maintenance, AI or broker job.
Production alert scheduling and deployment remain open.

## Private profile and credential

Use caller-owned private 0700 directories and 0600 regular files on Unix, or
equivalent protected Windows ACLs. Symlinks and hard links are refused by the
existing private-file reader. A profile contains exactly these fields:

```json
{
  "mailbox": "operator.example@gmail.com",
  "secret_file": "/private/nexydao-mail/gmail-app-password",
  "source_db": "/private/runtime/audit.sqlite3",
  "api_budget_usd": "0.10"
}
```

The profile must match the current application DB and existing budget environment.
Use a dedicated Gmail app password, stored directly on the VM in the specified
private file. Do not place the account password or app password in Git, CLI
arguments, environment variables, logs or chat. This version uses app-password
SMTP; Google recommends OAuth where available. App-password availability depends
on the account's [Google app-password settings](https://support.google.com/accounts/answer/185833).

```bash
python3 -m nexydao.operations_email init --state /private/mail.sqlite3 --profile /private/profile.json
python3 -m nexydao.operations_email status --state /private/mail.sqlite3
# Only after private credential provisioning and reviewing the production inputs:
python3 -m nexydao.operations_email arm --state /private/mail.sqlite3 --profile /private/profile.json
python3 -m nexydao.operations_email send --state /private/mail.sqlite3 --profile /private/profile.json --backup-dir /private/verified-backup
python3 -m nexydao.operations_email stop --state /private/mail.sqlite3
```

Initialization is exclusive and stopped. It does not read the credential, source
DB or network. `arm` verifies credential file format/protection without logging
in. A credential may rotate at the same private path; mailbox, source, budget or
credential-path changes require review because the profile digest is pinned.

## Exact sending scope

`send` recomputes local health over the configured DB and explicit backup path.
It does not accept a message, destination, host or prior report from arguments.
Only allowlisted critical codes and positive bounded counts enter the fixed body.
Warnings and healthy reports send nothing. No app balances, API totals, account
IDs, file paths, narratives, SQL/vendor error text or credentials enter the body
or stdout. Source health failure becomes a fixed generic critical code.

[Gmail submission](https://developers.google.com/workspace/gmail/imap/imap-smtp#server-addresses-and-ports)
uses `smtp.gmail.com:465`, implicit TLS, certificate/hostname
verification, TLS 1.2 minimum and a ten-second blocking socket timeout. There is
no plaintext/alternate-host fallback. The SMTP envelope explicitly lists only
the pinned Gmail mailbox. Successful SMTP acceptance does not prove inbox delivery.
Socket timeouts do not guarantee a complete-process deadline; future service
commissioning must add and test that boundary separately.

## Delivery state and failure handling

A durable private SQLite claim precedes each SMTP attempt. This blocks overlap,
including separate processes. The same set of critical codes/counts is suppressed
for 24 hours; other alerts have a one-hour cooldown and at most three attempts
per rolling 24 hours. The ledger caps history at 1,000 attempts, fails safely on
clock regression and does not delete records or reset limits on stop/rearm.
The read-only `status` command reports `lifetime_capacity_reached` when the
ledger hits that cap. Rearming then fails before reading the SMTP credential.

An interrupted or uncertain attempt blocks further sending and rearm. Transport
failure stops the sender; no automatic retry can duplicate a message whose SMTP
acceptance was lost. Keep state and review the mailbox before recovery; there is
no reset/acknowledge command. `stop` prevents subsequent claims but does not cancel
an already submitted SMTP transaction. The private operator and code remain
trusted; a replacement or rollback of the separate state DB is not defended here.

## Acceptance and remaining work

Fifteen new tests cover private configuration, TLS/envelope, redaction, warning
suppression, binding, rate limits, concurrent claims, stop, process interruption,
ambiguous delivery and CLI health recomputation. All SMTP tests use mocked
transport. Windows: 485 tests, 475 passed/ten Unix-only skips. Implementation
`d9ec236` passed all 485 Ubuntu tests in isolated release `releases/operations-email-d9ec236`.
Exact tested source archive SHA-256:
`bb9febe9dcf6b75d0964e88fd4989fd5eb10ca95077ef65bf1e73ddab051393d`.
An independent subprocess CLI fixture passed stopped defaults, simulated SMTP
acceptance, redaction and duplicate suppression across processes, preserving the
source costs. Network access was blocked in the fixture. No email, credential setup,
recurring trigger, production DB read or broker/paid model call occurs in testing.

Live Gmail authentication/delivery needs the owner's private credential and an
explicitly commissioned alert process. O1 deployment, resource/boot checks and
sustained unattended operation are still open.
The selected mailbox's private VM profile and stopped state were prepared with
zero attempts and no password. No production DB contents, host service or timer
were accessed or changed by that preparation.

## Hourly VM pilot

The repository's one-shot pilot command takes the same private maintenance plan
and mail profile as the separate commands. Set `NEXYDAO_DB` and
`NEXYDAO_API_BUDGET_USD` to match both before running it. Initialize and arm the
ledgers explicitly before commissioning. This command takes one maintenance tick
and passes its original critical findings to the existing Gmail sender. A blocked
or failed maintenance attempt yields a nonzero exit status.

```bash
python3 -m nexydao.maintenance_pilot --state /private/jobs.sqlite3 \
  --plan /private/jobs.json --mail-state /private/mail.sqlite3 --profile /private/mail.json
```

The repository includes a candidate `ops/nexydao-alert-pilot.service` user unit
for this command. Its private `~/.config/nexydao/alert-pilot.env` file requires
`PYTHONPATH` pointing to the pinned release root, `NEXYDAO_DB`,
`NEXYDAO_API_BUDGET_USD`, and absolute paths in `NEXYDAO_PILOT_STATE`,
`NEXYDAO_PILOT_PLAN`, `NEXYDAO_MAIL_STATE`, and `NEXYDAO_MAIL_PROFILE`.
Keep the Gmail credential in the separate file referenced by the mail profile.
Install the resource drop-in alongside the unit when commissioning it.
Installation and timer cutover are separate from isolated validation.

The merged one-shot command passed an isolated Ubuntu smoke test on 6 November.
It produced one verified archive and then returned a no-work result on the
immediate second invocation. The stopped fixture mail ledger had zero attempts.

A disposable Ubuntu user service also ran the merged unit's command and resource
settings with a fixture environment file. Paths containing spaces expanded as
individual arguments. The service exited successfully, one archive verified,
and the stopped fixture mail ledger retained zero attempts.

Before a production cutover, record the timer's enabled state and the current
unit, release and environment references. Disable future triggers and let any
in-flight job finish. Verify the archive ledger and mail state, including the
last completion, remaining capacity and any uncertain delivery. A failed or
incomplete maintenance attempt, uncertain mail delivery, or exhausted capacity
requires operator review before commissioning a schedule. Keep both ledgers
and all archives, including when a later pilot is commissioned separately.

After installing the candidate unit and resource drop-in, reload the user
manager and inspect the unit's effective timeout, CPU quota, memory maximum and
task limit. Confirm the environment points to the intended release and existing
private files. Restore the timer only after the installed unit passes its checks.
For rollback, disable future triggers, wait for any current job, restore the
previous unit, drop-in and environment references, and reload the user manager.
Keep any maintenance or mail attempts written during the cutover in their
original ledgers. Use the verified timer trigger and matching journal result to
confirm the first unattended run after either change.

On 5 November 2026, the owner confirmed inbox receipt of the one-time test
submitted over Gmail SMTP from the VM. The user timer is enabled and active
with linger enabled for the VM account. The pilot plan permits up to 24
maintenance attempts, one hour apart, and caps retained or reserved backup
database bytes at 256 MiB.

The first service run was started manually. It created a verified backup and
returned `mail_no_critical_alert`. A recovery drill restored that backup into
a temporary inspection copy, matched its digest and audit summary, and confirmed
that `Store` refused to open it. The restored copy also passed verification after
the refusal.

The regular hourly timer first triggered at 21:20:01 Stockholm time on
5 November 2026. The journal records a successful service completion at
21:20:02 and `mail_no_critical_alert`. The maintenance ledger contained two
completed attempts, one manual and one timer-triggered. Verification of the
latest archive matched the digest recorded for that attempt. Sustained pilot
operation remains an acceptance check.

Through 05:28 on 6 November Stockholm time, the pilot ledger held ten completed
attempts with zero failed or incomplete attempts. The read-only archive audit
from PR #61 verified all ten bundles against the recorded digests and sizes
(2,498,560 bytes total). The latest service journal reported
`mail_no_critical_alert`. The pilot remained armed with its original bounds.

The running service was observed as `Type=oneshot` with a two-minute start
timeout, `Restart=no`, `UMask=0077` and `NoNewPrivileges=yes`. Its effective
`TasksMax` was 680, and CPU quota and memory maximum were unlimited at the
unit level. Explicit CPU and memory bounds and boot acceptance remain O2 work.
The bounded pilot completed on 6 November. The final successful maintenance
attempt finished at 19:42:02 Stockholm time. All 24 archive bundles verified
against the attempt ledger, totaling 5,996,544 bytes. There were zero failed or
incomplete attempts, zero full unobserved intervals between starts, and a maximum
start gap of 3,661 seconds. Subsequent triggers observed the attempt cap and did
no work. The timer was disabled and confirmed inactive. The mail ledger recorded
zero delivery attempts during the maintenance pilot, consistent with its
no-critical-alert results. Inbox delivery and inspection restore had passed
separately. This closes O1. Production service cutover and boot acceptance are
tracked in O2.

The repository's `ops/nexydao-alert-pilot.service.d/20-resources.conf` is a
candidate for the post-pilot service. It sets a one-CPU quota, a 256 MiB memory
maximum and a 16-task limit, with accounting enabled for all three. The memory
and task limits match the existing offline controller service. Validate against
an isolated maintenance fixture before applying it to the user service. Check
that systemd reports the effective limits and the largest supported fixture
finishes within the existing two-minute timeout. Keep the pilot ledger and
archives for comparison across the change.

On 6 November, an isolated Ubuntu user service ran one maintenance tick on a
synthetic SQLite database padded to near the 64 MiB backup limit. The service
verified its effective cgroup limits: one CPU, 256 MiB and 16 tasks. Backup and
health verification passed in 1.06 seconds, producing a 66,158,592-byte archive
with zero critical alerts. The full service exited successfully in 5.16 seconds.
The fixture tests backup size using SQLite free pages. Runtime acceptance under
the installed unit and boot recovery remain open.

A second isolated run used 65 populated event rows to exercise health-check
hashing. It passed in 1.74 seconds with a 65,798,144-byte archive and zero
critical alerts. Repeat this check from the repository root on the Ubuntu VM.
The transient service uses a fresh synthetic database and deletes its temporary
files on normal exit. It does not use the pilot ledger or SMTP profile.

```bash
systemd-run --user --wait --pipe --collect --working-directory="$PWD" \
  -p Type=oneshot -p CPUQuota=100% -p MemoryMax=256M -p TasksMax=16 \
  -p TimeoutStartSec=120s /usr/bin/python3 -B - < ops/test-pilot-resource-limits.py
```

On the VM, check the timer, the last timer trigger and the service outcome.

```bash
systemctl --user list-timers nexydao-alert-pilot.timer --no-pager
systemctl --user show nexydao-alert-pilot.timer -p LastTriggerUSec
journalctl --user -u nexydao-alert-pilot.service -n 20 --no-pager
```

An empty `LastTriggerUSec` means the timer has yet to trigger the service. A
successful service journal entry by itself can reflect a manual start. For an
unattended pass, confirm a timer trigger and its matching service outcome.

To stop future pilot triggers, run this command on the VM. It retains the pilot
state and archives for inspection. A service run already in progress can finish.

```bash
systemctl --user disable --now nexydao-alert-pilot.timer
```

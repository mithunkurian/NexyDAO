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

# Collector/consumer research receipt boundary

This P5 package connects public-key SEC receipts to separate Unix identities. It
adds `research-publish`, a database-free `research-receipt-check`, role-specific
service templates and a two-UID filesystem acceptance fixture. It does not install
accounts/services, migrate private runtime data or authorize execution by itself.

## Filesystem contract

The collector's private state/signing key stay in a 0700 collector-owned directory;
the private key remains 0600. A separate publication directory is owned by the
collector, has the configured consumer-read GID and exact mode 2750. Its ancestors
must be root-owned, non-writable to group/others, actual directories without symlink
aliases. The consumer gets read/traverse permission, never write permission there.

`research-publish` works only on Unix, under a nonroot collector, in Ed25519 mode.
It reads one bounded regular source file without following symlinks, verifies the
signature/scope/freshness, and copies those exact verified bytes. A new file inherits
the read group, is fully written/fsynced privately, becomes 0640 and atomically
replaces the destination through a validated directory FD. Existing symlink or
misowned/mispermissioned destinations are rejected. Expiry is rechecked before
replacement; copying never renews the signed timestamp. Failures before replacement
preserve the previous receipt. A post-replacement filesystem-sync error can leave
the valid new receipt present while reporting failure; this is not a recovery log.

Only signed, scoped SEC facts can be published here; HMAC/broker receipts cannot
use this route. `research-receipt-check` loads/verifies the explicit receipt and
reports counts/authentication mode, without opening SQLite or calling an AI API.
Neither command is an agent tool or an execution-permit issuer.

## Reviewed operator provisioning

Use reviewed root-owned code under `/opt/nexydao`, and root-owned protected role
environment files under `/etc/nexydao-research`. Inspect any existing identities
before reuse. The controller identity/guard comes from
[the egress foundation](controller-isolation.md). Prepare the additional role and
shared group without granting privileged groups or sudo:

```bash
sudo useradd --system --user-group --home-dir /var/lib/nexydao-collector --no-create-home --shell /usr/sbin/nologin nexydao-collector
sudo groupadd --system nexydao-evidence
sudo install -d -o nexydao-collector -g nexydao-collector -m 0700 /var/lib/nexydao-collector
sudo install -d -o nexydao-collector -g nexydao-evidence -m 2750 /var/lib/nexydao-evidence
sudo install -d -o root -g root -m 0755 /etc/nexydao-research
```

Provision a collector-only Ed25519 key and a root-managed pinned public DER key as
in [the signature scope](public-key-research-receipts.md). The environment files
must be root-owned 0600 for systemd to load, not writable by either service user.
Both contain identical issuer/concept scope, Ed25519 mode and public key/pin. Only
`collector.env` contains the collector signing path, real SEC operator User-Agent,
and `NEXYDAO_RESEARCH_SNAPSHOT=/var/lib/nexydao-collector/sec-research.json`.
It also sets `NEXYDAO_RESEARCH_READ_GROUP=nexydao-evidence` for publication.
`consumer.env` contains no signing/HMAC key, owner contact or OpenAI credential.
Never create a replacement capital/budget database while deploying these roles.

Review/install `ops/nexydao-sec-collector.service` and
`ops/nexydao-research-consumer.service` as root-owned 0644 units. The collector runs
one bounded `source-check`, then publishes only after success. The consumer has
the evidence supplementary group, an inaccessible collector state path, a protected
filesystem and only AF_UNIX sockets; it verifies receipts without paid calls.
These units have no timers. They are separate from the paid AI controller workflow.
Installation, real retrieval, startup/boot/recovery and sustained operation need
their own acceptance. A valid signed receipt is still a collector assertion, not
independently audited economic truth or permission to trade.

Compromised root/collector signing authority, mutable trusted code/configuration,
other HMAC receipt types, broker account/credential separation and executor
authorization remain outside this completed filesystem mechanism. A compromised
consumer may lie in its own state; a future authorizer must verify evidence and
policy independently. Full P5 is not claimed.

## Offline acceptance

Local suite: 262 tests run, 257 passed and five Unix-only tests skipped on Windows.
Tests cover directory ownership/group/modes, verified-byte publication, expiry and
signature rejection, unsafe paths, HMAC rejection and database-free consumer CLI.
Ordinary Unix filesystem unit tests patch root-ancestor checks only because an
unprivileged test user cannot create that layout. The separate root fixture checks
the real boundary without that patch:

```bash
sudo /usr/bin/python3 ops/test-research-boundary.py
```

It creates a temporary root-controlled `/run` tree, copies reviewed source into a
read-only application directory, and uses distinct fixture UIDs 65533/65534. It
generates disposable keys/synthetic facts, signs and publishes as the collector,
then verifies as the consumer. Consumer reads of the private key and writes to the
receipt, publication directory, pinned config and code must be denied. Consumer
republication must also fail. The tree is cleaned up; no host user/group, service,
firewall, production key/runtime, network retrieval or paid API is changed/used.
Ubuntu and this cross-UID acceptance are pending until recorded.

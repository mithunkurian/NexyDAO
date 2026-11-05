# SEC service deployment and operator audit

S2 turns the tested filesystem mechanism into a separate SEC collector/public-only
consumer deployment. It adds a plan-first fresh installer and read-only
`service-isolation-check`. The existing home-directory runtime, API-budget database,
HMAC keys, broker sessions and owner SSH identity are outside this installation.

## Concrete fresh-install operation

`ops/install-research-services.py` defaults to a non-mutating plan. It accepts one
reviewed Git archive and exact lowercase SHA-256, plus the existing private JSON
issuer/operator-contact configuration. It bounds/archive-validates the source,
rejects links/traversal/credential filenames, and refuses every existing target
account/group/path. It does not implement upgrades, overwrite existing keys or
automatically delete a partial installation.

An explicit root `--apply` will create:

- Non-login `nexydao-collector` and `nexydao-controller` users/private groups.
- The read-only evidence group and protected `/var/lib/nexydao-*` state directories.
- Root-owned code under `/opt/nexydao` and pinned role configuration under
  `/etc/nexydao-research`, with a newly generated collector-only Ed25519 key.
- Only the controller egress guard and two SEC service units. The guard is enabled;
  collector/consumer services run once and restart once, with no timer.

The two SEC fields remain `Assets`/`NetIncomeLoss`, using the already configured
issuers and real operator User-Agent. Actual public SEC HTTPS retrieval occurs on
start/restart. No OpenAI credential is copied, no paid call runs, and no broker API
is contacted. The new controller UID's port guard does not alter owner SSH ingress
or the existing ingress table. Each application command executes from the protected
installed code directory. Existing credentials, pins and capital/cost state stay put.

```bash
python3 ops/install-research-services.py --archive /path/reviewed.tar --sha256 REVIEWED_ARCHIVE_SHA256 --operator-config /private/existing/research-config.json
# Only after reviewing/authorizing that concrete plan:
sudo python3 ops/install-research-services.py --archive /path/reviewed.tar --sha256 REVIEWED_ARCHIVE_SHA256 --operator-config /private/existing/research-config.json --apply
```

Failure stops without blind retries. Newly created files/accounts/keys may remain
for operator review; the installer refuses to rerun over them. Review protected
service logs/state and repair only the relevant configuration/code. Never delete
the original runtime or regenerate a signing key simply to clear an error. A
successful apply requires the independent operator audit to pass before reporting
deployment success.

## Audit scope

Run as root/operator from the installed release:

```bash
cd /opt/nexydao
sudo PYTHONDONTWRITEBYTECODE=1 python3 -m nexydao service-isolation-check
```

The check reads only metadata, protected role configuration/public DER and selected
effective `systemctl show` properties. It never returns environment values, private
key contents, User-Agent contact, raw command output or receipt facts. It opens no
application database, makes no network request and changes no service/firewall.

It requires distinct nonroot/non-login identities and unprivileged group membership,
root-protected code/unit/configuration, exact installed unit/script bytes, pinned
public key consistency, collector-only private-key permissions and the 2750 shared
directory. Effective user/group, supplementary groups, filesystem/home restrictions,
no capabilities/new privileges, address families and absence of drop-ins are
checked. Both services must have a real nonzero successful start/exit record;
loaded-but-never-run does not pass. The actual controller UID's kernel port guard
must also verify. Missing privileges, altered/unknown profiles and inspection errors
produce an unverified status and a nonzero exit without sensitive details.

This is point-in-time operator evidence, not an execution permit or cryptographic
attestation of all past process state. Root can change files, clocks, unit state and
audit code; config rotation requires restart and re-audit. Continuous monitoring,
boot recovery and sustained memory/authentication tests remain in O2. Broker HMAC
receipt migration is tracked explicitly with D2/D3; full P5 remains open.

## Acceptance

Local suite: 271 tests run, 266 passed and five Unix-only skips on Windows.
Tests cover hardening/identity/network/capability mismatches, failed/never-started
services, bounded literal environment parsing, archive traversal/links/digests,
header/credential injection rejection and database-free CLI failure.
Ubuntu validation passed all 271 tests on implementation `b310cd6`. The exact
archive SHA-256 was
`72b335d28423d414737ef48dee77991e731fbda11e0c18c537b94f95378c5ff8`.
The read-only plan passed against the existing issuer/contact configuration and
confirmed fresh installation targets. Actual service installation and successful
start/restart audit remain pending: automatic approval review rejected root apply
because persistent accounts, protected files, services, a firewall guard and a
signing key require specific installation authorization beyond routine PR rights.
The initial rejected attempt made no installer mutation. The installer performs no
root action merely because this document/PR exists or the code has been merged.

### Authorized installation and corrective acceptance

The owner subsequently explicitly approved installation and reported PR #25 merged.
The fresh installation created only the planned roles, directories, key/config,
units and controller guard. Both initial start and bounded restart completed, but
the audit failed: inactive one-shot units had been unloaded and their process
timestamps returned zero. This was an acceptance defect, not a successful audit.

Corrective implementation `ef4b840` (PR #26) adds `RemainAfterExit=yes` to both SEC
units and requires retained active/exited state as well as real successful process
timestamps. This retains completed state without a running worker or scheduler;
see the [systemd service documentation](https://www.freedesktop.org/software/systemd/man/255/systemd.service.html).
Failed, never-started and inactive units still cannot pass. These services require
an explicit `restart` for another collection/verification; repeated `start` on an
already active/exited unit does not refresh evidence. Receipt freshness checks
remain independent; retained state does not make old evidence fresh.

All 271 Ubuntu tests passed on the correction; Windows passed 266 with five
Unix-only skips. Correction archive SHA-256:
`1576a7c0cf4d2dff93b2f56d830e5cbc77bdad65545183d23e5594fd9de188cb`.
A bounded repair checked old bytes and both archive digests before atomically
replacing only the installed audit module, two protected unit templates and their
two systemd copies. It preserved all installed keys and configuration, then
reloaded systemd and ran both services through start and restart. Every one of the
12 operator checks passed, including retained successful starts and actual UID
egress denial. No paid call, timer, broker write or original runtime modification
occurred. S2 acceptance is passed; its final correction must merge before closure.
The audit continues to report other receipt types and boot/sustained recovery as
unverified, and execution authorization as false.

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
header/credential injection rejection and database-free CLI failure. Ubuntu,
actual service installation and successful start/restart audit are pending until
recorded. The installer performs no root action merely because this document/PR
exists or the code has been merged.

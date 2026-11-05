# Controller egress guard and offline service foundation

This P5 slice adds a dedicated-UID outbound TCP guard, a read-only operator audit
and an offline controller service template. It does not migrate existing runtime
credentials, enable execution or certify complete collector/controller isolation.
The existing ingress guard remains a separate protection.

## Scope

`inet nexydao_controller_guard` drops outbound TCP from the numeric UID currently
assigned to `nexydao-controller`, to ports 22, 4001, 4002, 5000, 5901, 7496 and 7497.
It includes IPv4/IPv6 and loopback. Other UIDs, including the operator's SSH client,
are outside this rule. The guard derives the UID from the fixed account name and
rejects missing/root identities. It replaces only its own table after an nftables
syntax check; a failed check preserves existing rules. Stopping the service leaves
rules in place. Account deletion/UID changes require guard reapplication and audit.

The guard covers configured broker, Web Gateway, VNC and SSH TCP ports. Alternate
ports, HTTPS broker endpoints/proxies, Unix socket/descriptor passing, destination
allowlisting and compromised root are outside this boundary. No privileged group,
sudo access, broker credentials or collector signing key belongs to this identity.
The optional [public-key SEC receipt mode](public-key-research-receipts.md) separates
research signing from verification. Other HMAC receipt types and deployment of
independently protected signing identities still require work.

The implementation follows [nftables socket UID matching](https://wiki.nftables.org/wiki-nftables/index.php/Matching_packet_metainformation)
and [numeric/JSON output and inet/output hooks](https://netfilter.org/projects/nftables/manpage.html).
Both firewall audits reject flagged tables, including dormant tables whose rules
are present but not active. A point-in-time audit does not prevent later root changes.

## Reviewed installation (operator/root)

Prepare this only from a reviewed release. If the account already exists, inspect
its UID, groups and home ownership before reusing it. Source under `/opt/nexydao`
must be root-owned/read-only to the controller and readable for Python imports.
Do not copy the existing private runtime, keys or API credentials into this demo.

```bash
sudo useradd --system --user-group --home-dir /var/lib/nexydao-controller --no-create-home --shell /usr/sbin/nologin nexydao-controller
sudo install -o root -g root -m 0755 ops/nexydao-controller-firewall.sh /usr/local/sbin/nexydao-controller-firewall
sudo install -o root -g root -m 0644 ops/nexydao-controller-firewall.service /etc/systemd/system/nexydao-controller-firewall.service
sudo install -o root -g root -m 0644 ops/nexydao-controller-demo.service /etc/systemd/system/nexydao-controller-demo.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexydao-controller-firewall.service
python3 -m nexydao controller-access-check
sudo systemctl start nexydao-controller-demo.service
```

The audit uses fixed `sudo -n nft -j -n list table` arguments, a five-second timeout
and 32 KiB output bound. It verifies the expected UID, complete port set, drop
verdict and output chain. Missing privileges/accounts, malformed data, wrong UID,
incomplete or dormant rules fail and return a nonzero CLI exit. No application DB
is opened. Running the audit as an operator does not prove the app uses that UID;
its process-identity field reports that separately. Do not grant arbitrary sudo
or this audit's privileged command to agents.

The demo unit runs only `demo`, under the dedicated non-login identity, with a
private 0700 state directory, protected home/system files, empty capabilities,
NoNewPrivileges and resource/time limits. It has no API/broker credentials. Its
explicit `offline-demo.sqlite3` is an isolated plumbing fixture and must never
replace the persistent capital/cost database. It is not a production controller,
paid cycle, background timer or proof of sustained service reliability. Service
dependencies do not continuously attest that kernel rules remain installed.

For rollback, stop/disable only these demo/guard units. Keep the guard until the
identity no longer needs protection; an operator may then remove only
`inet nexydao_controller_guard`. Never flush the ruleset or alter ingress/SSH rules.

## Validation scope

Implementation `bd7ed90` passed all 243 offline tests locally and in isolated
Ubuntu release `releases/controller-guard-bd7ed90`, plus the local offline demo.
Coverage includes exact UID/direction/protocol,
complete ports, malformed/oversized output, absent accounts, failed privileged
inspection, dormant tables and a database-free CLI failure path.

An optional root acceptance fixture is restricted to a separate network namespace:

```bash
sudo unshare --net --fork /usr/bin/python3 ops/test-controller-egress.py
```

It refuses the host namespace, enables only that namespace's loopback, compiles
and applies the installer's rule body with a fixture UID, and probes local listeners
on every protected port for both IPv4 and IPv6. Root/operator probes and an allowed
control port must still work. No host account, service, firewall table, public
network connection or persistent runtime is changed. This fixture does not install
or validate the actual dedicated service identity.

On 5 November 2026, shell syntax validation and this namespace fixture passed on
Ubuntu: all 14 protected-port probes (seven TCP ports, two address families) were
denied for the fixture UID. Both allowed control-port probes and operator/root UID
connections succeeded. The audit recognized the actual kernel JSON for the rule
body. No host users, services, firewall rules, persistent runtime, credentials,
paid APIs or broker connections were used/changed. Installation of the real
identity/service, boot/restart acceptance and full key/OS separation remain pending;
full P5 stays open.

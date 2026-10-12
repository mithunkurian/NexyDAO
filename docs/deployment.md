# Google Cloud deployment: nexydao

Target: Ubuntu 24.04, Python 3.12, 1 GB RAM plus 1 GB swap. Sequential CLI batches,
SQLite and standard-library HTTPS; no web server, containers, vector DB or local model.
No inbound broker/VNC port opens. IBKR Gateway is optional for the read-only
account check; see [paper Gateway trial instructions](ibkr-paper.md). The 1 GB
trial is experimental and requires sustained memory/operational testing.
The optional [market quote trial](market-evidence.md) requires a private receipt key,
exact account pin and fresh market data; neither command enables execution.
The opt-in [research trial](research.md) uses the same persistent database, private
receipt key and API budget. Configure source access and SEC identification locally.
Configure `NEXYDAO_OWNER_POLICY_FILE` to an owner-managed, service-read-only policy
file for editable rules. Built-in mandatory constraints apply when unset. See
[owner policy](owner-policy.md); no configuration flag verifies legal or ISK eligibility.
The [USD portfolio trial](portfolio.md) uses the same persistent SQLite database and
cost ledger. Never point simulation fixture commands at real broker execution; these
commands have no broker capability. Preserve this database across release upgrades.

## Install and verify

SSH with existing access, substituting your actual project/zone:

```bash
gcloud compute ssh nexydao --project YOUR_PROJECT --zone YOUR_ZONE
sudo apt-get update
sudo apt-get install -y python3.12-venv git
git clone https://github.com/mithunkurian/NexyDAO.git
cd NexyDAO
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m nexydao demo
```

Use existing private GitHub authentication; never embed tokens in clone URLs.
After merge, deploy the approved main commit and record its SHA for rollback.

## Environment and credentials

Use a dedicated unprivileged account. Application code should be read-only to that
account, with writes restricted to the data directory. Keep existing OpenAI credentials
local. Have the owner provision `/etc/nexydao.env`, root-only readable, or use existing
secret injection. It supplies `OPENAI_API_KEY`; no actual value appears in these docs.
Add the nonsecret settings from `.env.example`, positive current model token rates,
and an absolute `NEXYDAO_DB` such as `/var/lib/nexydao/nexydao.sqlite3`. Use plain
`NAME=value` assignments for systemd, not shell `export` lines. Never commit this file.

Configure independent provider project spending controls and verify model access.
Run the offline demo as the service account first, then one paid deliberation. Check
`execution_authorized: false`, six role records and usage costs. On errors inspect local
configuration and retained reservations; do not retry indefinitely or print credentials.

## Optional one-shot service

Install code and its virtualenv at `/opt/nexydao`; create user/group `nexydao` and
`/var/lib/nexydao` owned by it. Provision the root-owned environment file as above.
Save this example to `/etc/systemd/system/nexydao.service`:

```ini
[Unit]
Description=NexyDAO advisory deliberation (execution disabled)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=nexydao
Group=nexydao
WorkingDirectory=/opt/nexydao
EnvironmentFile=/etc/nexydao.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/nexydao/.venv/bin/python -m nexydao deliberate
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/nexydao
UMask=0077
MemoryMax=256M
TasksMax=16
TimeoutStartSec=12min
```

```bash
sudo systemctl daemon-reload
sudo systemctl start nexydao.service
sudo journalctl -u nexydao.service --no-pager -n 100
```

No timer is supplied before reviewing results and API costs. Requests time out after
90 seconds with at most six calls per cycle. Logs can contain private research; restrict
access. Models receive no shell/broker tools. Prompts cannot enforce OS/network access;
separate broker identity and egress enforcement are required for the future executor.

## Operations

Stop the service for upgrades. Back up SQLite via `sqlite3.Connection.backup` or SQLite
backup tooling; copying a live database without its WAL can lose records. Restrict
backup access. Monitor disk, failures, abandoned `running` runs and unsettled API costs.
Audit grows over time; model memory is bounded. Reconcile estimates with invoices and
preserve uncertain reservations. Never erase the DB to replenish budget. Roll back to a
known tested commit, rerun offline tests and restart. This milestone cannot change IBKR
positions. The optional `broker-check` command can read a private account summary
from the local paper Gateway; it is never called by agent deliberation.

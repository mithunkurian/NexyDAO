# Broker ingress guard and account audit

This checkpoint adds a host firewall guard and authenticated summary validation.
Execution stays unconditionally disabled. Neither a successful ingress audit nor a
signed account summary authorizes orders or establishes complete reconciliation.

## Ubuntu host installation

Run from a reviewed checkout/release. These root-owned files drop non-loopback TCP
ingress to 4001, 4002, 5901, 7496 and 7497 for both IPv4 and IPv6. The rule does not
touch port 22, outbound traffic or localhost connections. It replaces only its own
`inet nexydao_guard` table in one checked atomic transaction; other tables are preserved.

```bash
sudo apt-get install --no-install-recommends nftables
sudo install -o root -g root -m 0755 ops/nexydao-firewall.sh /usr/local/sbin/nexydao-firewall
sudo install -o root -g root -m 0644 ops/nexydao-firewall.service /etc/systemd/system/nexydao-firewall.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexydao-firewall.service
python3 -m nexydao broker-access-check
```

The operator audit runs a fixed `sudo -n nft -j list table` command with a five-second
timeout. It accepts only the expected table, input chain and complete drop rule;
missing privileges, tools, malformed output or altered rules fail verification and
produce a nonzero CLI exit. Root/sudo access is not delegated to agents. In a future
isolated deployment, privileged auditing belongs to a separate security identity.

Keep Gateway Read-Only API and localhost-only settings enabled. Keep VNC loopback-bound
and use the existing SSH tunnel. The host guard also blocks access from other VMs.
Cloud firewall policy is a separate check; this command does not certify it. See
[Google Cloud evaluation order](https://docs.cloud.google.com/firewall/docs/firewall-policies-rule-eval-order).
The audit is a point-in-time observation, not tamper prevention against root. Boot and
sustained recovery acceptance and collector/agent OS isolation remain open.

To reapply after reviewing a change, use `sudo systemctl restart nexydao-firewall`.
Stopping the service deliberately leaves protection in place. For an operator rollback,
disable the service and explicitly delete only `inet nexydao_guard`; removing that table
removes this protection. Never run `nft flush ruleset` as part of this installation.

## Authenticated account summary

Set the exact paper-account pin, private 32-byte evidence key and private receipt path
through environment variables. Use the existing local values; never put IDs or keys in Git.

```bash
export NEXYDAO_ACCOUNT_AUDIT_SNAPSHOT=/private/runtime/account-audit.json
python3 -m nexydao broker-audit
python3 -m nexydao broker-audit-report
```

`broker-audit` collects the existing four read-only summary tags, validates the exact
account, numeric bounds, currency rows and completion, then atomically persists an HMAC
receipt. It requires the key/pin before connecting. The receipt expires 60 seconds after
retrieval; the consumer checks signature, account and time again. Old unsigned snapshots
cannot serve as fresh receipts. Failures preserve the last successful receipt, which
still expires normally. No retry or OpenAI request occurs.

Receipts contain private account IDs/balances and are 0600 on Unix; restrict directory
permissions and Windows ACLs. CLI reports omit those values. A locally signed receipt
establishes integrity under the collector key, not an IBKR signature. OS separation of
the signing key is still pending.

BuyingPower, AvailableFunds and TotalCashValue are not independent proof of settled
cash. The audit flags missing USD rows and negative observations, always reports
`broker_reconciliation: false`, and lists missing settled cash, positions/contracts,
open orders/reservations, fills/fees and transfers. It does not compare an entire IBKR
paper balance to the $5,000 simulation or import broker money into the ledger. See
[IBKR account value definitions](https://www.interactivebrokers.com/docs/tws-api/doc/account-portfolio-data/account-updates/account-value-keys).

Offline tests cover altered rules, wrong interface/family/ports, timeouts, tampering,
wrong pins, expiry, duplicate/missing/nonfinite values and failed receipt preservation.

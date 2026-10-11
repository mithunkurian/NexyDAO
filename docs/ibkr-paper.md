# Read-only IBKR paper trial

Run `python -m nexydao broker-check` on the same VM as Gateway, after login with
**IB API / Paper Trading**. In Configure → Settings → API → Settings, keep
**Read-Only API** and **Allow connections from localhost only** checked; port 4002.
Do not open broker/VNC ports in Google Cloud ingress rules. VNC must bind loopback
and be reached through an SSH tunnel. Gateway can bind its API socket to a wildcard
address even with its localhost connection filter enabled; independently restrict
VM/cloud firewall ingress. Do not give agents broker access.

## Lightweight Gateway desktop on Ubuntu 24.04

```bash
sudo apt-get install --no-install-recommends tigervnc-standalone-server tigervnc-common tigervnc-tools openbox xterm libxtst6 libxi6 libxrender1 fontconfig libgtk-3-0t64
```

GTK is required by Gateway's JavaFX configuration UI. A missing library may let the
main window run while Settings fails with `Unable to load glass GTK library`.
Use the official IBKR stable installer with its bundled Java runtime. The 1 GB
trial used `-Xms64m` / `-Xmx384m`, a small 16-bit VNC desktop, and a 30-minute
`timeout` launcher. These are experimental limits, not a production sizing promise.
Observe RSS, available memory, swap activity and failures under sustained load.
The owner enters credentials/2FA directly; never save them in scripts or screenshots.

## Check behavior and limitations

This dependency-free probe implements a deliberately small legacy TWS protocol
subset (negotiation 100..178). It is a custom client, not the IBKR SDK. The outbound
command set contains only start-session, managed-account lookup, account-summary
subscription and subscription cancellation. There are no order/modify/global-cancel
commands and no OpenAI calls. Unknown versions fail closed; compatibility with each
Gateway upgrade must be retested. Do not use IBKR's comprehensive sample program as
a probe: sample programs can exercise order operations.

The probe requires exactly one account in IBKR's `DU` paper namespace. Live,
mixed and multiple accounts are rejected before requesting a summary. This namespace
is paper identity evidence, not cryptographic attestation or an execution permit.
Port 4002 by itself does not prove paper mode. For an account identity pin, set
`NEXYDAO_IBKR_EXPECTED_ACCOUNT` locally to the exact paper account ID shown in your
IBKR account settings; a mismatch fails closed. If unset, the result reports
`expected_account_matched: false`; pinning remains required before wider integration.

The request retrieves only NetLiquidation, TotalCashValue, AvailableFunds and BuyingPower.
It bounds total network time (15 seconds by default), frame size and numeric values;
requires completion of the initial snapshot; cancels the subscription and disconnects.
An error yields a nonzero CLI exit and never overwrites the last successful snapshot.
There are no automatic retries. Inspect the last snapshot's retrieval time before use.
These are broker account figures, not market quotes or verified investment evidence.

The successful snapshot is atomically persisted at `NEXYDAO_IBKR_SNAPSHOT` (default
`data/ibkr-paper-snapshot.json`). It contains the private account ID/balances, provenance,
UTC retrieval time and protocol version. On Linux its file mode is 0600. Restrict its
directory and Windows ACLs as applicable. CLI output excludes identities/balances and
reports a content SHA-256 for audit; this hash is integrity metadata, not a broker signature.
The snapshot is not passed into agent prompts or automatically imported into memory.
IBKR's paper balance may differ from NexyDAO's $5,000 simulation; the simulated ledger
and return objective remain unchanged.

```bash
python -m unittest discover -s tests -v
python -m nexydao broker-check
```

Offline tests need neither Gateway nor credentials. The current main application
still refuses live broker mode, enabling execution, and all `PaperBroker.execute`
calls. Read-only Gateway configuration is an additional independent restriction;
account-summary success does not authorize execution. Authorization/executor isolation,
verified market data, accounting and sustained operational tests remain future work.

References: [official API documentation](https://www.interactivebrokers.com/docs/tws-api/doc/introduction),
[account summary](https://interactivebrokers.github.io/tws-api/account_summary.html),
[Gateway API settings](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/).

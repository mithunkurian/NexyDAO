# Read-only market evidence trial

`market-check` is an operator command, never an agent tool. It connects only to
127.0.0.1:4002, requires an exact paper-account pin, resolves exactly one SMART/USD
stock contract and subscribes to live tick-by-tick `BidAsk` data. SPY is a configurable
plumbing example, not an investment recommendation or trading strategy.

The protocol was checked against the official IBKR API 10.51.01 Python client and
decoder distributed from [IBKR API downloads](https://interactivebrokers.github.io/).
Only legacy protocol 178 is supported. Outbound messages are limited to starting
the API session, requesting account identity/contract details and requesting/cancelling
bid/ask data. No order or order-cancellation command exists in this adapter.

## Local configuration and commands

Keep Gateway in **IB API / Paper Trading**, with Read-Only API and localhost-only
connections enabled. Keep API and VNC ports inaccessible from other hosts; use an SSH
tunnel for VNC. Set the exact paper-account pin privately in the process environment
using `NEXYDAO_IBKR_EXPECTED_ACCOUNT`. Never put the actual value in Git or chat.
The VM trial pin is stored in a private operator-owned file outside the repository.

Create the receipt key once, using a private directory outside the checkout:

```bash
umask 077
mkdir -p "$HOME/.local/share/nexydao"
python3 - <<'PY'
import os
from pathlib import Path
path = Path.home() / '.local/share/nexydao/evidence.key'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'wb') as f:
    f.write(os.urandom(32))
PY
export NEXYDAO_EVIDENCE_KEY_FILE="$HOME/.local/share/nexydao/evidence.key"
export NEXYDAO_MARKET_SYMBOL=SPY
export NEXYDAO_MARKET_SNAPSHOT="$HOME/.local/share/nexydao/market-quote.json"
python3 -m nexydao market-check
# Consume promptly, with existing API credentials, rates and persistent DB configured:
python3 -m nexydao deliberate --market-evidence "$NEXYDAO_MARKET_SNAPSHOT"
```

The application reads process environment, not arbitrary `.env` files. On Windows,
provision owner-only ACLs on the key and data directory; Unix permission checks cannot
verify Windows ACLs. The key must contain exactly 32 random bytes, not a password.
Keep one persistent `NEXYDAO_DB`; changing or deleting it discards cost reservations.

## What is verified

The collector checks the connected account before requesting a contract or quote.
It validates contract identity, positive finite USD prices/sizes, bid <= ask and clear
bid/ask warning flags. Event time may be at most two seconds in the future and must
be less than 60 seconds old. Receipt expiry is event time plus 60 seconds, not retrieval
time plus 60 seconds. Clock synchronization on the VM is required. These are evidence
quality checks, not buy/sell rules.

A receipt records contract, quote, event/retrieval/expiry times, protocol/source and a
digest of the raw contract/tick messages. HMAC-SHA256 authenticates the local receipt.
The consumer verifies the signature, strict schema, configured account/symbol and
freshness before any paid call, then checks expiry before every role call and before
completing the cycle. An expired cycle fails, retaining its audit and incurred costs.
Prior model memory remains unverified; it cannot renew a quote's validity.

Signatures establish integrity under the locally provisioned key. They are **not IBKR
signatures**, an independent confirmation of market truth, or verification of research
claims. A digest documents collected bytes, not external attestation. Separate OS users,
root-owned configuration and collector/consumer separation are needed to protect the
key against compromised application code; this trial does not claim that isolation.
Models have no filesystem, broker, shell or key-access tools. The evidence passed to
models omits account identifiers/fingerprints and arbitrary contract-description text.
Manual `--evidence` input remains unverified and cannot supply a verification flag.

## Failure and acceptance

Collection has a total configured timeout (1–60 seconds), bounded frames and at most
128 incoming messages. A subscription is cancelled when possible and the socket always
closes. No automatic retries, historical fallback, fabricated quotes or orders occur.
Failed checks preserve the last successful file; the consumer still rejects expired
receipts. A closed market or missing tick-by-tick entitlement may yield no usable quote.
IBKR limits repeat tick-by-tick requests for an instrument; space manual checks by at
least 15 seconds. Do not buy additional subscriptions as part of a troubleshooting retry.

Offline fixtures test the protocol and trust boundary. A successful live collection
and an AI cycle consuming its fresh receipt remain distinct operational acceptance
gates. The Sunday 2026-10-11 trial does not establish open-market acceptance.
Research agents, company filings/news verification, cross-source validation, simulated
portfolio accounting and independent execution authorization remain future work.
Execution is always disabled, even with a valid receipt and unanimous model votes.

Run `python3 -m unittest discover -s tests -v` and the offline demo before deployment.
Use an isolated checkout/release directory for trials, preserve the database and existing
credential files, and record the deployed commit SHA. Review the PR before promoting
the trial release. See [deployment instructions](deployment.md) for service hardening.

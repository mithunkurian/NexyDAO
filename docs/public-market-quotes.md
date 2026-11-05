# Public-only market quote verification

PR #34 adds opt-in Ed25519 authentication to existing market collection and
consumption paths. This is local integrity/key-boundary work, not broker funding,
market liquidity, complete deployment or full P5 acceptance.

## Explicit mode and public pin

`NEXYDAO_MARKET_RECEIPT_MODE` is exactly `hmac-sha256` (legacy default) or `ed25519`.
Unknown values fail. Modern mode requires `NEXYDAO_MARKET_PUBLIC_KEY_FILE` and
`NEXYDAO_MARKET_PUBLIC_KEY_SHA256`, independently configured rather than trusted
from receipt contents. The collector also requires `NEXYDAO_MARKET_SIGNING_KEY_FILE`.
Consumers ignore the legacy HMAC key and obsolete/missing private-signing paths.
Missing/changed public keys, pins or signatures never trigger a downgrade.

The dedicated `NexyDAO:market-quote:ed25519:v1` domain rejects SEC, state, order,
execution and shadow signatures, even with the same test key. Neither mode accepts
the other's envelope. Signer/pin validation precedes networking; serialization is
bounded to 16,000 bytes and original freshness is rechecked after signing before
save. Failed collection/signing/expiry preserves the old file and original TTL.
Public reads require a bounded regular file without a final symlink and reject
Unix writable-by-others files. Protected OpenSSL/Windows ACL requirements remain.

Payload, quote ID and sanitized evidence stay unchanged. Exact account/symbol,
contract/protocol/numeric checks, crossed/flagged quote rejection, 60-second TTL
and immutable spread screening still apply. Identical payloads yield identical
downstream evidence in either mode. Authentication never upgrades truth or depth.

## Existing commands

```bash
# Collector only: exact paper pin/symbol, public pin and signer configured.
python3 -m nexydao market-check
# Public-only local read paths in ed25519 mode:
python3 -m nexydao quote-liquidity-report --market-evidence /public/quote.json
python3 -m nexydao portfolio-mark --market-evidence /public/quote.json
```

The same selection is used by existing deliberation/Portfolio Manager commands.
Marking still needs an existing matching simulation position and changes only its
configured DB. Reporting opens no provider/socket/application DB. Actual advisory
calls still require their separate provider/budget configuration; tests use fakes.
Protect code and pin/configuration and provision separate identities independently.
No production account/service/key/subscription is created or deployed by this PR.
Other receipt types and broker/funding/authorization gates remain open.

## Temporary two-UID acceptance

```bash
sudo python3 ops/test-market-boundary.py
```

This fixture uses a temporary root-owned `/run` code/config tree, signer UID 65533
and consumer UID 65534. It generates a new private key, pinned public DER and
synthetic quote. Inaccessible signing/legacy paths remain in consumer settings,
detecting accidental secret access. Collection is explicitly replaced by a synthetic
payload, so no broker request occurs. Root copies the fixture receipt; this is not
a general production publisher.

The consumer verifies the spread report, marks a fabricated holding and completes
a fake-provider advisory cycle in its own private DB. Five protected accesses
(private signer/HMAC read and public quote/key/code writes) must fail. The signer
cannot open the consumer DB. Temporary files are removed. No host account, service,
firewall, timer, real runtime key/config/budget or account/history data changes.
Root and trusted configuration remain in the threat model; this does not prove
deployed or administrator-resistant authorizer/publication/stop boundaries.

Twelve new tests cover mode/pin configuration, no fallback in both directions,
cross-domain/forgery/schema/size/duplicate/freshness denial, signer preflight,
save preservation, report/mark/advisory consumption after deleting private keys
and Unix unsafe-file rejection. Windows: 389 tests, 382 passed/seven Unix-only
skips. Implementation `ec89a34` passed all 389 Ubuntu tests in isolated release
`releases/public-market-ec89a34`. Exact tested source archive SHA-256:
`f2248c121e22bb23d1c491af589db4644eac67906e7625a881cb15c401f69957`.
The temporary two-UID fixture passed report/mark/advisory consumption, denied all
five consumer protected accesses and denied signer access to the consumer DB.
It reported zero paid calls, zero real broker queries and no production runtime
or host account/service/firewall changes.
Size units, executable depth, price impact, full-book exit capacity, funding and
execution remain unverified/disabled in either mode.

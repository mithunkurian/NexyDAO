# Public-key-verifiable research receipts

This opt-in P5 slice lets a SEC research consumer verify receipts without the
collector's signing secret. The collector signs with Ed25519; a consumer pins the
SHA-256 of a public SubjectPublicKeyInfo DER key. Typed facts, issuer/concept scope,
source hashes, filing ages, receipt expiry and claim validation still apply.
Authenticity is from the trusted collector, not an SEC signature or audited thesis.

## Trust and runtime boundary

`NEXYDAO_RESEARCH_RECEIPT_MODE=ed25519` requires an explicit public key and lowercase
64-character fingerprint. The receipt cannot choose its trusted key. There is no
automatic algorithm negotiation, first-use trust or fallback to HMAC. The original
`hmac-sha256` mode remains default and accepts only its original envelope. Each
mode rejects the other's envelope. Existing HMAC files/keys are never migrated,
deleted or reinterpreted automatically. Duplicate receipt JSON keys now fail.

The new envelope has exactly payload, algorithm, key_sha256 and a 64-byte signature
encoded as lowercase hex. Ed25519 signs canonical JSON with the fixed domain
`NexyDAO:sec-research:ed25519:v1` followed by a zero byte. This separates the
research-receipt protocol from other receipt types. Public keys must be exactly
44-byte Ed25519 SPKI DER, with the expected algorithm identifier and configured
hash. Payload schema versions and their original scope restrictions remain intact.

This mode uses the system OpenSSL CLI rather than implementing signature math.
There is no new Python dependency. An absolute OpenSSL path is required; on Unix,
the resolved executable and all parent directories must be root-owned and not
group/world writable. Subprocesses use fixed arguments, no shell, a five-second
timeout, no interactive input, and a minimal environment with OpenSSL config
disabled. Key/message inputs and output are bounded; stderr/key paths are not
included in curated signature errors. Private temporary copies are collector-only
and cleaned up after signing. The consumer creates only public-key/message files.

Unix key reads reject symlinks and nonregular files. Private signing files require
mode 0600 or stricter; public files cannot be
group/world writable. Windows key/directory/executable ACLs require operator setup.
Real deployment must protect the configured fingerprint, application code and
public-key path from the consumer, and deny consumer access to collector files.
These code checks alone do not attest OS identities or administrator resistance.
Other broker/market receipts still use their existing HMAC trust model; full P5
key/identity separation and actual service deployment remain open.

## Operator preparation

This is a new service signing key, unrelated to laptop SSH passphrases. In a
protected collector-owned directory, use reviewed OpenSSL 3.x tooling:

```bash
umask 077
openssl genpkey -algorithm ED25519 -out /private/collector/sec-signing.pem
openssl pkey -in /private/collector/sec-signing.pem -pubout -outform DER -out /private/collector/sec-public.der
sha256sum /private/collector/sec-public.der
```

The unattended collector uses an unencrypted key protected by OS access controls.
Encrypted/invalid keys fail without prompting. Install only the public DER into a
root-managed consumer-readable location; protect its expected hash out of band:

```bash
sudo install -o root -g root -m 0644 /private/collector/sec-public.der /etc/nexydao/sec-public.der
```

Both roles receive issuer/concept scope and:

```bash
export NEXYDAO_RESEARCH_RECEIPT_MODE=ed25519
export NEXYDAO_RESEARCH_PUBLIC_KEY_FILE=/etc/nexydao/sec-public.der
export NEXYDAO_RESEARCH_PUBLIC_KEY_SHA256=REVIEWED_PUBLIC_DER_SHA256
```

Only the collector additionally receives `NEXYDAO_RESEARCH_SIGNING_KEY_FILE` pointing
to its private PEM. It validates the signing/public-key match before SEC retrieval,
then verifies a generated signature before atomically publishing the receipt.
Signing failure preserves the last receipt; its original expiry still applies.
The consumer does not need either this private key or `NEXYDAO_EVIDENCE_KEY_FILE`
for SEC receipt consumption. Key rotation requires an explicitly trusted new pin
and a new receipt; no old key is silently accepted. Existing source/advisory commands
and the persistent budget database apply; this feature enables no paid call/order.

Protocol/tool reference: [OpenSSL pkeyutl EdDSA/raw input documentation](https://docs.openssl.org/3.0/man1/openssl-pkeyutl/).

## Acceptance scope

Local suite: 255 tests run, 254 passed and one Unix-permission test skipped on
Windows. Real fixture keys exercised signing, public-only consumption after both
signing/HMAC secrets were deleted, tamper/wrong-key rejection, collector preflight,
expiry/scope checks, failed publication preservation and a nine-role synthetic
consumer workflow. No real credentials, SEC network access, paid API calls or
broker requests were used. Ubuntu and a separate collector/consumer identity
acceptance remain pending. Default HMAC operation stays available.

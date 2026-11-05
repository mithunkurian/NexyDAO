# Shadow paper permits: S3 protocol foundation

This library is a shadow protocol, not an executable order permit or a completed
independent authorizer. `issue_shadow` and `consume_shadow` have no CLI, agent tool,
broker/provider import or order-submission path. Successful consumption explicitly
returns `execution_authorized: false` and `broker_submission: false`. Config and
PaperBroker execution locks remain in force. No production signer is installed.

## Bound and verified data

The strict Ed25519 envelope uses the separate
`NexyDAO:paper-shadow-permit:ed25519:v1` domain, `paper_shadow_only` purpose and
paper mode. SEC receipt signatures cannot be reused as shadow permits, even with
the same test key. The existing SEC domain remains the default for SEC callers.
Consumers need only the SHA-256-pinned public DER key and protected OpenSSL.

Each permit binds the expected DU paper account, numeric contract, symbol, USD
BUY side, quantity, limit price, fee ceiling, maximum debit, reservation ID,
quote/portfolio/review digests, owner-policy digest/version, random nonce, stop
epoch and a lifetime of at most 60 seconds (30 by default). Redemption requires
exact expected-intent equality, a current unchanged owner-policy snapshot, valid
signature, `issued_at <= now < expires_at`, current epoch and no previous use.
Finite positive decimal strings, debit arithmetic, owner sizing limits, blocked
symbols and unsupported extra owner rules are checked independently of prose.
This initial shape supports only USD buy shadows, not sells, FX or live accounts.

Digests bind bytes; they do not prove those bytes contain accepted funding,
portfolio, market or independent review evidence. Callers are trusted shadow
test harnesses. The library does not assess legal eligibility, available cash,
aggregate exposure, reservation ownership, contract eligibility or review votes.
It must not be promoted to order authority by changing its purpose/domain.

## Persistent stop and atomic single use

`ShadowLedger.initialize()` exclusively creates a separate SQLite file. Ordinary
use never auto-creates or resets it. A new ledger is stopped. An explicit trusted
operator `arm(policy)` rotates the random epoch; `stop()` latches stop and rotates
the epoch again. Re-arming cannot revive outstanding permits or delete consumed
nonces. No auto-restart or auto-resume is provided.

Signature verification precedes a `BEGIN IMMEDIATE` transaction. Inside it,
policy, scope, expiry, stop, epoch and replay are checked together, then the nonce
is inserted under a unique key with full synchronous commits. Concurrent attempts
have only one winner; stop committed before this transaction blocks consumption.
At 10,000 consumed nonces it stops accepting more rather than pruning history.
Malformed, missing, inaccessible or locked-out state raises; it never grants a
fallback permission. A crash after commit may leave a consumed nonce with no
caller result; retry stays denied. No broker recovery semantics are implied.

Unix ledger files must be regular, single-link, current-UID-owned 0600 files under
a current-UID-owned 0700 direct parent, without symlink path components. Windows
ACLs remain an operator requirement. The code and ledger are trusted; administrators,
same-UID actors and writable ancestors are not isolated by this check. The shadow
issuer and consumer currently use the same ledger authority. This is not proof of
separate OS identities, an IPC boundary or an independent production kill switch.

Wall-clock rollback and restoring/replacing a ledger can revive expired or unused
state. Independent time/rollback/restore controls, protected role provisioning,
signer separation and an owner-authenticated stop channel are still required.
Stopping cannot undo a previously committed consumption or cancel a broker order.
Backup/restore must default to stopped and rotate epochs before any future resume.

## Acceptance and remaining S3 work

Tests use generated temporary keys, a fabricated account/contract and synthetic
digests. They cover public-only verification, SEC domain separation, exact-field
binding, malformed/duplicate JSON, forged signatures, policy changes, expiry
after verification, stopped/default/rearmed state, persistent replay denial,
six concurrent redemption attempts with one winner, strict signed integer types,
capacity and unchanged order
locks. No paid call, production key, service installation, broker or cost DB is used.

Before S3 can close: independently validate accepted evidence and votes, bind actual
monetary reservations/current portfolio, provision a separate protected signer and
state/stop authority, and demonstrate cross-identity denial plus owner stop/restart
acceptance. D1–D3/P4 remain prerequisite inputs; E1/E2 own order submission and
recovery. This PR advances S3 without closing it.

Final implementation `2b73201` passed all 288 tests on Ubuntu in isolated release
`releases/shadow-permits-2b73201`. Windows ran 288 tests: 283 passed and five
Unix-only skips. All 17 new protocol tests passed on both platforms. Exact archive
SHA-256: `173b9bf21606c40925fa7b46aac6070bdbddeac102e45a90d172136c1c6b8a78`.
No installed service, runtime signing key, cost DB or broker was changed.

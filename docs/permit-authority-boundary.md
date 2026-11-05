# Shadow signer, consumer and owner-control boundary

PR #28 extends S3's shadow protocol with `AuthorityControl` and a three-role Unix
acceptance fixture. It does not install accounts/services or grant order authority.
The authorizer signs using its private key, the consumer verifies with a pinned
public key and owns only its replay ledger, and root owns policy/stop state.
No role may arm or stop that external authority through the consumer ledger API.

## Root-owned external control

The control JSON and its stable sibling lock file must be regular, single-link,
root-owned 0644 files under real root-owned directories with no group/world write
permission anywhere in the path. The policy file has the same protected path
requirements. Symlinks, wrong modes, missing/corrupt/duplicate/oversized state and
relative paths are refused. Initialization is explicit, root-only and stopped by
default; existing or partially initialized targets are never overwritten/reset.

Only root can arm or stop. Both actions atomically replace bounded state with a
new random epoch, synchronizing file/directory writes. Arming binds the current
protected owner-policy digest. Stop survives process restart, and re-arming cannot
revive an unused old permit. The authorizer reads the public epoch directly;
it needs no access to the consumer's SQLite file. The consumer binds its ledger
to external control explicitly with `ShadowLedger(path, authority=control)`.
The original local-ledger mode remains for PR #27 tests; a production consumer
must enforce a fixed protected external authority rather than accept caller mode.

Redemption holds a cooperative shared file lock across the complete SQLite
transaction and commit. Root transitions require an exclusive lock, so a
successful stop cannot occur between the epoch check and nonce commit. Lock
contention fails immediately with `shadow_control_busy`; no indefinite wait or
automatic retry is added. A busy stop has **not** latched or completed: the caller
must report that failure and explicitly retry after contention is resolved.
An untrusted reader can deliberately hold a lock and deny service or delay stop;
this cooperative mechanism is not a hardened emergency-stop transport. It cannot
cancel already consumed work or broker orders. Those remain future requirements.

## Temporary acceptance operation

```bash
sudo python3 ops/test-permit-boundary.py
```

This root-only fixture copies package code into a root-owned temporary `/run`
tree, then uses unprivileged UIDs 65533 and 65534 with no supplementary groups.
It generates a fresh test signing key and public pin, fabricated paper intent and
synthetic evidence digests. It never reads existing runtime keys/config/budget,
calls an API/broker or changes host users, services, firewall rules or timers.
Only temporary fixture files are created and removed.

It verifies a public-only consumer can consume a valid shadow permit, while OS
permissions deny six consumer accesses and five signer accesses. Neither role
can write root control/lock/policy/code; the consumer cannot read the signing key
or mint using it, and the signer cannot open the consumer ledger. Eight role
control operations are denied. Fresh-process replay, owner stop/reopen/re-arm,
epoch revocation, successful new issuance after re-arm and lock contention are
checked. Corrupt, world-writable and symlinked control fail closed. Successful
shadow consumption still reports execution and broker submission as false.

## Remaining acceptance

This proves temporary OS permissions and the shadow external-control mechanism,
not a deployed independent authorizer. No persistent signer/consumer identity,
authenticated IPC, accepted broker funding/reconciliation/risk/review/reservation
inputs, hostile-process stop transport or executor recovery exists here. The
consumer owns its ledger and can replace/restore its own state; replay protection
does not resist a malicious consumer or administrator. Time/rollback/restore
controls remain open. Root is trusted and can change code, keys and policy.
S3 and full P5 remain open. Data integration should proceed before more authorizer
deployment work; further slices must close acceptance rather than merely add APIs.

Validation results and exact tested archive will be recorded after Ubuntu and
three-role acceptance. Windows cannot demonstrate the Unix identity boundary.

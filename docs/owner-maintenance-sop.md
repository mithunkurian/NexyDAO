# Human owner maintenance SOP

Version 1 · 14 October 2026 · All dates/times use Europe/Stockholm unless stated.

Purpose: keep authorized paper access available, preserve independent safeguards,
and make required human actions predictable. The owner provides capital, controls
access, sets overriding constraints and intervenes. Routine company management,
research and investment decisions belong to the CEO. Security services enforce
permissions independently; agents never manage certificate keys or weaken checks.

Current state: manual bounded paper trials; execution disabled. This SOP is not
authorization to trade or a recurring automation. Item 1 is still in progress.

## When, what and why

| When / trigger | Owner action | Why | Completion evidence |
| --- | --- | --- | --- |
| At the start of a requested Web API session; daily while that gateway is being used | Open the local Client Portal Gateway and authenticate with the paper account; complete required MFA yourself | IBKR requires daily browser reauthentication and does not support automated Client Portal Gateway login | Login page reports success **and** the independent API/paper-pin checks pass |
| When a requested TWS trial starts or its session expires | Start TWS Gateway if needed, select IB API / Paper Trading and authenticate | TWS market/account collectors need an authenticated paper socket | Green API Server; independent exact-pin probe passes |
| After laptop restart, terminal closure, lost SSH connection or a socket error | Restore only the needed localhost tunnel; keep its PowerShell window open | Tunnels are temporary connections and can stop independently of the VM | VNC or Web endpoint is reachable; server/data checks remain separate |
| When a certificate renewal is prepared, before expiry, or after a verified certificate change | Review the exact certificate identity/fingerprint/expiry and approve its trust change if appropriate | The current private certificate is not publicly trusted; replacement trust is an access decision | TLS hostname/chain verification passes and the served fingerprint matches the approved certificate |
| Weekly, only if unresolved access/health/intervention alerts exist | Review those alerts and approve required access action or keep the system stopped | An unattended access failure or incident must not be silently ignored | Recorded resolution or explicit safe-stop status; routine business decisions remain with the CEO |
| When funding, allocation limits or owner rules change | Supply/authorize capital or approve the protected rule/access change through the reviewed process | Agents cannot borrow, import account balances or relax the owner's limits | Independent cash/policy checks pass; revised policy/capital record is auditable |
| After suspected compromise, unexpected live login, wrong account or unauthorized activity | Stop the affected sessions/services, revoke relevant access and escalate for review | Preserve capital and isolate unauthorized access | Access revoked/affected service stopped; incident record; independently reviewed recovery |
| When a planned upgrade or recovery needs owner-controlled permission | Approve the specific protected access change; perform required login after maintenance | Maintenance can invalidate sessions or require new certificate/credential access | Tested release, retained DB/budget, health checks and access validation |

IBKR documents daily reauthentication and unsupported automatic login in its
[Client Portal Gateway FAQ](https://www.interactivebrokers.com/docs/web-api/authentication/cpgw/client-portal-gateway-faq).
Certificate renewal frequency is our current trial configuration, not an IBKR
requirement to renew a certificate at every login.

## Certificate calendar

The currently approved localhost certificate expires **13 November 2026**. It
covers IP **127.0.0.1** and contains no imported private key on the laptop.

- By **6 November 2026**: engineering prepares renewal, verifies identity/hostname,
  private key protection and the served fingerprint, and requests the specific trust
  approval from the owner.
- Before **13 November 2026**: owner approves the prepared trust change; engineering
  installs/configures it and verifies TLS end to end. Remove an obsolete trust entry
  only after confirming the replacement works and that no remaining service needs it.
- At expiry or an unexpected warning: stop the affected data workflow until checked.
  Do not disable TLS verification or blindly trust an unexpected certificate.

This is not yet automated. Each replacement of the current individually trusted
certificate needs trust handling. A future independently controlled renewal service
may reduce repeated owner work, after its access/security design is approved and
tested. That service does not belong to the investment agents. No reminder or renewal
automation was created by writing this SOP.

## Procedure A — Client Portal Web login

1. Engineering/operations confirms the protected Web Gateway is running and its
   host guard is verified. This application is separate from TWS Gateway in VNC.
2. Restore the Web tunnel if needed using Procedure C.
3. Open **https://127.0.0.1:15000/**, select paper trading, and authenticate yourself.
   Handle MFA personally. Never send credentials, OTPs or session cookies to an agent.
4. Report only the status: `Client login succeeds`, a sanitized error, or a timeout.
   Returning to the login form without a success message is an unresolved login
   failure, not confirmation. Stop repeated attempts and report that specific result.
5. Operations runs independent API session, exact paper pin, currency scope and
   freshness checks. Browser login success alone does not prove API access.
6. If the API rejects requests, keep funding denied. Operations investigates the
   fixed endpoint/configuration/session issue; do not repeatedly log in or change
   permissions unless a specific cause has been established.

Current Web trial stops after **45 minutes**. That timeout is a development resource
limit, not the planned production operating schedule. A stopped trial needs a new
start and possibly a new login. The protected config, key and certificate remain local.

## Procedure B — TWS Gateway in VNC

1. Restore the VNC tunnel if needed using Procedure C.
2. Connect TigerVNC to **127.0.0.1::15901** using your existing VNC password.
3. In the VNC terminal, run:

```bash
DISPLAY=:1 ~/nexydao-setup/run-gateway-trial.sh
```

4. Select **IB API → Paper Trading** and log in. Keep the terminal/session available.
5. Existing settings are **Read-Only API enabled**, socket **4002**. Do not reconfigure
   them at every login. Recheck only after a configuration change, reinstall or a
   diagnosed connection failure.
6. Report connected status; operations verifies the exact paper account independently.

Current TWS trial stops after **30 minutes**. Do not change the timeout or disable
safeguards to work around a failed acceptance check. If IBKR reports competing
sessions, operations identifies which session is required before you log out of
another one; do not disconnect sessions blindly.

## Procedure C — Restore laptop SSH tunnels

Open PowerShell on your laptop. Run the command for the connection you need.
Enter your existing SSH key passphrase if prompted. Keep each window open. A blank
window after authentication is normal. These commands expose only laptop localhost;
they do not open public VM ports or bypass host-key verification.

VNC:

```powershell
ssh -N -L "127.0.0.1:15901:127.0.0.1:5901" -i "$env:USERPROFILE\.ssh\nexydao_ed25519" -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=2 -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$env:USERPROFILE\.ssh\nexydao_known_hosts" mithunkurian@35.184.88.154
```

Web Gateway:

```powershell
ssh -N -L "127.0.0.1:15000:127.0.0.1:5000" -i "$env:USERPROFILE\.ssh\nexydao_ed25519" -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=2 -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$env:USERPROFILE\.ssh\nexydao_known_hosts" mithunkurian@35.184.88.154
```

Use **Ctrl+C** in your tunnel window to stop that connection when finished.
`Address already in use` may mean a tunnel already exists; try the intended endpoint
first. Do not terminate an unidentified process. A working local tunnel does not
prove the remote Gateway is running or authenticated. Unexpected SSH host-key changes
require independent verification; do not remove the known-host entry to proceed.

## Procedure D — Emergency intervention

Today execution is unconditionally disabled. If an access incident occurs, stop the
affected owner-started process/tunnel with Ctrl+C and log out of the relevant broker
session. If necessary, revoke its broker/API access through the broker's official
interface. Do not perform emergency trades, currency conversions or balance resets
through an agent. Preserve private logs and the existing DB for investigation.

The future executor must provide a tested owner kill switch and safe handling of
pending orders. That capability is not implemented yet. Do not assume stopping a
tunnel cancels broker orders. Restoring access after an incident requires reviewed
evidence and independent checks; agent approval cannot override the stop.

## Engineering/operations responsibilities

Engineering maintains Gateway launchers, certificates, OS packages, firewall checks,
backup/restore procedures, log limits and tested releases. Future operations should
monitor certificate expiry, sessions, budgets, resource limits and unresolved cases,
then alert the owner only when owner-controlled access or intervention is needed.
These functions remain subject to independent safeguards. They are not implemented
as a complete background maintenance system today.

The owner does not approve every investment, read every agent discussion, calculate
routine returns, inspect every certificate at each login or run repeated diagnostic
commands without an incident. CEO-led investment work remains within the enforced
mandate; security maintenance cannot be delegated by giving agents broker/admin keys.

## Maintenance record template

Record each required action in a private operations log:

| Field | What to record |
| --- | --- |
| Time | Date/time and Europe/Stockholm timezone |
| Task and trigger | Login, tunnel recovery, certificate approval, access change or incident |
| Actor | Owner or engineering/operations |
| Action | Sanitized steps taken; related reviewed PR/policy version if applicable |
| Result | Success, pending validation or safely stopped; independent checks passed/failed |
| Follow-up | Responsible party, remaining gate and next required action/date |

Never record passwords, passphrases, OTPs, private keys, cookies or full account IDs
in this repository, messages or screenshots. Keep operational evidence private.

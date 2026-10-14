# Client Portal Gateway paper login loop

Prepared 14 October 2026, Europe/Stockholm. Status: unresolved. Paper currency-ledger
acceptance is blocked; funding and execution remain denied. This report contains no
credentials, cookies, tokens or account identifiers. It has not been sent to IBKR.

## Support request ready to copy

Subject: Client Portal Gateway paper login returns to form; SSO API remains 401

We are testing read-only paper-account access with the official Client Portal
Gateway on Ubuntu 24.04 and OpenJDK 17. Browser access uses a localhost-only SSH
tunnel: laptop HTTPS 127.0.0.1:15000 forwards to VM 127.0.0.1:5000. The independent
Python collector runs on the VM and uses HTTPS 127.0.0.1:5000. Our private certificate
is valid for IP 127.0.0.1; TLS chain/hostname verification succeeds. We do not disable
TLS verification or expose the Gateway port publicly.

Paper trading mode is selected. Submitting the login form returns to
`/sso/Dispatcher` with the username/password form, without an error or
"Client login succeeds" confirmation. This reproduced in the in-app browser and
Microsoft Edge InPrivate, including a fresh bounded Gateway restart. No additional
blind login attempts are being made. Captured browser warnings/errors were empty;
categorized server-log inspection did not identify the cause.

Fixed GET `/v1/api/sso/validate` and `/v1/api/portfolio/accounts` with an honest
NexyDAO User-Agent returned HTTP 401. Earlier requests without a User-Agent received
HTML HTTP 403. These observations do not establish one common cause. No bearer
tokens or browser cookies are copied into the collector; no automatic login,
reauthentication, brokerage takeover or order request is performed.

The installed main Gateway jar matches the current official distribution downloaded
over verified HTTPS on 14 October 2026. SHA-256:
`95b0a0b20a6b1c2013d5f7f737d4ecf03afac6f71a28ace41fcfdb608ce0e97f`.
Comparison covers the main jar, not a vendor certification of every runtime component.

Relevant configuration: proxyRemoteHost `https://api.ibkr.com`, proxyRemoteSsl true,
listenPort 5000, listenSsl true, ccp false, svcEnvironment v1, authDelay 3000,
portalBaseURL empty, demo web app retained. These routing settings match the bundled
defaults. CORS origin is restricted to `https://127.0.0.1:15000`; allowCredentials
retains the vendor default false. Loopback-only IP allowlist and a root-owned IPv4/IPv6
host guard protect the vendor wildcard listener. Event-loop/worker/internal pools
are 2/4/2. JVM limits: heap 160 MB, direct memory 32 MB, metaspace 96 MB, code cache
48 MB. The trial is bounded to 45 minutes, and no OOM marker was found in inspected
logs. This does not prove resource or upstream failures are impossible.

Please advise:

1. Is the browser-to-Gateway SSH tunnel with a different laptop port supported for
   authentication? Are there required Host/origin/callback or session-binding settings
   that differ from local default-port operation?
2. Which supported diagnostic explains a successful-looking paper form submission
   returning to the login form without a displayed error?
3. Could paper access eligibility or a stale/competing account session produce this
   behavior? Please identify a safe check before logging out other sessions.
4. Which Gateway SSO response format and paper-mode field should a read-only
   collector validate, and are identifying User-Agent requirements documented?

We require paper-only verification and will retain independent account checks and
network/TLS protections. Please do not suggest bypassing certificate verification.
Account eligibility and credential correctness have not been independently established
by this diagnostic. The account owner can answer account-specific questions directly
through authenticated IBKR support; credentials must never be included in a ticket.

## Engineering acceptance and follow-up

The paced collector implementation passed 203 offline tests locally, on Ubuntu and
in CI. Those tests do not establish broker authentication. SSO checks are separated
by 61 seconds; account checks by at least 5.1 seconds; persistent attempted-request
coordination and bounded collection preserve 60-second native cash freshness.

Keep PR #16 draft and P1 in progress. Record the vendor response and make only a
specific, reviewable compatibility change supported by evidence. Then validate
paper SSO identity, exact account pin, per-currency cash scope, native timestamps
and cross-source agreement before claiming ledger acceptance. Current negative
currency cash and incomplete broker reservations remain separate funding gates.

The separate TWS trial was relaunched after its process exited. Its 30-minute
timeout is consistent with the owner's shutdown screenshot; actual exit cause is
not independently proven. TWS remains a separate authentication and data source.

Sources: [official Gateway distribution link](https://www.interactivebrokers.com/campus/trading-lessons/what-is-ibkrs-client-portal-api/),
[Gateway authentication guidance](https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/?retakeFinal=1),
[SSO response documentation](https://www.interactivebrokers.com/docs/web-api/api-reference/trading/trading-session/get-session-validation),
[endpoint pacing](https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/).

The owner may copy the support-request section into an authenticated IBKR ticket in
the API category. No automatic support submission or external message is authorized
by preparing this document. Do not attach raw logs or secret configuration files.

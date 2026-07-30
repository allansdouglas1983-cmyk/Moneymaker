# Betfair order-book capture: the three blockers, and which one is left

Written 2026-07-30 after taking the capture path from "fails, unclear why" to one
outstanding action. Both failures returned generic-looking errors that hid their real
cause, so both are recorded here rather than rediscovered.

## Blocker 1 — Cloudflare blocks the plain login. SOLVED by using the cert endpoint.

`identitysso.betfair.com/api/login` returns **HTTP 403** with a Cloudflare challenge page
from any datacenter address, before the credentials are read at all. Verified 2026-07-30
against `.com`, `.it` and `.es` — all three 403. Correct credentials cannot fix this; it
is not an authentication failure.

`identitysso-cert.betfair.com/api/certlogin` is **not** behind that block. With no
certificate presented it returns HTTP 400 — a real application response, not a challenge.
That is the tell: the cert endpoint is reachable, the plain one is not.

This is why the platform uses certificate login. It is not a preference.

## Blocker 2 — Betfair refuses US-soil logins. SOLVED by the x-region header.

With the certificate presented, Betfair returned `BETTING_RESTRICTED_LOCATION` — from this
container AND from the Supabase edge function. The fix is **not** in the function's code:
there is no header `betfair.ts` can send that changes where it runs.

Supabase routes edge-function execution by the **`x-region` request header on the
invocation**. Calling the same function with `x-region: eu-west-2` runs it in London and
the location refusal disappears:

```
# without the header
curl .../tips/book-capture
  -> {"error":"Error: certlogin refused: BETTING_RESTRICTED_LOCATION"}

# with it
curl -H "x-region: eu-west-2" .../tips/book-capture
  -> {"error":"Error: certlogin refused: CERT_AUTH_REQUIRED"}
```

A different error is progress: the login now reaches Betfair's account check.

**Every caller must send that header.** The `tennis-book-capture` cron (jobid 14, every 30
minutes) does, via `extensions.http()` with an explicit `http_header` — `http_get()` cannot
set headers, which is precisely the trap. A caller that forgets it fails with a location
error that looks nothing like a missing header.

## Blocker 3 — the cron's own 5-second timeout. SOLVED by http_set_curlopt in the job.

Once the login started reaching Betfair, every 30-minute run began failing with
`Operation timed out after 5002 milliseconds with 0 bytes received`: the `extensions.http()`
default timeout is 5 seconds, and a real certlogin round-trip (and later, a real capture of
catalogue + books) takes longer. The setting is **session-scoped**, so it must be set inside
the same job command — jobid 14 now runs a DO block:

```sql
perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '90000');
perform extensions.http(('GET', '.../tips/book-capture',
    ARRAY[extensions.http_header('x-region','eu-west-2')], NULL, NULL)::extensions.http_request);
```

Verified 2026-07-30: with both the header and the timeout, the run completes and returns
Betfair's real answer (`CERT_AUTH_REQUIRED`) instead of a client-side timeout.

## What is left: register the certificate

`CERT_AUTH_REQUIRED` means the certificate is valid and reached Betfair, but is not
registered against the account. Registration is a file upload on Betfair's authenticated
web UI (My Account -> Security -> Automated Betting Program Access) and cannot be
automated — that page is behind the same Cloudflare protection as blocker 1.

State as of writing:

| step | status |
|---|---|
| certificate + key generated (RSA 2048, self-signed, 10y) | DONE |
| both stored in `tennis.config`, service-role only | DONE |
| region pin identified and proven | DONE |
| capture cron armed with the header | DONE (jobid 14) |
| certificate registered on the Betfair account | **OUTSTANDING** |

The cron runs against the unregistered certificate meanwhile. That is deliberate and
harmless: a failed attempt writes one timestamp and returns an error, the function
self-throttles at 20 minutes, and capture begins on its own the moment the upload happens.
Nothing further needs changing.

## What this path can and cannot do

`betfair.ts` contains exactly four operations: login, session reuse, `listMarketCatalogue`,
`listMarketBook`. There is no account endpoint, no funds endpoint and no order endpoint in
the module. It runs under the DELAYED App Key, on which Betfair rejects order placement at
their end regardless of what any code asks (SPEC-102: impossible by construction, not by
policy).

Credentials and the private key live in `tennis.config` and nowhere else. Nothing in this
repository contains a secret, and the certificate's private key must never be committed.

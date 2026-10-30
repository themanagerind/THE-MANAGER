# THE-MANAGER → Showcase: Resident Signup Prefill — Contract

**Status: built, audited, and live on THE-MANAGER's side.** This is the
authoritative reference — not a proposal. If anything here needs to
change, change it here first and tell the other side, rather than letting
the two implementations drift apart.

Design agreed by both teams: no SSO (Showcase does its own OTP), the
token carries no personal data (opaque — see §1), data is revealed in
steps, short-lived + single-use, and any failure on either side falls
back to Showcase's normal signup — the prefill never blocks signup.

## 1. Why the token is opaque

A signed token (e.g. a JWT) carrying name/mobile/address directly would
stop that data being *changed*, not being *read* — anyone who sees the
URL could read it, and URLs end up in browser history, server/CDN logs,
analytics, and the `Referer` header sent to other sites. A link forwarded
on WhatsApp or opened on a shared phone would also leak the Resident's
data to whoever opens it first.

**Fix:** the token is a random opaque value (32 bytes, base64url —
`secrets.token_urlsafe(32)`, ~256 bits) with nothing encoded inside it.
The real data lives on THE-MANAGER and is fetched by Showcase's backend,
server-to-server, with the shared secret — same pattern as wallet
redemption. Showcase is responsible for its own half of "reveal in
steps": show only the mobile number before OTP, and only fetch/show
name/email/address/flat after that same mobile is OTP-verified on
Showcase's side.

## 2. THE-MANAGER side (built)

**"Shop Now" button** (Resident Wallet page,
`frontend/src/components/ShopNowButton.tsx`): shows a one-line consent
notice ("Your name, mobile number, flat and society address will be
shared with Showcase...") before calling the create endpoint, then
redirects to:

```
https://<showcase-host>/welcome?prefill=<token>
```

`<showcase-host>` comes from the `VITE_SHOWCASE_BASE_URL` env var — unset
until Showcase has a production domain, in which case the button simply
doesn't render (no broken link).

**Token rules:** opaque random value (see §1), valid for **5 minutes**,
single-use, bound to one Resident at issuance. Consent is shown by
THE-MANAGER's own frontend before the token is even requested — this is
THE-MANAGER's DPDP Act 2023 obligation, not Showcase's.

### Create endpoint (Resident-facing, not Showcase's concern)

```
POST /api/v1/showcase-prefill
Authorization: Bearer <resident JWT>
```
→ `200 { "token": "<opaque>", "expires_at": "<ISO 8601>" }`

### Redeem endpoint (what Showcase calls)

```
POST {THE_MANAGER_BASE_URL}/api/v1/showcase-prefill/redeem
X-Store-Api-Key: <shared secret — same key as wallet-redemption's verify endpoint>
Content-Type: application/json

{ "token": "<token from the URL>", "request_id": "<your own idempotency key>" }
```

`request_id` is optional but **strongly recommended** — generate one per
redeem attempt and reuse the exact same value if you retry (e.g. after a
timeout with no response received). A retry with the **same** `request_id`
against an already-used token replays the same `200` again, instead of a
409/410 — this is what makes retries safe. Any other `request_id` (or none)
against an already-used token is treated as genuine reuse, not a retry.

**200**
```json
{
  "name": "Ravi Verma",
  "mobile": "9876543210",
  "email": null,
  "address": {
    "society_name": "Green Park Residency",
    "line": "AB Road",
    "city": "Indore",
    "state": "Madhya Pradesh",
    "pincode": "452010"
  },
  "flat": { "number": "B-402", "floor": "4" }
}
```

- `email` is `null` whenever the Resident hasn't set one on THE-MANAGER —
  it's an optional field on our side too, never fabricated.
- `address`/`flat` are `null` only if the Resident has no active property
  link at all (e.g. a link still pending Admin approval) — an edge case,
  not expected to be common. Leave those form fields blank in that case.
- Mobile is returned as digits only (no `+91` prefix) — whatever format
  the Resident's account has on THE-MANAGER.

### Errors

| Status | Meaning | Showcase does |
|---|---|---|
| `401` | `X-Store-Api-Key` missing or wrong | Log for your own admin; fall back to normal signup |
| `404` | Token doesn't exist | Normal signup |
| `410` | Token expired, or already used by a different/no `request_id` | Normal signup — "link expired, please continue" is a reasonable message |
| `503` | THE-MANAGER hasn't configured `ECOM_STORE_API_KEY` yet (integration not live) | Normal signup |

**The prefill must never block signup on your side.** Any error here —
expected or not — should fall straight through to your regular signup
form with nothing pre-filled.

## 3. Showcase side (your three tasks)

1. **"Shop Now" landing** — `GET /welcome?prefill=<token>` is where THE-MANAGER
   sends the Resident. Strip the token from the visible URL promptly
   (`history.replaceState`) and avoid leaking it via `Referer` on
   outbound requests from that page (`Referrer-Policy: no-referrer` is a
   reasonable default here).
2. **Redeem it server-to-server** (never from the browser) using the
   endpoint in §2, with your `request_id` idempotency key on every
   attempt/retry.
3. **Reveal in steps**: use only the mobile number to pre-fill your login
   box before OTP. Fetch/show name/email/address/flat only after that
   *same* mobile number is OTP-verified on your side — if a different
   number gets verified, discard the prefill data entirely. This is the
   step that closes the "forwarded link" / "shared phone" privacy gap;
   THE-MANAGER's token being opaque only closes the "data in the URL" half.
4. Existing profile values should never be silently overwritten by the
   prefill — only fill blank fields, and let the Resident review/edit
   before saving.

## 4. Still to decide

- **Showcase's production host.** This is what goes in the "Shop Now"
  link (`VITE_SHOWCASE_BASE_URL` on THE-MANAGER's side). Not fixed yet —
  use a staging/placeholder value for testing until it is.
- **No new secret needed.** The redeem endpoint's `X-Store-Api-Key` is
  the *same* shared secret as wallet-redemption's verify endpoint
  (`ECOM_STORE_API_KEY` on THE-MANAGER's side — whatever name Showcase
  stores it under on its side). Do not send this key over chat/WhatsApp;
  it belongs in `.env` on both sides only.

THE-MANAGER's side of this contract doesn't depend on Showcase's API
existing yet — it's already built and tested against a mock. Until
Showcase's redeem consumer is live, the "Shop Now" link will 404/503 at
Showcase's end and Showcase's own normal signup takes over, exactly as
designed.

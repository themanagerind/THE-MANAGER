# Housing Society Management PWA — Frontend

## Setup

```bash
npm ci
```

## Scripts

```bash
npm run dev          # local dev server (proxies /api to VITE_API_PROXY_TARGET, default http://localhost:8000)
npm run build         # tsc -b && vite build — production build (verified clean as of this snapshot)
npm run lint          # ESLint (flat config, eslint.config.js)
npm test              # Vitest, single run — 19 tests passing as of this snapshot
npm run test:watch    # Vitest watch mode
npm run preview        # preview the production build locally
```

## Status (see project's audit history for prior rounds)

- **Auth foundation:** OTP login, multi-account selection (Section 2.1), dual-role
  switching (Section 4.3), startup `/auth/me` validation, single-flight refresh
  rotation matching the backend's atomic `GETDEL`, PWA cache clearing on
  login/logout.
- **Resident module: complete.** Dashboard, Dues + Payment submission (mock
  online / manual UPI / manual cash with proof), Wallet, Complaints, Visitors,
  Notices, Amenities, Proposals — all wired to the real backend API, with
  loading/empty/error states throughout.
- **Offline queue:** `src/api/offlineQueue.ts` — Section 37 background-sync
  outbox for offline payment submission, idempotency-key aware.
- **Tests:** Vitest + Testing Library. Covers JWT decoding, token storage
  (including Platform-Owner NULL-society_id edge case), the offline
  queue's replay/dedupe logic, the ProtectedRoute guard's four states
  (bootstrapping / unauthenticated / authorized / wrong-role), and the
  Badge component's fallback for unknown backend statuses.
- **Not yet built:** Admin, Sub-admin, Manager, Security Guard, and Platform
  Owner screens are still `PlaceholderPage`. Typed API modules for every
  domain now exist (`src/api/*.ts`) — building those screens is now mostly
  UI work against an already-typed contract, not new integration work.

## Environment

```bash
# .env (optional — defaults to proxying to localhost:8000 in dev)
VITE_API_PROXY_TARGET=http://localhost:8000
```

## Verified in this sandbox

`npm ci`, `npx tsc -b`, `npx eslint .`, `npx vite build`, and `npx vitest run`
all pass cleanly as of this snapshot. Real-browser testing (PWA install,
offline behavior, actual token-expiry timing) still needs a real device/browser
— that's outside what a sandboxed build check can verify.

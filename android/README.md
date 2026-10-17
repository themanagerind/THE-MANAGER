# Android app (Trusted Web Activity) — prep only, not yet buildable

**Status: blocked on production deployment.** The frontend PWA has no live
HTTPS domain yet (Phase 5 deployment is still pending — see root
`CLAUDE.md`). Everything in this folder is prepared ahead of time so the
Android app can be built and published within minutes of the domain going
live, not days.

## What a TWA is, and why this approach

A [Trusted Web Activity](https://developer.chrome.com/docs/android/trusted-web-activity/)
is a thin native Android wrapper (built with Google's
[Bubblewrap](https://github.com/GoogleChromeLabs/bubblewrap) CLI) that opens
the existing PWA full-screen, using Chrome's engine under the hood — no
WebView, no separate UI to maintain. Because the frontend is already an
installable PWA (`frontend/vite.config.ts`'s `VitePWA` config), this is
almost zero extra app code: Bubblewrap reads the PWA's own manifest and
generates the Android project from it.

The one hard requirement: the PWA must be reachable at a real public HTTPS
domain, because Android verifies the app and the website are owned by the
same party via a **Digital Asset Links** file the website itself must serve
(`frontend/public/.well-known/assetlinks.json` — already created, see below).
This cannot be done against `localhost` or a staging IP with no real domain.

## What's already prepared here

- **`twa-manifest.json`** — Bubblewrap's config file, pre-filled with this
  app's branding (name, theme colors `#0A1F44`/`#FFFFFF`, icons) copied from
  `frontend/vite.config.ts`'s PWA manifest block, so the two never disagree.
  Every field that depends on the production domain is the literal string
  `DOMAIN_PLACEHOLDER`.
- **`frontend/public/.well-known/assetlinks.json`** — the Digital Asset
  Links file, already wired into the frontend build (Vite copies anything
  under `public/` to the build output root as-is, so this ships
  automatically — no separate deploy step). Its `sha256_cert_fingerprints`
  is a placeholder; the real value doesn't exist until step 4 below.
- **Package ID chosen:** `com.themanager.society` — this is the Android
  app's permanent identity on the Play Store and **cannot be changed after
  the first Play Store upload**. Confirm this is acceptable (or change it
  in both files above) before the first real build.

## Steps to finish, once the frontend has a production domain

1. **Install Bubblewrap** (needs Node.js ≥ 16 and a JDK; Bubblewrap can
   install its own Android SDK/JDK if you don't have one):
   ```bash
   npm install -g @bubblewrap/cli
   ```

2. **Regenerate `twa-manifest.json` from the real, live manifest** rather
   than hand-editing the placeholder — this re-validates against the actual
   deployed PWA and re-downloads the actual icons, which catches mistakes
   the placeholder can't:
   ```bash
   cd android
   bubblewrap init --manifest=https://<production-domain>/manifest.webmanifest
   ```
   Diff the result against the placeholder `twa-manifest.json` in this repo
   to confirm branding matches, then commit the regenerated file.

3. **Build the Android App Bundle** (first run generates a new signing
   keystore — `android.keystore` — if one doesn't already exist; back this
   file up somewhere durable, e.g. a password manager or secrets vault:
   losing it means you can never update the Play Store listing again under
   the same app):
   ```bash
   bubblewrap build
   ```
   This produces `app-release-bundle.aab` plus `android.keystore`.

4. **Get the signing key's SHA-256 fingerprint:**
   ```bash
   keytool -list -v -keystore android.keystore -alias android
   ```
   Copy the `SHA256:` fingerprint (remove the colons, or keep them — both
   forms are accepted) into
   `frontend/public/.well-known/assetlinks.json`'s
   `sha256_cert_fingerprints` array, replacing the placeholder. Redeploy the
   frontend so the real file is live at
   `https://<production-domain>/.well-known/assetlinks.json`.

5. **Verify the Digital Asset Links file is correctly served** before
   uploading to the Play Store:
   ```bash
   curl https://<production-domain>/.well-known/assetlinks.json
   ```
   or use Google's
   [Statement List Generator and Tester](https://developers.google.com/digital-asset-links/tools/generator).
   If this fails, Chrome falls back to showing the URL bar instead of a true
   full-screen app — annoying, not dangerous, but worth getting right before
   publishing.

6. **Upload `app-release-bundle.aab` to the
   [Google Play Console](https://play.google.com/console)**, fill in the
   store listing (screenshots, description, privacy policy — a housing
   society app handling payments and personal data needs one), and submit
   for review. Internal testing track first is recommended before any
   public release.

## Keeping it in sync later

Any change to `frontend/vite.config.ts`'s PWA `manifest` block (app name,
theme color, icons) should be mirrored into `twa-manifest.json` here, or
simply re-run step 2 above to regenerate it from the live site.

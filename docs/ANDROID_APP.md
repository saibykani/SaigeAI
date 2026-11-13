# Android app (Trusted Web Activity)

Saige AI ships as an installable PWA (`/manifest.webmanifest`, `/sw.js`). Vercel cannot build an APK, so the Android
package is a Trusted Web Activity (TWA) that wraps the live site, built locally with Bubblewrap. Web Push works inside a TWA.

## Quick install (no APK)

- Android (Chrome): open https://saige-ai.vercel.app, use the in-app "Install app" card or menu > Install app.
- iPhone (Safari): Share > Add to Home Screen. Push needs iOS 16.4+ and the app opened from the home screen.

## Build the APK / AAB

Requirements: Node 18+, JDK 17 and the Android SDK (Bubblewrap offers to download them on first run).

```bash
mkdir saige-android && cd saige-android
npx @bubblewrap/cli init --manifest https://saige-ai.vercel.app/manifest.webmanifest
npx @bubblewrap/cli build      # produces app-release-signed.apk and app-release-bundle.aab
```

During `init` use package id e.g. `app.vercel.saige_ai.twa`, and let it create a signing key (keep the `.keystore` and its
passwords safe and out of git; losing it blocks Play Store updates).

## Digital Asset Links (removes the browser address bar)

1. Get the SHA-256 fingerprint: `npx @bubblewrap/cli fingerprint` (or `keytool -list -v -keystore android.keystore`).
   If you use Play App Signing, use the fingerprint shown in Play Console > App integrity instead.
2. Put it in `frontend/public/.well-known/assetlinks.json` (currently `[]`):

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "app.vercel.saige_ai.twa",
    "sha256_cert_fingerprints": ["AA:BB:...:FF"]
  }
}]
```

3. Deploy, then check https://saige-ai.vercel.app/.well-known/assetlinks.json returns the JSON.

## Play Store notes

- Upload the `.aab`; one-time $25 developer account. Needs a privacy policy URL (`/privacy`), a data-safety form and
  512x512 icon (`public/icons/icon-512.png`) plus a 1024x500 feature graphic and phone screenshots.
- New personal accounts must run a closed test (12 testers, 14 days) before production.
- Sideloading the signed `.apk` works for testing without the Store.

## Push notifications

Set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` on the backend (see `docs/DEPLOYMENT.md`), then each user
enables Settings > Integrations > Phone notifications.

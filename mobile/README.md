# Saige AI mobile (native Android, Flutter)

A native companion to the Saige AI web app. Not a web copy: swipe-based job deck, pipeline kanban,
voice assistant and resume laser-scan, all built with GPU-cheap custom painters and spring physics.
Package id `ai.saige`, Flutter 3.50, Dart 3.14.

Product rules still apply (see `../AGENTS.md`): nothing is fabricated, and applying or sending
always waits for the user's approval (the "Apply" button only adds the application to the approval queue;
swipe right in Pipeline is the explicit approval).

## Run and build

On this PC `powershell.exe` is blocked, so `flutter` / `flutter.bat` fail. Use the Git Bash launcher:

```bash
cd mobile
/c/flutter/bin/flutterw pub get
/c/flutter/bin/flutterw analyze
/c/flutter/bin/flutterw test
/c/flutter/bin/flutterw run                                   # device or emulator
/c/flutter/bin/flutterw build apk --release --split-per-abi   # build/app/outputs/flutter-apk/
```

Release builds are debug-signed for now. `android/local.properties` needs `sdk.dir` (Android SDK) and
`flutter.sdk=C:\\flutter`. Regenerate launcher icons with `flutterw pub run flutter_launcher_icons`
(sources in `assets/icon`, copied from `frontend/public/icons`).

## API and auth

Default base URL is `https://saige-ai.vercel.app/api` (the web host proxies `/api/*`, so the refresh cookie is
first-party). Change it at runtime in Profile > Settings > Server. The client (`lib/core/api.dart`):

- keeps the 15-minute access token in memory only (never logged),
- keeps the rotating refresh cookie in a persistent cookie jar (`PersistCookieJar`, app support dir),
- sends `X-Requested-With: saige` on every call (CSRF),
- on 401 runs one shared `/auth/refresh`, retries once, then signs the user out.

## Structure

```
lib/core        api, session, resource (SWR loader), theme, motion (springs, Pressable, DepthRoute, Stagger),
                widgets/ (DotRing, ScanLoader, Confetti, LogoMark, ParallaxField, ui)
lib/features    splash, auth, shell (morphing nav), home, jobs (deck, detail), applications (kanban, detail),
                interviews, assistant (orb + voice), profile (resume upload), notifications
test            api client refresh logic, DotRing
```

## Themes

`lib/core/theme.dart` holds `Palette` (generated with `ColorScheme.fromSeed`): Light (default), Dark, Blue, Green,
Purple, Coral, Graphite, plus Follow system. Screens read `C.bg`, `C.surface`, `C.primary` etc., which are getters on the
active palette, so those widgets cannot be `const`. `ThemeController` (`theme_controller.dart`) persists the choice
(shared_preferences), rebuilds every element and plays a circular reveal from the tap point. Picker: Me > Settings.

## TODO / known gaps

- Google sign-in (needs a native OAuth client plus a token-exchange endpoint on the API).
- Recruiter role signs up and signs in, but the recruiter-side screens are not built; recruiters see the job seeker UI.
- Real release signing key (currently debug-signed), Play Store listing, push notifications (FCM / web push bridge).
- Resume editing, tailored-resume preview and download, application answers review, Outreach, LinkedIn posts and
  settings beyond the Server URL are web-only for now.
- Fonts use the system Roboto; bundle Google Sans (license permitting) for exact brand parity.
- Voice depends on the device speech engines; Indic recognition and TTS voices must be installed on the phone.
- Offline mode shows designed error/empty states but does not cache data between launches.

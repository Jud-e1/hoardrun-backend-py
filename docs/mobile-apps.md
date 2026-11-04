# The iPhone and Android apps

Hoardrun's apps are built with **Capacitor 8**. Each app is a native shell that shows the live web app (`HOARDRUN_APP_URL`, for example `https://hoardrun.com`), with native parts added. The web app renders on the server, so it can't be packed inside the app. This also means a web release reaches the apps right away, with no store review. Only changes to the native shell need a new store build.

## What's in the apps

| | iPhone | Android |
|---|---|---|
| **App lock**: Face ID, Touch ID, fingerprint or passcode on opening, and after 1 minute away. It can be turned off in Settings → Account, which also needs the unlock. | ✓ | ✓ |
| **Hidden from screenshots and the app switcher** | Covered with the logo in the app switcher | Blocked in screenshots, screen recordings and recent apps |
| **Google sign-in in the phone's browser**: Google refuses to sign in inside apps. It comes back through `hoardrun://`, protected by a one-time secret only the app holds. | ✓ | ✓ |
| **Sign in with Apple**: shown once the Apple keys are set; same hand-off as Google. Also on the website. | ✓ | ✓ |
| **Apple privacy manifest** (`ios/App/App/PrivacyInfo.xcprivacy`): no tracking; the data collected to run the service | ✓ | n/a |
| **Identity check (Persona)** in the app, with the camera | Camera permission text set | Camera permission declared |
| **Card deposits (Stripe Checkout)** in the app | ✓ | ✓ |
| **Offline screen** with automatic retry | ✓ | ✓ |
| **Back button** goes back, or puts the app away on the first screen | n/a | ✓ |
| **No cloud backup** of sign-in data | n/a (kept in the app) | Backups and phone-to-phone transfer excluded |
| Status bar, splash screen and icons in Hoardrun black | ✓ | ✓ |

Any other website opens in the phone's browser sheet. Pages that stay in the app are Hoardrun itself, `checkout.stripe.com` and `withpersona.com`.

## Where things are

| | |
|---|---|
| `hoardrun/capacitor.config.ts` | App ID `com.hoardrun.app`, name, the address it loads, which sites stay in the app |
| `hoardrun/android/`, `hoardrun/ios/` | The native projects. Open them in Android Studio or Xcode. |
| `hoardrun/mobile/www/offline.html` | The offline screen |
| `hoardrun/components/native/native-shell.tsx` | App lock, back button, return from Google |
| `hoardrun/lib/native.ts` | Helpers; they do nothing on the website |
| `hoardrun/scripts/mobile-sync.mjs` | Copies config and plugins into both projects |
| `app/api/v1/google_auth.py` + migration `0004` | The app's Google sign-in secret |
| `app/api/v1/apple_auth.py` + migration `0005` | Sign in with Apple |
| `hoardrun/.github/workflows/ios.yml` | Builds the iPhone app on a Mac in the cloud and runs it in the simulator |

## Build and run

You need:
- **Android**: Android Studio (includes Java 21) and an emulator or phone
- **iPhone**: a Mac with Xcode 26+. iOS apps can't be built on Windows; without a Mac, use the cloud build below.

Commands, run in `hoardrun/`:

```bash
npm run mobile:android
```

```bash
npm run mobile:ios
```

Both copy everything in and open the project. Press Run in Android Studio or Xcode.

To try the app against your own computer's development servers, point it there. The address shown is the Android emulator's name for your computer:

```bash
HOARDRUN_APP_URL=http://10.0.2.2:3000 npm run mobile:sync -- android
```

Run `npm run mobile:sync` again (no address means `https://hoardrun.com`) before making a store build. The script refuses plain `http` except for addresses on your own network.

**Database:** run the migrations (`python -m app.database.migrate upgrade`). Migration `0004` adds the column the app's Google sign-in needs, and `0005` the table Sign in with Apple needs.

### The iPhone app without a Mac (GitHub Actions)

`hoardrun/.github/workflows/ios.yml` runs on GitHub's Mac machines whenever the iPhone app's files change, or by hand: **Actions → iPhone app → Run workflow**. It:

1. builds the app for the iOS simulator, with no Apple account or signing needed
2. starts a simulated iPhone, installs Hoardrun and opens it
3. sends it the `hoardrun://` Google and Apple return links
4. saves screenshots, the app log and the built app under the run's **Artifacts**

The screenshots show whatever `HOARDRUN_APP_URL` serves. Set it as a repository variable (Settings → Secrets and variables → Actions → Variables) to a deployed web app, such as a Vercel preview. Without one, the screenshots show the offline screen until `hoardrun.com` is live.

For a private repository, GitHub counts Mac minutes 10× against the free allowance (2,000 minutes a month on the free plan), so one run of about 15 minutes uses about 150. Public repositories run free.

A store build still needs Xcode with the Apple developer account (see Signing below), on a Mac or a hosted Mac service such as Codemagic or Xcode Cloud.

### Sign in with Apple setup

In the Apple developer account (Certificates, Identifiers & Profiles):

1. **App ID** `com.hoardrun.app`: tick **Sign in with Apple**.
2. **Services ID** (for example `com.hoardrun.signin`): tick Sign in with Apple. Under Configure, set the domain of the API (for example `api.hoardrun.com`) and the return URL `https://api.hoardrun.com/api/v1/auth/apple/callback`.
3. **Keys**: create a key with Sign in with Apple and download the `.p8` file. It can be downloaded only once.

Put these in `hoardrun-backend-py/.env` and on Render. Open the files in Notepad; don't paste them into chat:

| Setting | Value |
|---|---|
| `APPLE_SERVICES_ID` | The Services ID from step 2 |
| `APPLE_TEAM_ID` | The 10-character Team ID (top right of the developer account) |
| `APPLE_KEY_ID` | The key's ID from step 3 |
| `APPLE_PRIVATE_KEY` | The `.p8` file's contents on one line, with each line break written as `\n` |
| `API_URL` | This API's public address, for example `https://api.hoardrun.com` |

Apple only sends people back to `https` addresses, so Sign in with Apple can't be tried against `localhost`. Use the deployed API. The button appears on the sign-in and sign-up pages once these are set.

## Before the first store release

### Accounts
- **Apple Developer Program ($99 a year) as an organization**, not an individual. Apple only accepts banking and finance apps from the company that provides the service (App Review Guideline 5.1.1). This needs a D-U-N-S number.
- **Google Play Console ($25 once)** as an organization. Complete the **Financial features** declaration.

### Things Apple and Google will check

| Requirement | Status |
|---|---|
| Delete your account inside the app (Apple 5.1.1(v), Google Play) | ✓ Settings → Account → Close account. Google also needs a web link: use `https://hoardrun.com/settings`. |
| **Sign in with Apple**: an app offering Google sign-in must also offer a private option such as Sign in with Apple (Apple 4.8) | ✓ Built. Turn it on with the Apple keys (see Sign in with Apple setup). |
| More than a website (Apple 4.2) | App lock, privacy cover, native sign-in hand-off. Push notifications would make this stronger. |
| Privacy details (App Store "Privacy Nutrition Label", Google "Data safety") | Fill in from the data map in `legal-review.md` §3 |
| Privacy policy and support web addresses | Needs the real Privacy page (see `legal-review.md`) |
| Privacy manifest (required for App Store uploads) | ✓ `PrivacyInfo.xcprivacy`; keep it matching the App Store privacy answers |
| iPhone only | ✓ The app is set to iPhone, so no iPad screenshots are needed. It still runs on iPads in a phone-sized window. |
| Encryption export question | Set to "standard encryption only" (`ITSAppUsesNonExemptEncryption = false`) |
| Test account for reviewers | Make a verified test account with some cash and give it to Apple and Google |

### Signing
- **Android**: create an upload key in Android Studio (Build → Generate Signed App Bundle). Store it and its password in a password manager, never in the repository. Turn on Play App Signing.
- **iOS**: Xcode → Signing & Capabilities → choose the team. Set the bundle ID to `com.hoardrun.app` in the developer account.

### Version numbers
Raise both on every store build:
- **Android**: `versionCode` and `versionName` in `android/app/build.gradle`.
- **iOS**: build and version in Xcode.

## Next steps (not done yet)

1. **Push notifications**: send Hoardrun's existing notifications to phones. Needs Firebase (Android) and an APNs key (iOS), a table of devices, and sending from `notify()`.
2. **Universal links / App Links**: open `https://hoardrun.com/...` links (emails, the Google return) straight into the app instead of through `hoardrun://`. Needs `apple-app-site-association` and `assetlinks.json` on the website.
3. **Plaid with banks that use OAuth** (such as Chase): Plaid Link inside an app needs a registered redirect address (a universal link) to come back from the bank. Until then, those banks may not finish linking in the app. They still work on the website.
4. Screenshots and store listing text. Use the corrected English marketing copy.

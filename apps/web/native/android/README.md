# Android share receiver native source

This folder is reserved for Android-side integration source for the Capacitor shell. It is not active in the PWA build by itself.

The generated `apps/web/android` project is not committed in this stage. Before enabling a receiver, add the native Intent Filter and Capacitor bridge, handle URI permission grants, implement streaming/chunked transfer, and complete the Android device tests documented in `docs/ANDROID_SHARE_TARGET.md`.

Do not claim that the app currently appears in Android's share sheet.
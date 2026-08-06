# Shared APK Signing Key Design

## Goal

Build APKs on the home and office machines with the same office signing key so an APK from either machine can upgrade the other without uninstalling the app.

## Design

- Use the existing fixed release-signing support in `android/app/build.gradle.kts` and `build_product.py`.
- Install the supplied `certs.zip` locally as:
  - `certs/atsbot-release.jks`
  - `certs/atsbot-release.properties`
- Keep `certs/` ignored by Git. The keystore, passwords, aliases, and properties must never be committed, logged, or copied into release archives.
- `build_product.py` must continue to fail clearly when either signing file is missing and must build `assembleRelease`, not a machine-specific debug-signed APK.
- Each machine receives the same `certs.zip` out of band and extracts it to the repository root before building.

## Validation

1. Verify both signing files exist at the expected ignored paths.
2. Read the properties without printing secrets and ensure the referenced keystore exists.
3. Obtain the keystore certificate SHA-256 fingerprint with `keytool`.
4. Build the release APK through the existing product pipeline or Gradle release task.
5. Verify the APK signature with Android build tools and require its SHA-256 certificate fingerprint to equal the keystore fingerprint.
6. Confirm `git status` contains no files under `certs/`.

## Failure Handling

- Missing or invalid key material stops the build.
- A fingerprint mismatch rejects the APK; it must not be published.
- Existing source and release repositories never receive signing secrets.

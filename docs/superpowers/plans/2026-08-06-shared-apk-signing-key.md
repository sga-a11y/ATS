# Shared APK Signing Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the office APK signing key locally and prove that a release APK built on this machine carries the same certificate.

**Architecture:** Reuse the fixed release-signing configuration already present in Gradle and `build_product.py`. Extract the supplied key material only into the Git-ignored repository `certs/` directory, then compare Gradle's configured signing fingerprint with the certificate fingerprint embedded in a newly built release APK.

**Tech Stack:** PowerShell, 7-Zip, Gradle 8.7, Android build tools `apksigner`, JDK 17.

## Global Constraints

- The keystore and properties remain under `certs/` and must never be committed.
- Secret property values must not be printed in logs or command output.
- The build must use `assembleRelease`; a debug-signed APK is not an acceptable result.
- A certificate fingerprint mismatch rejects the APK.
- No source or release upload is part of this local signing-key setup.

---

### Task 1: Install and validate the office signing files

**Files:**
- Create locally, ignored: `certs/atsbot-release.jks`
- Create locally, ignored: `certs/atsbot-release.properties`
- Consume: `C:/Users/Admin/Downloads/certs.zip`

**Interfaces:**
- Consumes: archive containing the exact `certs/` directory.
- Produces: the two local paths expected by `android/app/build.gradle.kts` and `build_product.py`.

- [ ] **Step 1: Verify the expected files are currently absent or record their hashes if present**

```powershell
Get-Item certs/atsbot-release.jks,certs/atsbot-release.properties -ErrorAction SilentlyContinue |
    Get-FileHash -Algorithm SHA256
```

Expected: either no files, or hashes to compare before replacement.

- [ ] **Step 2: Extract the supplied archive into the repository root**

```powershell
& 'C:\Program Files\7-Zip\7z.exe' x 'C:\Users\Admin\Downloads\certs.zip' "-o$PWD" -y
```

Expected: both signing files are written under `certs/`.

- [ ] **Step 3: Validate structure without printing secrets**

```powershell
$required = 'storeFile','storePassword','keyAlias','keyPassword'
$names = Get-Content certs/atsbot-release.properties |
    Where-Object { $_ -match '^\s*[^#!][^=]*=' } |
    ForEach-Object { ($_ -split '=', 2)[0].Trim() }
$missing = $required | Where-Object { $_ -notin $names }
if ($missing) { throw "Missing signing properties: $($missing -join ', ')" }
if (-not (Test-Path certs/atsbot-release.jks)) { throw 'Missing keystore' }
```

Expected: exit 0 with no secret values printed.

- [ ] **Step 4: Prove Git ignores the key material**

```powershell
git check-ignore certs/atsbot-release.jks certs/atsbot-release.properties
git status --short
```

Expected: both paths are reported by `check-ignore`, and neither appears in `git status`.

---

### Task 2: Build and verify the signed release APK

**Files:**
- Consume: `android/app/build.gradle.kts`
- Generate: `android/app/build/outputs/apk/release/aTSBot-<version>-release.apk`

**Interfaces:**
- Consumes: local `certs/` files from Task 1 through Gradle signing config `atsRelease`.
- Produces: a release APK whose signer SHA-256 equals Gradle's `atsRelease` certificate SHA-256.

- [ ] **Step 1: Inspect Gradle signing configuration**

```powershell
Set-Location android
.\gradlew.bat signingReport
```

Expected: release variant uses config `atsRelease` and reports a SHA-256 fingerprint without a signing error.

- [ ] **Step 2: Build the release APK**

```powershell
$version = '1.1.' + (Get-Date -Format 'yyyyMMddHHmm')
.\gradlew.bat clean assembleRelease "-PatsVersion=$version"
```

Expected: `BUILD SUCCESSFUL` and `app/build/outputs/apk/release/aTSBot-$version-release.apk` exists.

- [ ] **Step 3: Verify the APK signature**

```powershell
$apk = Get-ChildItem app/build/outputs/apk/release/*-release.apk |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$sdk = (Get-Content local.properties | Where-Object { $_ -like 'sdk.dir=*' } | Select-Object -First 1) -replace '^sdk.dir=', '' -replace '\\\\', '\'
$apksigner = Get-ChildItem "$sdk\build-tools\*\apksigner.bat" |
    Sort-Object FullName -Descending | Select-Object -First 1
& $apksigner.FullName verify --verbose --print-certs $apk.FullName
```

Expected: verification succeeds and prints the APK signer SHA-256 certificate digest.

- [ ] **Step 4: Compare configured and embedded fingerprints**

```powershell
$report = .\gradlew.bat signingReport | Out-String
$gradleMatch = [regex]::Match(
    $report,
    '(?s)Variant:\s*release.*?Config:\s*atsRelease.*?SHA-256:\s*([0-9A-Fa-f:]+)'
)
if (-not $gradleMatch.Success) { throw 'Cannot read atsRelease SHA-256 from signingReport' }
$apkOutput = (& $apksigner.FullName verify --print-certs $apk.FullName) | Out-String
$apkMatch = [regex]::Match($apkOutput, 'Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f]+)')
if (-not $apkMatch.Success) { throw 'Cannot read APK signer SHA-256' }
$gradleSha = $gradleMatch.Groups[1].Value.Replace(':', '').ToUpperInvariant()
$apkSha = $apkMatch.Groups[1].Value.ToUpperInvariant()
if ($gradleSha -ne $apkSha) { throw "Signer mismatch: $gradleSha != $apkSha" }
"SIGNER_SHA256=$apkSha"
```

Expected: exact equality proves APKs built from this `certs.zip` use the office certificate and can upgrade one another.

- [ ] **Step 5: Verify no secret entered Git**

```powershell
Set-Location ..
git status --short --branch
git check-ignore certs/atsbot-release.jks certs/atsbot-release.properties
```

Expected: only the implementation-plan document may be tracked; both signing files remain ignored.

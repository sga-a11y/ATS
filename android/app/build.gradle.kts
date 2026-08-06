import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Version mac dinh tu sinh, nhung build_product.py se truyen -PatsVersion=<version>
// de EXE va APK dung CHUNG 1 version trong version.json.
val versionPrefix = "1.1"
fun nowVersion(): String = "$versionPrefix." + SimpleDateFormat("yyyyMMddHHmm", Locale.US).format(Date())
fun versionCodeFromVersion(version: String): Int? {
    val stamp = version.substringAfterLast(".")
    if (!Regex("""\d{12}""").matches(stamp)) return null
    return try {
        SimpleDateFormat("yyyyMMddHHmm", Locale.US).apply { isLenient = false }
            .parse(stamp)
            ?.let { (it.time / 60000L).toInt() }
    } catch (_: Exception) {
        null
    }
}
val requestedBuildVersion = (
    providers.gradleProperty("atsVersion").orNull
        ?: System.getenv("ATS_BUILD_VERSION")
        ?: ""
).trim()
val buildVersionName = requestedBuildVersion.ifEmpty { nowVersion() }
val buildVersionCode = (
    providers.gradleProperty("atsVersionCode").orNull?.toIntOrNull()
        ?: System.getenv("ATS_BUILD_VERSION_CODE")?.toIntOrNull()
        ?: versionCodeFromVersion(buildVersionName)
        ?: (System.currentTimeMillis() / 60000L).toInt()
)
val repositoryRoot = rootProject.projectDir.parentFile
val releaseSigningPropsFile = File(repositoryRoot, "certs/atsbot-release.properties")
val releaseSigningProps = Properties().also { props ->
    if (releaseSigningPropsFile.isFile) {
        releaseSigningPropsFile.inputStream().use(props::load)
    }
}
fun releaseSigningProp(name: String): String? =
    releaseSigningProps.getProperty(name)?.trim()?.takeIf { it.isNotEmpty() }

val releaseStorePath = releaseSigningProp("storeFile")
val releaseStoreFile = releaseStorePath?.let { path ->
    File(path).let { if (it.isAbsolute) it else File(repositoryRoot, path) }
}
val hasReleaseSigning = releaseStoreFile?.isFile == true &&
    releaseSigningProp("storePassword") != null &&
    releaseSigningProp("keyAlias") != null &&
    releaseSigningProp("keyPassword") != null

val generatedSmartNavAssets = layout.buildDirectory.dir("generated/smart-nav-assets")
val prepareSmartNavAssets by tasks.registering(Copy::class) {
    val worldNav = File(repositoryRoot, "world_nav.json")
    val ground = File(repositoryRoot, "gamedata/Ground.mmg")
    val sceneFight = File(repositoryRoot, "gamedata/SceneFight_C.dat")
    val trainMaps = File(repositoryRoot, "train_maps.json")
    inputs.files(worldNav, ground, sceneFight, trainMaps)
    doFirst {
        val missing = listOf(worldNav, ground, sceneFight, trainMaps).filterNot { it.isFile }
        check(missing.isEmpty()) {
            "Missing smart navigation assets: ${missing.joinToString { it.path }}"
        }
    }
    from(worldNav) { into("train_bot_data") }
    from(ground) { into("train_bot_data/gamedata") }
    from(sceneFight) { into("train_bot_data/gamedata") }
    from(trainMaps) { into("train_bot_data") }
    into(generatedSmartNavAssets)
}

android {
    namespace = "com.tsbot.android"
    compileSdk = 34
    ndkVersion = "26.3.11579264"

    defaultConfig {
        applicationId = "com.tsbot.android"
        minSdk = 26
        targetSdk = 34
        versionCode = buildVersionCode
        versionName = buildVersionName
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            // arm64/armeabi = dien thoai that; x86_64 = emulator PC (MuMu/LDPlayer) chay tren Intel/AMD
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
        externalNativeBuild {
            cmake {
                cppFlags += "-std=c++17"
            }
        }
    }

    signingConfigs {
        create("atsRelease") {
            if (hasReleaseSigning) {
                storeFile = releaseStoreFile
                storePassword = releaseSigningProp("storePassword")
                keyAlias = releaseSigningProp("keyAlias")
                keyPassword = releaseSigningProp("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            signingConfig = signingConfigs.getByName("atsRelease")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    // Dat ten file APK = aTSBot-<version>.apk (khop ten "aTSBot" ban PC, kem version timestamp)
    // thay vi app-debug.apk mac dinh.
    applicationVariants.all {
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl).outputFileName =
                "aTSBot-$buildVersionName-${buildType.name}.apk"
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    sourceSets.getByName("main").assets.srcDir(generatedSmartNavAssets)
}

tasks.named("preBuild").configure {
    dependsOn(prepareSmartNavAssets)
}

chaquopy {
    defaultConfig {
        buildPython("python")
        pyc {
            src = false
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.2")
    debugImplementation("androidx.compose.ui:ui-tooling")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}

import java.text.SimpleDateFormat
import java.util.Date

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Version TU SINH luc build, KHOP scheme ban PC (build_product.py: "1.1." + yyyyMMddHHmm).
// versionCode = so phut ke tu 1970 (tang dan moi build, ~29 trieu nam 2026 -> vua khit Int).
val buildVersionName = "1.1." + SimpleDateFormat("yyyyMMddHHmm").format(Date())
val buildVersionCode = (System.currentTimeMillis() / 60000L).toInt()
val repositoryRoot = rootProject.projectDir.parentFile
val generatedSmartNavAssets = layout.buildDirectory.dir("generated/smart-nav-assets")
val prepareSmartNavAssets by tasks.registering(Copy::class) {
    val worldNav = File(repositoryRoot, "world_nav.json")
    val ground = File(repositoryRoot, "gamedata/Ground.mmg")
    val trainMaps = File(repositoryRoot, "train_maps.json")
    inputs.files(worldNav, ground, trainMaps)
    doFirst {
        val missing = listOf(worldNav, ground, trainMaps).filterNot { it.isFile }
        check(missing.isEmpty()) {
            "Missing smart navigation assets: ${missing.joinToString { it.path }}"
        }
    }
    from(worldNav) { into("train_bot_data") }
    from(ground) { into("train_bot_data/gamedata") }
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

    buildTypes {
        release {
            isMinifyEnabled = true
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

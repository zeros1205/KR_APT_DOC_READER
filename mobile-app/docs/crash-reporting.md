# 크래시 리포팅 (Firebase Crashlytics)

앱의 치명적 크래시 / 비치명적(non-fatal) JS 오류를 Firebase Crashlytics 로 수집한다.
기존 FCM 푸시가 쓰던 **동일한 Firebase 프로젝트 / 동일한 설정 파일**을 그대로 재사용하므로
별도의 벤더·시크릿이 필요 없다.

## 무엇이 추가됐나

| 레이어 | 변경 |
| --- | --- |
| JS | `@capacitor-firebase/crashlytics` 의존성, `src/crash.ts` 래퍼, `src/ErrorBoundary.tsx` |
| JS | 부팅 시 `initCrashReporting()` 호출(`src/App.tsx`), 설정에 옵트아웃 토글 |
| Android | `firebase-crashlytics-gradle` classpath(root), `firebase-crashlytics` 의존성 + 플러그인 조건부 apply(app) |
| iOS | Podfile 에 `CapacitorFirebaseCrashlytics` pod (podspec 이 `FirebaseCrashlytics ~> 11.7` 를 끌어옴) |

### 동작 모델
- **네이티브에서만** 동작한다. 웹(`vite dev`/`vite preview`)에서는 `src/crash.ts` 가 전부 no-op.
- Firebase 설정 파일이 없는 빌드에서는 네이티브 호출이 조용히 무시된다(앱은 정상 동작).
  - Android: `app/build.gradle` 이 `google-services.json` 존재 시에만 두 플러그인을 apply.
  - iOS: `AppDelegate.swift` 가 `GoogleService-Info.plist` 존재 시에만 `FirebaseApp.configure()`.
- `window.onerror` / `unhandledrejection` / React `ErrorBoundary` 에서 잡힌 오류는
  **비치명적 예외**로 보고된다(앱을 죽이지 않음).

## 사용자 동의 / 개인정보

- 설정 화면의 **"진단 데이터 보내기"** 토글로 사용자가 끌 수 있다(`UserSettings.crashReportingEnabled`).
- 기본값은 **ON** (기존 AdMob 동의 정책과 일관). 기존 사용자(필드 미존재)는 ON 으로 간주하며,
  명시적으로 `false` 일 때만 수집을 끈다.
- 토글을 끄면 `FirebaseCrashlytics.setEnabled({ enabled: false })` 가 호출되어 이후 수집이 중단된다.

> ⚠️ **출시 전 운영자 체크리스트**
> - Google Play **데이터 안전성(Data Safety)** 양식에 "앱 활동/진단(크래시 로그, 기기 식별자)" 수집을 신고.
> - Apple **App Privacy** 항목에 동일 내용 신고(통상 "Diagnostics" → "Crash Data").
> - `https://apt-note.com/privacy.html` 개인정보 처리방침에 크래시 진단 데이터 수집·목적을 추가.

## Android 메모

- 릴리스 빌드에 이미 `ndk { debugSymbolLevel 'FULL' }` 가 있어 네이티브 심볼이 AAB 에 포함된다.
- 현재 `minifyEnabled false` 라 R8 난독화 매핑이 없으므로 Java/Kotlin 스택은 그대로 읽힌다.
  추후 minify 를 켜면 Crashlytics Gradle 플러그인이 mapping 업로드를 자동 처리한다.

## iOS 메모 — dSYM 업로드 (심볼리케이션)

JS/Capacitor 레벨 크래시는 별도 작업 없이 보고된다. **네이티브 크래시 스택을 사람이 읽는
함수명으로 심볼리케이션**하려면 dSYM 을 Crashlytics 에 업로드해야 한다. 두 가지 방법:

1. **빌드 단계(run script)** — Xcode `App` 타깃에 Run Script Phase 추가:
   ```
   "${PODS_ROOT}/FirebaseCrashlytics/run"
   ```
   Input Files:
   ```
   ${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}/Contents/Resources/DWARF/${TARGET_NAME}
   $(SRCROOT)/$(BUILT_PRODUCTS_DIR)/$(INFOPLIST_PATH)
   ```
2. **CI 업로드 스크립트** — 빌드 산출 dSYM 을 다음으로 업로드:
   ```
   "${PODS_ROOT}/FirebaseCrashlytics/upload-symbols" -gsp GoogleService-Info.plist -p ios <dSYM 경로>
   ```

> 이 run-script 단계는 `ios/App/App.xcodeproj/project.pbxproj` 수정이 필요하며,
> 잘못 건드리면 빌드가 깨질 수 있어 이 PR 에서는 자동화하지 않았다. 운영자가 Xcode 또는
> CI 워크플로우에서 위 절차를 한 번 적용하면 된다.

## 코드에서 쓰는 법

```ts
import { recordError, logCrashBreadcrumb } from "./crash";

logCrashBreadcrumb("결제 화면 진입");
try {
  await doSomething();
} catch (e) {
  await recordError(e, { screen: "checkout", noticeId });
}
```

이미 swallow 되던 `catch {}` 들은 그대로 두되, 진단 가치가 있는 지점에 점진적으로
`recordError(e, {...})` 를 끼워 넣으면 된다.

## 통합 검증

1. CI 시크릿(`GOOGLE_SERVICES_JSON_BASE64`, iOS `GoogleService-Info.plist`)이 설정된 빌드를 설치.
2. 설정 → "진단 데이터 보내기" 가 켜져 있는지 확인.
3. 테스트용으로만 `forceCrashForTest()`(`src/crash.ts`) 를 임시 버튼/콘솔에서 호출 →
   앱 종료 후 재실행 → Firebase Console → Crashlytics 에 약 수 분 내 리포트가 뜨는지 확인.
   **검증 후 강제 크래시 호출은 반드시 제거**한다.

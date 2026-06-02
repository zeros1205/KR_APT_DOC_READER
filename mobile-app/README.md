# 정과장의 청약노트 모바일 앱

Capacitor 기반 iOS/Android 앱 shell 초안입니다. 웹 콘텐츠는 `https://apt-note.com`의 `posts_index.json`과 상세 포스트 URL을 그대로 사용하고, 앱 고유 기능은 로컬 저장소 중심으로 둡니다.

## 포함 범위

- 최신 공고 목록 로딩
- 지역 탭과 검색
- 상세 포스트 웹 URL 열기
- 로컬 즐겨찾기 저장/삭제
- 관심지역 저장
- 푸시 알림 ON/OFF 설정 진입
- 조용한 시간 기본 ON
- 진단 데이터(크래시 리포트) 수집 ON/OFF (기본 ON, 옵트아웃 가능)
- 개인정보 보호정책/이용약관 열기
- 웹 URL 공유

## 실행

```bash
cd mobile-app
npm ci
npm run dev
```

프로덕션 웹 셸 빌드:

```bash
npm run build
```

네이티브 프로젝트 동기화:

```bash
npm run build
npx cap sync
```

Android debug 빌드:

```bash
cd android
./gradlew assembleDebug --no-daemon
```

## 웹 데이터 동기화 방식

앱은 공고 데이터를 앱 번들에 복사하지 않고 `https://apt-note.com/posts_index.json`을 직접 읽습니다.
따라서 GitHub 워크플로우가 웹 프런트 데이터를 갱신해 배포하면 앱 목록도 다음 새로고침 시 최신 데이터로 반영됩니다.

- 웹 공고 데이터 변경: 앱 재빌드 불필요
- 앱 UI/기능 변경: `mobile-app` 빌드 검증 워크플로우 실행
- Android/iOS 네이티브 프로젝트 변경: `npx cap sync` 후 네이티브 빌드 검증

## GitHub Actions

`.github/workflows/codex-mobile-app.yml`이 모바일앱 변경을 검증합니다.

- 실행 조건: `mobile-app/**` 변경 PR, `main` push, 수동 실행
- 검증 단계: `npm ci` → `npm run build` → `npx cap sync android` → `./gradlew assembleDebug --no-daemon`
- 커밋 대상: 앱 소스와 네이티브 프로젝트 설정
- 제외 대상: `node_modules/`, `dist/`, Android build/cache, Capacitor generated assets

## AdMob

`src/admob.ts` 가 `@capacitor-community/admob` 을 동적 import 로 감싸 iOS/Android 공통으로 배너를 띄웁니다.

- 배너 표시 시점 (2026-05 정책):
  - **메인(home) / 상세(detail) / 인트로 / 온보딩**: 광고 없음 (초기 retention 보호)
  - 즐겨찾기 — 항목 있음: ADAPTIVE_BANNER 하단 sticky
  - 즐겨찾기 — 빈 화면 / 설정: MEDIUM_RECTANGLE(300x250) 하단 큰 광고로 교체
- SDK banner view 는 1 개만 다루므로 모든 전환은 `setBannerMode("adaptive"|"mrec-center"|"mrec-bottom"|"none")` 단일 API 로 순차 처리
- 종료 다이얼로그 (Android 백버튼 전용): home 뷰에서 시스템 백버튼 누르면 표시. 화면 중앙에 Medium Rectangle (300x250) 광고 노출 + "돌아가기" / "앱 종료하기" 버튼. iOS 는 시스템 백버튼이 없어 트리거되지 않음.
- 앱 오프닝 광고: 콜드 스타트 직후 (인트로 사라진 뒤 800ms) + foreground 복귀 시. 직전 표시로부터 4 시간 룰
- 전면 광고: 상세 페이지 진입 카운터가 10 의 배수 + 직전 광고로부터 30 분 경과 시 1 회. 청약Home 외부 링크 카드는 카운터 미증가
- 광고 단위 ID 우선순위: `.env` 의 `VITE_ADMOB_*_ID_*` → `src/admob.ts` 상단의 `PRODUCTION_*` 상수 → Google 공개 테스트 ID
  - iOS 하단 배너: `ca-app-pub-8234120897033274/2306903637`
  - iOS Medium Rectangle (종료 다이얼로그): `ca-app-pub-8234120897033274/1061800806` (네이티브 광고 고급형)
  - iOS 전면 광고: `ca-app-pub-8234120897033274/3304820769`
  - iOS 앱 오프닝: `ca-app-pub-8234120897033274/6142737093`
- iOS 앱 ID: `ios/App/App/Info.plist` 의 `GADApplicationIdentifier` 키에 직접 명시 (`ca-app-pub-8234120897033274~4486344416`)
- Android 앱 ID: `android/app/src/main/AndroidManifest.xml` 의 `com.google.android.gms.ads.APPLICATION_ID` meta-data 에 직접 명시 (`ca-app-pub-8234120897033274~3125849648`). **이 meta-data 가 없으면 Google Mobile Ads SDK 의 ContentProvider 가 앱 시작 시점에 IllegalStateException 으로 즉시 크래시함.**
- ATT(App Tracking Transparency): iOS 14.5+ 에서 마운트 시 1 회 요청, 거부 시 비추적 광고로 자동 폴백
- `VITE_ADMOB_USE_TEST=true` 또는 dev 빌드면 강제로 Google 공개 테스트 광고 사용

iOS 빌드 흐름:

```bash
cd mobile-app
npm ci
npm run build
npx cap sync ios        # Podfile 갱신 + Google Mobile Ads SDK 설치
cd ios/App && pod install
npx cap open ios        # Xcode 에서 archive
```

## 크래시 리포팅 (Firebase Crashlytics)

`src/crash.ts` 가 `@capacitor-firebase/crashlytics` 를 동적 import 로 감싸 치명적 크래시 +
비치명적(non-fatal) JS 오류를 수집합니다. FCM 푸시와 **동일한 Firebase 프로젝트·설정 파일**
(`google-services.json` / `GoogleService-Info.plist`)을 재사용하므로 별도 시크릿이 없습니다.

- **네이티브에서만** 동작 (웹은 전부 no-op), Firebase 설정 파일이 없는 빌드에서는 조용히 무시
- `window.onerror` / `unhandledrejection` / React `ErrorBoundary`(`src/ErrorBoundary.tsx`)에서
  잡힌 오류를 비치명적으로 보고
- 설정 화면 **"진단 데이터 보내기"** 토글로 사용자가 끌 수 있음 (`UserSettings.crashReportingEnabled`, 기본 ON)
- Android: `firebase-crashlytics-gradle` 플러그인을 `google-services` 와 함께 **조건부** apply
- iOS: Podfile 에 `CapacitorFirebaseCrashlytics` pod (podspec 이 `FirebaseCrashlytics ~> 11.7` 동반)

> 출시 전 운영자 작업(개인정보 고지, iOS dSYM 업로드 등)과 검증 절차는 **`docs/crash-reporting.md`** 참고.

## 출시 버전 게시 흐름 (app-version.json)

설정 화면의 "현재 X · 최신 Y · 업데이트" 표기에서 **최신 Y**는 `https://apt-note.com/app-version.json` 한 파일이 결정합니다. 이 파일은 **사용자가 실제로 스토어에서 받을 수 있는 버전**만 가리켜야 합니다. 빌드만 끝났거나 심사 중인 버전을 가리키면 사용자에게 "받을 수 없는 업데이트" 가 보이고, 다운그레이드 광고로도 이어집니다.

규칙은 한 가지: `output/app-version.json`은 **`mobile-app-publish-version.yml` 워크플로만** 변경합니다. 빌드 워크플로(`mobile-app-play-release.yml`, `mobile-app-ios-release.yml`)는 더 이상 이 파일을 건드리지 않습니다.

권장 흐름:
1. 빌드 워크플로로 AAB / IPA 산출 → 스토어 업로드
2. Play 콘솔 / App Store Connect에서 출시 절차 진행
3. 스토어 승인이 떨어지면(앱이 실제 설치 가능 상태일 때) `mobile-app-publish-version.yml` 을 **수동 실행**:
   - `platform`: ios / android / both (각 스토어 심사 속도가 다르므로 보통 따로 실행)
   - `mode=auto` (기본): 스토어 API에서 **현재 라이브 버전을 자동 감지** — 버전 입력 불필요
   - `mode=manual`: API 우회. 긴급용 escape hatch. 이때만 `*_version_name` 입력 필요

판정 기준 (auto 모드):
- iOS: App Store Connect 에서 `appStoreState == READY_FOR_SALE` 인 가장 최신 iOS appStoreVersion
- Android: Play `production` 트랙에서 `status == "completed"` 인 가장 최신 release (단계적 출시 도중인 `inProgress` 는 라이브로 보지 않음)
- 라이브 버전이 아직 없으면 워크플로가 exit 2 로 실패 → 출시가 끝나면 다시 실행

App.tsx 의 비교는 semver(`compareVersions`)로 처리하므로, 잘못된 형식·동일·다운그레이드는 모두 "업데이트 없음"으로 안전하게 떨어집니다.

### 필요한 GitHub 시크릿
- iOS: `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_KEY_BASE64` (TestFlight 업로드와 공유)
- Android: `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` (Play Developer API 전용. Google Cloud에서 서비스 계정 → JSON 키 생성 후, Play Console "사용자 및 권한"에서 해당 서비스 계정 이메일 초대)

### Play 자동 업로드 (선택)

`mobile-app-play-release.yml` 의 `upload_to_play=true` 입력으로 빌드한 AAB를 Play Console 테스트 트랙에 자동 업로드합니다 (iOS의 `upload_to_testflight` 와 대칭).

- `play_track`: `internal` (기본) / `alpha` / `beta` 중 선택. 프로덕션 자동 출시는 의도적으로 제외 — 프로덕션은 Play Console 에서 직접 promote.
- 자동 업로드를 쓰려면 위 서비스 계정의 Play Console 앱 권한에 **"테스트 트랙으로 출시 (Release to testing tracks)"** 가 추가로 체크되어 있어야 합니다. 조회만 할거면 "앱 정보 및 보고서 보기" 만으로 충분.
- versionCode 가 직전 트랙 빌드보다 커야 함 (워크플로 입력 `version_code` 그대로 사용).

## 다음 구현 지점

- ~~Firebase 프로젝트 연결 및 FCM/APNs 토큰 등록~~ (완료 — FCM + Crashlytics)
- GitHub Actions 신규 공고 감지 워크플로우와 푸시 발송 서버 구성
- 앱 아이콘/스플래시 자산 연결
- iOS Bundle ID와 Android Package Name 확정
- TestFlight/Play 내부 테스트 설정

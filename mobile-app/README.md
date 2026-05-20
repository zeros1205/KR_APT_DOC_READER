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

- 배너 표시 시점: 인트로/온보딩/상세/종료 다이얼로그를 제외한 home / favorites / settings 뷰
- 종료 다이얼로그 (Android 백버튼 전용): home 뷰에서 시스템 백버튼 누르면 표시. 화면 중앙에 Medium Rectangle (300x250) 광고 노출 + "돌아가기" / "앱 종료하기" 버튼. iOS 는 시스템 백버튼이 없어 트리거되지 않음.
- 앱 오프닝 광고: 콜드 스타트 직후 (인트로 사라진 뒤 800ms) + foreground 복귀 시. 직전 표시로부터 4 시간 룰
- 전면 광고: 상세 페이지 진입 카운터가 10 의 배수 + 직전 광고로부터 30 분 경과 시 1 회. 청약Home 외부 링크 카드는 카운터 미증가
- 광고 단위 ID 우선순위: `.env` 의 `VITE_ADMOB_*_ID_*` → `src/admob.ts` 상단의 `PRODUCTION_*` 상수 → Google 공개 테스트 ID
  - iOS 하단 배너: `ca-app-pub-8234120897033274/2306903637`
  - iOS Medium Rectangle (종료 다이얼로그): `ca-app-pub-8234120897033274/1061800806` (네이티브 광고 고급형)
  - iOS 전면 광고: `ca-app-pub-8234120897033274/3304820769`
  - iOS 앱 오프닝: `ca-app-pub-8234120897033274/6142737093`
- iOS 앱 ID: `ios/App/App/Info.plist` 의 `GADApplicationIdentifier` 키에 직접 명시 (`ca-app-pub-8234120897033274~4486344416`)
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

## 다음 구현 지점

- Firebase 프로젝트 연결 및 FCM/APNs 토큰 등록
- GitHub Actions 신규 공고 감지 워크플로우와 푸시 발송 서버 구성
- 앱 아이콘/스플래시 자산 연결
- iOS Bundle ID와 Android Package Name 확정
- TestFlight/Play 내부 테스트 설정

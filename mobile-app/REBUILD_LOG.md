# Mobile App Rebuild Log

This file exists to trigger the `Build Signed Mobile App for Play` workflow
(it runs on pushes to `main` that touch `mobile-app/**`). Each entry records
why a fresh signed build was kicked off. It does not affect app behavior.

## 2026-06-02 — Firebase Crashlytics 통합
- 목적: 크래시/비치명적 오류 가시화. 기존 FCM 과 동일한 Firebase 프로젝트·설정 재사용.
- 변경: `@capacitor-firebase/crashlytics` 추가, `src/crash.ts`/`src/ErrorBoundary.tsx`,
  Android Gradle(조건부 plugin apply) + iOS Podfile pod, 설정에 "진단 데이터 보내기" 옵트아웃 토글.
- 검증 필요: 설정 시크릿이 주입된 릴리스 빌드에서 Crashlytics 리포트 수신.
  iOS 네이티브 dSYM 업로드 run-script 는 `docs/crash-reporting.md` 참고(이 PR 미포함).
- 빌드 소스: 본 PR HEAD.

## 2026-05-30 — splash 잔류 수정 검증 빌드
- 목적: #158(`EdgeToEdge.enable()` 제거로 스플래시 후 상단 오렌지 블록 잔류 회귀
  수정 + 구버전 빌딩 로고 흔적 제거)이 반영된 새 APK 를 폰에 설치해 육안 검증.
- 빌드 소스: `main` HEAD (스플래시 수정 포함).
- 버전: 자동(push) 빌드이므로 versionName=0.1.0, versionCode=run_number.
  사이드로드 업그레이드 설치엔 영향 없음(코드가 항상 증가).
- Play 업로드 없음(아티팩트 APK 다운로드 → 수동 설치).

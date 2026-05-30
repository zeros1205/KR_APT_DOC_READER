# Mobile App Rebuild Log

This file exists to trigger the `Build Signed Mobile App for Play` workflow
(it runs on pushes to `main` that touch `mobile-app/**`). Each entry records
why a fresh signed build was kicked off. It does not affect app behavior.

## 2026-05-30 — splash 잔류 수정 검증 빌드
- 목적: #158(`EdgeToEdge.enable()` 제거로 스플래시 후 상단 오렌지 블록 잔류 회귀
  수정 + 구버전 빌딩 로고 흔적 제거)이 반영된 새 APK 를 폰에 설치해 육안 검증.
- 빌드 소스: `main` HEAD (스플래시 수정 포함).
- 버전: 자동(push) 빌드이므로 versionName=0.1.0, versionCode=run_number.
  사이드로드 업그레이드 설치엔 영향 없음(코드가 항상 증가).
- Play 업로드 없음(아티팩트 APK 다운로드 → 수동 설치).

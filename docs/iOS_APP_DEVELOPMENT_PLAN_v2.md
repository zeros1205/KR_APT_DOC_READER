# iOS 앱 개발 계획 v2.0 (수정: 기존 Capacitor 앱 재사용)

> **프로젝트**: PROJECT BALI iOS 앱  
> **작성일**: 2026-05-13  
> **개발 방식**: 1인 개발 + 기존 React 웹앱 재사용  
> **핵심**: Android 앱과 99% 동일한 코드로 iOS 배포

---

## 📊 현황 분석

### 기존 앱 현황
- **기술 스택**: React 19 + TypeScript + Capacitor 7
- **빌드 도구**: Vite
- **상태 관리**: React Context API
- **저장소**: Capacitor Preferences (네이티브 저장소)
- **푸시 알림**: Capacitor Push Notifications 플러그인
- **배포**: Android는 Google Play Store 완료

### 재사용 가능한 코드
```
mobile-app/
├── src/
│   ├── App.tsx               ✅ 그대로 재사용
│   ├── api.ts                ✅ 그대로 재사용
│   ├── types.ts              ✅ 그대로 재사용
│   ├── storage.ts            ✅ 그대로 재사용
│   ├── usePullToRefresh.ts   ✅ 그대로 재사용
│   └── main.tsx              ✅ 그대로 재사용
├── capacitor.config.ts       ✅ iOS 플러그인 설정만 추가
├── package.json              ✅ 그대로 사용
└── index.html                ✅ 그대로 사용
```

**코드 재사용율: 99%** 🎉

---

## 🚀 iOS 배포 전략 (1인 개발, 2~3주)

### Phase 0: 준비 (1주, 5일)

#### 0.1 Apple Developer 계정 설정
- [ ] Apple Developer Program 가입 ($99/년)
- [ ] App ID 생성 (`app.aptnote.mobile`)
- [ ] Certificates, Identifiers & Profiles 설정
  - Development Certificate
  - Distribution Certificate (App Store)
  - Provisioning Profiles (Development + Distribution)
- [ ] App Store Connect 앱 등록

#### 0.2 로컬 환경 구성
```bash
# Mac 필수
- Xcode 15+ (App Store에서 다운로드)
- CocoaPods (`sudo gem install cocoapods`)
- Capacitor CLI (`npm install -g @capacitor/cli`)

# 확인
xcode-select --install
pod repo update
```

#### 0.3 Capacitor iOS 플랫폼 추가
```bash
cd mobile-app
npm run build                    # React 빌드
npx cap add ios                  # iOS 플랫폼 추가 (~5분)
npx cap sync                     # 동기화
```

**결과**: `mobile-app/ios/` 디렉토리 자동 생성

### Phase 1: iOS 빌드 & 테스트 (1주, 5일)

#### 1.1 Xcode 프로젝트 열기
```bash
npx cap open ios  # Xcode 자동 실행
```

#### 1.2 빌드 설정 확인
- **Product** → **Scheme** → **App** 선택
- **Project Settings**
  - Team: Apple Developer Account 선택
  - Bundle Identifier: `app.aptnote.mobile`
  - Version: `1.0.0`
  - Build: `1`
  - Deployment Target: iOS 16.0

#### 1.3 시뮬레이터에서 테스트
```bash
# Xcode에서 시뮬레이터 선택 (iPhone 15 Pro)
⌘ + B  # 빌드
⌘ + R  # 실행
```

**테스트 항목**:
- ✅ 공고 목록 조회
- ✅ 무한 스크롤
- ✅ Pull-to-Refresh
- ✅ 찜하기 (로컬 저장)
- ✅ 검색
- ✅ 지역 필터
- ✅ 상세 페이지 (웹뷰)
- ✅ 설정 페이지

#### 1.4 실제 기기에서 테스트
```bash
# iPhone 연결 후
- Signing & Capabilities에서 Development Team 설정
- ⌘ + R 실행
```

### Phase 2: TestFlight 배포 (1주, 5일)

#### 2.1 빌드 서명 설정 (Distribution)
- **Xcode** → **Product** → **Build For** → **Any iOS Device (arm64)**
- **Window** → **Organizer**
- Archives 탭에서 최신 빌드 선택
- **Distribute App** → **App Store Connect**
- **Automatically manage signing** 확인

#### 2.2 App Store Connect 설정
- [App Store Connect](https://appstoreconnect.apple.com/)
- **App Information**
  - 앱명: 정과장의 청약노트
  - 부제: 분양공고 한눈에 보기
  - 카테고리: Lifestyle
  - 라이선스: 무료
  
- **Screenshots & Preview** (필수)
  - iPhone 6.7"(최소 2장, 최대 10장)
  - 각 스크린샷에 설명 텍스트 추가
  
- **App Preview** (선택)
  - 30초 동영상 (선택사항)

- **Description**
  - 150자: "청약홈 분양공고를 모바일에서 쉽게 열람하세요"
  - 4000자: 기능 상세 설명
  
- **Privacy**
  - 개인정보 보호정책 URL 등록
  - 수집하는 사용자 데이터 항목 (최소)

- **Rating**
  - 콘텐츠 등급 (일반적)
  
- **Version Release**
  - 자동 릴리스 or 수동 승인 선택

#### 2.3 TestFlight에 빌드 업로드
```bash
# Xcode Organizer에서
- Distribute App 클릭
- App Store Connect 선택
- 자동 서명 + 업로드
```

**대기 시간**: ~15분 (빌드 처리)

#### 2.4 TestFlight 초대
- App Store Connect에서 Internal Testing 탭
- Testers 추가 (최대 100명 내부 테스터)
- Build 선택 후 검토 전 테스트

**테스트 기간**: 최소 48시간

### Phase 3: App Store 출시 (3~5일)

#### 3.1 심사 제출
- App Store Connect → **Prepare for Submission**
- 모든 필수 항목 완료 확인
- **Submit for Review** 클릭

**심사 기준 (주요)**:
- ✅ 개인정보 보호정책 명시
- ✅ 명확한 기능 설명
- ✅ 스크린샷 품질 (해상도 1242×2208px)
- ✅ 앱 아이콘 (1024×1024px)
- ✅ 마케팅 텍스트 정확성
- ❌ 과도한 광고 또는 외부 링크

#### 3.2 심사 진행
- **In Review**: 대기 중 (보통 24~48시간)
- **Pending Developer Release**: 심사 통과 (수동 릴리스 대기)
- **Ready for Sale**: 공개 (자동 또는 수동 선택)

**심사 거부 시 대응**:
- Apple의 거부 사유 확인
- 수정 후 Re-submit (횟수 제한 없음)

#### 3.3 출시!
```
Version 1.0.0
- iOS 16+ 지원
- 공고 목록, 찜하기, 검색 기능
- 오프라인 캐싱
- APNs 푸시 알림 대비
```

---

## 📋 상세 체크리스트

### Pre-Launch (Phase 0~1)
- [ ] Apple Developer 계정 가입 ($99)
- [ ] Xcode 15+ 설치
- [ ] `npx cap add ios` 실행
- [ ] 시뮬레이터에서 전체 기능 테스트
- [ ] 실제 기기 (iPhone) 테스트

### TestFlight (Phase 2)
- [ ] App Store Connect 앱 등록
- [ ] 스크린샷 5장 준비 (1242×2208px)
- [ ] 앱 아이콘 (1024×1024px)
- [ ] 마케팅 텍스트 작성
- [ ] 개인정보 보호정책 URL 준비
- [ ] 빌드 업로드 및 TestFlight 배포
- [ ] 내부 테스트 48시간 이상

### App Store (Phase 3)
- [ ] 심사 제출
- [ ] 심사 통과 대기 (24~48시간)
- [ ] 수동 릴리스 또는 자동 공개
- [ ] 출시 후 모니터링 (크래시, 리뷰)

---

## 🔧 주요 설정 항목

### Capacitor iOS 플러그인 활성화

#### Push Notifications (푸시 알림)
```typescript
// capacitor.config.ts
plugins: {
  PushNotifications: {
    presentationOptions: ["badge", "sound", "alert"]
  }
}
```

**필수**: Apple Push Notification Certificate (.p8 파일)
- App Store Connect → Certificates, Identifiers & Profiles
- Keys 탭 → Apple Push Notification service (APNs) 인증서 생성

#### Splash Screen
```typescript
plugins: {
  SplashScreen: {
    launchAutoHide: true
  }
}
```

### Xcode Signing (중요!)

**Automatic Signing** (권장):
- Xcode → Project → Signing & Capabilities
- ☑ Automatically manage signing
- ☑ Enable automatic signing
- Team 선택

**Manual Signing** (고급):
- Provisioning Profile 직접 관리
- 엔터프라이즈 배포 시 필요

---

## 📦 배포 체크리스트

### 아이콘 & 스크린샷
```
App Icon: 1024 × 1024 px (PNG, RGB)
  └─ Xcode 자동 변환 (App Store: 512×512, App: 120×120 등)

iPhone Screenshots (최소 2장, 최대 10장):
  - 6.7" (iPhone 15 Pro Max): 1242 × 2688 px
  - 6.1" (iPhone 15 Pro): 1170 × 2532 px
  - 5.8" (iPhone 14): 1125 × 2436 px

Design Tool: Figma 또는 Sketch
```

### 마케팅 텍스트
```
Subtitle (30자 이내):
"분양공고 한눈에 보기"

Description (4000자 이내):
• 청약홈 최신 분양공고 자동 수집
• 지역별 필터링 및 검색
• 관심공고 찜하기 및 비교
• 오프라인 캐싱 지원
• APNs 푸시 알림

Keywords (100자 이내):
아파트, 분양, 청약, 공고, 부동산
```

### 개인정보 보호정책
```
필수 포함 항목:
- 수집되는 정보: 없음 (로컬 저장만)
- 제3자 공유: 없음
- 데이터 삭제: 사용자가 앱 삭제 시 모두 삭제
- 보안: HTTPS 사용

예시:
https://apt-note.com/privacy.html
```

---

## ⏱️ 예상 일정

| Phase | 기간 | 작업 | 담당 |
|-------|------|------|------|
| **0** | 1주 | Apple 계정, Xcode, 환경 설정 | 1인 |
| **1** | 1주 | iOS 빌드, 시뮬레이터/기기 테스트 | 1인 |
| **2** | 1주 | TestFlight 배포, 내부 테스트 | 1인 |
| **3** | 3~5일 | App Store 심사 및 출시 | 자동 |
| **총** | **2.5~3주** | iOS v1.0.0 공개 | 1인 |

**비교**:
- 기존 계획: 8개월, 4~6명
- **신규 계획: 2.5주, 1인** 🚀

---

## 💰 비용 분석

| 항목 | 비용 | 비고 |
|------|------|------|
| Apple Developer Program | $99/년 | 필수 |
| Mac (이미 보유) | $0 | 기존 장비 활용 |
| Xcode | 무료 | App Store |
| 개발 도구 | 무료 | Capacitor, Vite 오픈소스 |
| **총** | **$99/년** | |

---

## 🎯 MVP 기능 (1.0.0)

### 포함 ✅
1. 공고 목록 조회 (posts_index.json)
2. 무한 스크롤 페이지네이션
3. Pull-to-Refresh
4. 지역별 필터링 (8개 지역)
5. 공고명 검색
6. 찜하기 (SQLite)
7. 찜 목록 조회
8. 상세 페이지 (웹뷰)
9. 설정 (관심지역, 알림 ON/OFF)
10. 오프라인 캐싱

### 제외 ❌ (v1.1 이후)
- 비교 기능
- 고급 필터링
- 푸시 알림 (준비만 함)
- 사용자 계정

---

## 🛠️ 문제 해결

### 일반적인 이슈

#### 1. Capacitor iOS 빌드 실패
```bash
# 해결 방법
rm -rf ios/
npm run build
npx cap add ios
npx cap sync
```

#### 2. Signing 오류
```
Xcode → Project → Signing & Capabilities
→ ☑ Automatically manage signing
→ Team 재선택
```

#### 3. Pod 의존성 오류
```bash
cd ios/App
pod repo update
pod install --repo-update
```

#### 4. 웹뷰 로딩 느림
```typescript
// 기존 캐싱 정책 유지
// API 응답 캐싱 (max-age 헤더)
// 이미지 최적화 (WebP, lazy loading)
```

---

## 📈 Post-Launch (Phase 4+)

### v1.1 (3주 후)
- 비교 기능 (최대 3개 동시)
- 고급 필터링 (가격, 공급유형, 일자)
- Firebase Analytics 연동

### v1.2 (6주 후)
- APNs 푸시 알림 활성화
- 알림 히스토리
- A/B 테스트

### v1.3+ (지속적)
- Dark Mode 지원
- 다국어 지원 (영어, 중국어)
- iPad 최적화

---

## 🔑 성공 지표

- ✅ **2.5주 내 App Store 출시**
- ✅ **Android와 동일한 기능 (코드 재사용)**
- ✅ **1인 개발로 완성**
- ✅ **$99 최소 비용**

---

## 📚 참고 자료

**Apple 공식 문서**:
- [App Store Connect Help](https://help.apple.com/app-store-connect/)
- [Xcode Help](https://help.apple.com/xcode/)
- [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

**Capacitor 공식 문서**:
- [Capacitor iOS Guide](https://capacitorjs.com/docs/ios)
- [Capacitor Plugins](https://capacitorjs.com/docs/plugins)

**개발 팁**:
- TestFlight은 심사 없이 48시간 내 배포 (빠른 반복 가능)
- 심사 통과율: ~95% (정책 준수 시)
- 심사 소요시간: 평균 24~48시간

---

## 다음 단계

1. **즉시** (오늘)
   - [ ] Apple Developer 계정 가입
   - [ ] Xcode 설치
   
2. **이번 주**
   - [ ] `npx cap add ios` 실행
   - [ ] 시뮬레이터에서 기본 테스트
   
3. **다음 주**
   - [ ] 실제 기기 테스트
   - [ ] App Store Connect 앱 등록
   - [ ] 스크린샷 및 마케팅 텍스트 준비
   
4. **2주 후**
   - [ ] TestFlight 배포
   - [ ] 내부 테스트 (48시간)
   
5. **3주 후**
   - [ ] App Store 심사 제출
   - [ ] 출시!

---

**이 계획은 1인 개발자가 2.5~3주 내에 iOS v1.0.0을 App Store에 출시할 수 있도록 설계되었습니다.**

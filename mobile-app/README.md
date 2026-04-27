# apt-note Mobile App (Capacitor + React)

애플리케이션 청약홈 공공데이터 기반 아파트 분양공고 정보를 iOS/Android에서 제공하는 모바일 앱입니다.

## 프로젝트 구조

```
mobile-app/
├── src/
│   ├── components/          # 재사용 가능한 UI 컴포넌트
│   ├── screens/             # 앱 화면 (OnboardingScreen, HomeScreen, 등)
│   │   ├── OnboardingScreen.tsx
│   │   ├── HomeScreen.tsx
│   │   ├── FavoritesScreen.tsx
│   │   └── SettingsScreen.tsx
│   ├── services/            # 비즈니스 로직
│   │   ├── apiService.ts    # 백엔드 API 통신
│   │   ├── storageService.ts # 로컬 저장소 (Capacitor Storage)
│   │   ├── notificationService.ts # FCM/로컬 알림
│   │   └── cacheService.ts  # 오프라인 캐싱
│   ├── styles/
│   │   ├── themes.ts        # 색상 팔레트 (A, B, C)
│   │   └── index.css        # 글로벌 스타일
│   ├── types/               # TypeScript 타입 정의
│   ├── hooks/               # 커스텀 React 훅
│   ├── App.tsx              # 메인 앱 컴포넌트 + 바텀 탭 네비게이션
│   └── index.tsx            # 진입점
├── public/
│   └── index.html           # HTML 템플릿
├── capacitor.config.ts      # Capacitor 설정
├── package.json             # npm 의존성
├── tsconfig.json            # TypeScript 설정
└── .gitignore
```

## 주요 기능 (Phase 1~6 로드맵)

### Phase 1: 온보딩 (1.5주) ✅
- [x] 5단계 온보딩 플로우
- [x] 관심 지역 선택 (최대 3개)
- [x] 알림 권한 요청 준비
- [x] 로컬 저장소 초기화

### Phase 2: 핵심 UI & 기능 (2.5주)
- [ ] 홈 화면: 포스트 그리드 + API 연동
- [ ] 포스트 상세 페이지
- [ ] 즐겨찾기 관리 + 로컬 저장
- [ ] 설정 탭 (관심지역, 알림 설정)

### Phase 3: 알림 & 캐싱 (2주)
- [ ] Firebase FCM 통합
- [ ] 로컬 알림 스케줄링
- [ ] 조용한 시간 로직
- [ ] 오프라인 캐싱

### Phase 4-6: 빌드 & 배포
- [ ] iOS/Android 네이티브 빌드
- [ ] 테스트 및 최적화
- [ ] Google Play 배포 (Android)

## 시작하기

### 1. 의존성 설치
```bash
npm install
```

### 2. 웹 버전 실행 (개발 모드)
```bash
npm start
```

### 3. Android 빌드 준비
```bash
npm run cap:build
npm run cap:add:android
npm run cap:open:android  # Android Studio에서 열기
```

### 4. iOS 빌드 준비 (Mac 필요)
```bash
npm run cap:add:ios
npm run cap:open:ios  # Xcode에서 열기
```

## 주요 서비스

### apiService
백엔드 FastAPI와 통신하는 HTTP 클라이언트
- `getPosts(regions?, limit, offset)` - 포스트 목록 조회
- `getPostDetail(postId)` - 포스트 상세 조회
- `registerDevice(fcmToken, deviceId, platform)` - 디바이스 등록

### storageService
Capacitor Storage를 사용한 로컬 저장소
- `getFavorites()` / `addFavorite()` - 즐겨찾기 관리
- `getUserPreferences()` / `setUserPreferences()` - 사용자 설정
- `getAppearanceSettings()` / `setAppearanceSettings()` - 테마 설정

### notificationService
로컬 알림 및 FCM 통합
- `initialize()` - 알림 권한 요청
- `scheduleLocalNotification(title, body, id)` - 로컬 알림 스케줄
- `showPostNotification(aptName, region)` - 분양공고 알림

### cacheService
오프라인 캐싱 (24시간 TTL)
- `getCachedPost()` / `setCachedPost()` - 포스트 캐시
- `getCacheSize()` / `clearCache()` - 캐시 관리

## 테마 시스템

CSS 변수로 구현된 3가지 색상 팔레트:
- **A**: 따뜻한 톤 (기본값) - `#d97757` (주색상)
- **B**: 자연스러운 톤 - `#386641` (주색상)
- **C**: 부드러운 톤 - `#ffafcc` (주색상)

HTML `data-palette` 속성으로 전환됨:
```html
<html data-palette="A">
```

## 백엔드 API 요구사항

### 새로 추가할 엔드포인트

```
POST /api/users/register-device
  req: { fcm_token, device_id, platform: 'ios'|'android' }
  res: { user_id, status }

POST /api/users/{user_id}/interests
  req: { regions: ['서울', '부산', ...] }
  res: { interests, updated_at }

GET /api/posts
  query: ?regions=서울,부산&limit=10&offset=0
  res: { posts: [{post_id, apt_name, notice_date, region, ...}], total }

GET /api/posts/{post_id}
  res: { post_id, apt_name, content, notice_date, region, ... }
```

## Firebase 설정 (필요)

1. Firebase Console에서 프로젝트 생성
2. Cloud Messaging (FCM) 활성화
3. 서비스 계정 키 다운로드
4. 백엔드에서 FCM API 사용

## GitHub Actions 배포 (미정)

- Android: Google Play Console에 자동 배포
- iOS: TestFlight 및 App Store (후속)

## 개발 팀 역할

| 작업 | 담당 |
|------|------|
| React/TypeScript 코드 | Claude Code (✅ 완료) |
| Capacitor 플러그인 통합 | Claude Code (다음 단계) |
| FastAPI 백엔드 API 추가 | Claude Code (필요) |
| iOS 빌드 (Xcode 서명) | 사용자 (필요) |
| Android 빌드 (Gradle, keystore) | 사용자 (필요) |
| Google Play 등록/배포 | 사용자 (필요) |
| App Store 등록/배포 | 사용자 (iOS 시) |
| 물리 기기 테스트 | 사용자 (필요) |

## 다음 단계

1. ✅ Capacitor + React 프로젝트 초기화
2. ⏳ 백엔드 FastAPI에 4개 엔드포인트 추가
3. ⏳ Phase 2-3 기능 구현 (홈, 즐겨찾기, 알림)
4. ⏳ Firebase FCM 통합
5. ⏳ Android/iOS 빌드 및 배포

---

**시작 일자**: 2026년 4월 27일  
**목표 배포**: 2026년 6월 (Android), 2026년 8월 (iOS)

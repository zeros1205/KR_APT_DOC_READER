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
│   │   ├── themes.ts        # 테마 설정
│   │   └── index.css        # 글로벌 스타일
│   ├── types/               # TypeScript 타입 정의
│   ├── hooks/               # 커스텀 React 훅
│   ├── App.tsx              # 메인 앱 컴포넌트 + 플로팅 메뉴
│   └── index.tsx            # 진입점
├── public/
│   └── index.html           # HTML 템플릿
├── capacitor.config.ts      # Capacitor 설정
├── package.json             # npm 의존성
├── tsconfig.json            # TypeScript 설정
└── .gitignore
```

## 주요 기능 (Phase 1~4 구현 완료)

### Phase 1: 온보딩 ✅
- [x] 3단계 온보딩 플로우 (앱 소개 → 지역 선택 → 알림 설정)
- [x] 관심 지역 선택 (최대 3개)
- [x] 알림 권한 요청
- [x] 로컬 저장소 초기화

### Phase 2: 핵심 UI & 기능 ✅
- [x] 홈 화면: 포스트 그리드 + 검색 + 무한 스크롤
- [x] 포스트 상세 페이지
- [x] 즐겨찾기 관리 + 정렬
- [x] 설정 탭 (관심지역, 조용한 시간, 캐시)
- [x] 플로팅 메뉴 (홈, 즐겨찾기, 설정)

### Phase 3: 알림 & 캐싱 & Firebase ✅
- [x] Firebase Cloud Messaging (FCM) 통합
- [x] FCM 토큰 관리 및 디바이스 등록
- [x] 로컬 알림 스케줄링
- [x] 조용한 시간 로직 (22:00~08:00 자동 조용함)
- [x] 오프라인 캐싱 (24시간 TTL)
- [x] 캐시 쿼터 관리 (최대 100개 항목, LRU)
- [x] 캐시 통계 (크기, 개수, 오래된/새로운 항목)

### Phase 4: 빌드 & 배포 🔄
- [x] Capacitor 플러그인 설정
- [x] Android 빌드 가이드 작성 (ANDROID_BUILD_GUIDE.md)
- [x] Firebase 설정 가이드 작성 (FIREBASE_SETUP.md)
- [ ] 로컬 Android 빌드 테스트
- [ ] Google Play Store 배포
- [ ] iOS (후속, Mac 확보 시)

## 빠른 시작

### 1. 의존성 설치
```bash
npm install
```

### 2. 웹 버전 실행 (개발 모드)
```bash
npm start
```

### 3. Android 빌드
**자세한 가이드**: [ANDROID_BUILD_GUIDE.md](./ANDROID_BUILD_GUIDE.md)

```bash
# 환경 준비
npm run cap:build
npm run cap:add:android

# 빌드
npm run build
npx capacitor sync android

# Android Studio에서 열기
npm run cap:open:android
```

### 4. Firebase 설정
**자세한 가이드**: [FIREBASE_SETUP.md](./FIREBASE_SETUP.md)

```bash
# 1. Firebase Console에서 프로젝트 생성
# 2. google-services.json 다운로드
# 3. android/app/ 폴더에 배치
# 4. npm install @capacitor-firebase/messaging
```

### 5. iOS 빌드 준비 (Mac 필요)
```bash
npm run cap:add:ios
npm run cap:open:ios  # Xcode에서 열기
```

## 주요 서비스

### apiService
백엔드 FastAPI와 통신하는 HTTP 클라이언트 (오프라인 폴백)
- `getPosts(regions?, limit, offset)` - 포스트 목록 조회 (네트워크 오류 시 캐시 반환)
- `getPostDetail(postId)` - 포스트 상세 조회
- 개발 모드: `manifest.json` 사용, 프로덕션: REST API

### storageService
Capacitor Storage를 사용한 로컬 저장소
- `getFavorites()` / `addFavorite()` / `removeFavorite()` - 즐겨찾기 관리
- `getUserPreferences()` / `setUserPreferences()` - 관심지역, 조용한 시간, 알림 설정
- `getAppearanceSettings()` / `setAppearanceSettings()` - 테마 설정
- `getDeviceId()` / `setDeviceId()` - 디바이스 ID 관리

### notificationService
로컬 알림 스케줄 및 일일 동기화
- `initialize()` - 알림 권한 요청 및 리스너 등록
- `scheduleLocalNotification(title, body, id, delayMs, region)` - 조용한 시간 체크
- `showPostNotification(aptName, region)` - 단일 포스트 알림
- `showBatchNotification(count, region)` - 여러 포스트 일괄 알림
- `scheduleDailySync()` - 자정에 새 포스트 동기화 (백엔드 연동 예정)
- `getNotificationLogs()` / `clearNotificationLogs()` - 감사 로그

### firebaseService
Firebase Cloud Messaging 통합
- `initialize()` - FCM 토큰 획득 및 리스너 설정
- `getToken()` - FCM 토큰 획득
- `registerDevice(fcmToken)` - 백엔드에 디바이스 등록
- `updateRegions(regions)` - 사용자 관심지역 업데이트
- 메시지 수신 핸들러 (포그라운드/백그라운드)

### cacheService
오프라인 캐싱 (24시간 TTL, LRU 쿼터, 버전 관리)
- `getCachedPost()` / `setCachedPost()` - 포스트 캐시
- `getCachedPostsList()` / `setCachedPostsList()` - 목록 캐시
- `getCacheStats()` - 캐시 통계 (크기, 개수, 오래된/새로운 항목)
- `getCacheSize()` / `clearCache()` - 캐시 관리
- `clearExpiredCache()` - 만료된 항목 선택 삭제
- `invalidateCache()` - 버전 기반 캐시 무효화
- `getOfflineMode()` / `setOfflineMode()` - 오프라인 모드 추적

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

## 문서 가이드

| 문서 | 용도 |
|------|------|
| [ANDROID_BUILD_GUIDE.md](./ANDROID_BUILD_GUIDE.md) | Android 개발 환경 설정, 빌드, Google Play 배포 |
| [FIREBASE_SETUP.md](./FIREBASE_SETUP.md) | Firebase 프로젝트 생성, FCM 설정, 배포 준비 |

## 개발 역할 분담

| 작업 | 상태 | 담당 |
|------|------|------|
| React/TypeScript 코드 (Phase 1-3) | ✅ 완료 | Claude Code |
| Capacitor 플러그인 통합 | ✅ 완료 | Claude Code |
| FirebaseService 구현 | ✅ 완료 | Claude Code |
| FastAPI 백엔드 API 추가 | ⏳ 필요 | Claude Code |
| 개발 환경 설정 | 📘 문서화 | 사용자 |
| Android 키스토어 생성 | 📘 가이드 제공 | 사용자 |
| Google Play 등록/배포 | 📘 가이드 제공 | 사용자 |
| Firebase 프로젝트 생성 | 📘 가이드 제공 | 사용자 |
| 물리 기기 테스트 | ⏳ 필요 | 사용자 |
| iOS 빌드 (Mac 필요) | ⏳ 후속 | - |

## 다음 단계 (사용자)

### Phase 4 실행 체크리스트

1. **개발 환경 준비** ([ANDROID_BUILD_GUIDE.md](./ANDROID_BUILD_GUIDE.md#1-개발-환경-준비) 참조)
   - [ ] JDK 17 설치
   - [ ] Android Studio 설치 (SDK Platform 33+)
   - [ ] ANDROID_HOME 환경 변수 설정
   - [ ] Node.js 16+ 확인

2. **Firebase 설정** ([FIREBASE_SETUP.md](./FIREBASE_SETUP.md) 참조)
   - [ ] Firebase Console에서 프로젝트 생성
   - [ ] Android 앱 등록 (com.apta.note)
   - [ ] google-services.json 다운로드
   - [ ] android/app/ 폴더에 배치

3. **Google Play 준비** ([FIREBASE_SETUP.md#4-google-play-console-설정](./FIREBASE_SETUP.md#4-google-play-console-설정) 참조)
   - [ ] Google Play Developer 계정 등록 ($25)
   - [ ] 앱 생성
   - [ ] 스토어 정보 입력

4. **로컬 빌드 테스트**
   ```bash
   npm run build
   npx capacitor sync android
   ./gradlew assembleDebug
   ```

5. **배포**
   - [ ] 키스토어 파일 생성
   - [ ] Release AAB 빌드
   - [ ] Google Play에 업로드
   - [ ] 심사 대기 (24시간~1주)

## 성과 요약

### Phase 1-3 완료 (8주)
- ✅ 온보딩 시스템 (관심지역 선택)
- ✅ 홈 + 즐겨찾기 + 설정 탭
- ✅ Firebase FCM 통합
- ✅ 로컬 알림 + 조용한 시간
- ✅ 오프라인 캐싱 (LRU + 쿼터)
- ✅ 97개 샘플 포스트 데이터

### Phase 4 진행 중
- ✅ Android 빌드 가이드
- ✅ Firebase 설정 가이드
- ⏳ 첫 배포

---

**시작 일자**: 2026년 4월 27일  
**Phase 1-3 완료**: 2026년 4월 27일  
**목표 배포**: 2026년 5월 중순 (Android)

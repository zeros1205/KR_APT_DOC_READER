# iOS 앱 확장 개발 계획

> **프로젝트**: PROJECT BALI (청약홈 분양공고 자동 포스팅 시스템)  
> **작성일**: 2026-05-13  
> **상태**: 계획 수립 단계  
> **담당**: iOS 개발팀

---

## 개요

기존 Python 백엔드(청약홈 데이터 수집 + LLM 파이프라인 + HTML 정적 렌더링) 기반의 웹 시스템을 iOS 네이티브 앱으로 확장하기 위한 상세 개발 전략입니다.

**핵심 목표**:
- 사용자가 모바일에서 편하게 분양공고를 열람, 비교, 저장
- 실시간 알림으로 새 공고 감지 자동화
- 기존 웹 인프라(Cloudflare Pages + Python 파이프라인) 최대한 활용
- 비용 최소화 + 빠른 출시

---

## 1. 시스템 아키텍처 설계

### 1.1 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                    iOS 네이티브 앱                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ SwiftUI 프론트엔드 (iOS 16+)                          │   │
│  │ - 공고 목록 조회 (infinite scroll)                     │   │
│  │ - 상세 페이지 (웹뷰 + 네이티브 오버레이)                │   │
│  │ - 저장/비교 기능 (로컬 DB)                             │   │
│  │ - 검색 & 필터링 (다중 조건)                            │   │
│  │ - 실시간 알림 (FCM/APNs)                              │   │
│  │ - 오프라인 모드 (캐싱)                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 로컬 저장소 (SQLite + CoreData)                       │   │
│  │ - favorites: 찜한 공고                                │   │
│  │ - comparisons: 비교 목록                              │   │
│  │ - search_history: 검색 히스토리                       │   │
│  │ - offline_cache: 최근 공고 스냅샷                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              백엔드 API (신규 Node.js/Python 서버)            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ RESTful API                                          │   │
│  │ - GET  /api/notices             (공고 목록)          │   │
│  │ - GET  /api/notices/:id         (상세)              │   │
│  │ - POST /api/favorites           (찜)                │   │
│  │ - GET  /api/search              (검색)              │   │
│  │ - POST /api/push-tokens         (FCM 토큰)          │   │
│  │ - GET  /api/notifications       (알림 히스토리)      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 데이터 베이스 (PostgreSQL or MongoDB)                │   │
│  │ - notices (메인 공고 데이터)                          │   │
│  │ - user_preferences (사용자 설정)                      │   │
│  │ - notifications_log (알림 히스토리)                   │   │
│  │ - user_favorites (찜한 공고)                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           기존 Python 파이프라인 + Cloudflare Pages            │
│  - 공고 수집 (청약홈 API)                                   │
│  - 콘텐츠 생성 (GPT-5.4 + Gemini)                          │
│  - HTML 렌더링 → Cloudflare Pages 배포                     │
│  - posts_index.json (메인 데이터 소스)                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 데이터 흐름 (3단계)

#### Phase 1 (MVP): 웹 데이터 직접 사용
- iOS 앱 → `https://apt-note.com/posts_index.json` 직접 호출
- 상세 HTML 웹뷰로 표시
- 로컬 저장소만으로 찜/비교 관리

#### Phase 2: 백엔드 API 추가
- 새로운 Node.js/Express API 서버 구축
- 기존 posts_index.json 데이터를 API로 변환
- 검색, 필터링, 알림 기능 추가
- 사용자 선호도 추적

#### Phase 3: 실시간 알림 시스템
- Firebase Cloud Messaging (FCM) / Apple Push Notifications (APNs)
- 새 공고 감지 → 즉시 사용자 알림
- 관심 지역 기반 알림 필터링

---

## 2. 기술 스택 선택

### 2.1 iOS 앱

| 계층 | 선택 기술 | 사유 |
|------|---------|------|
| **UI 프레임워크** | SwiftUI | 최신 Apple 표준, 프리뷰 지원, iOS 16+ 타겟 |
| **네트워킹** | URLSession + async/await | 표준 라이브러리, 모던 Swift 문법 |
| **로컬 저장소** | SQLite (GRDB 라이브러리) | 복잡한 쿼리 지원, 성능 최적 |
| **상태 관리** | @ObservedObject + @StateObject | SwiftUI 기본, 간단한 상태 관리 |
| **캐싱** | URLCache + 커스텀 레이어 | HTTP 캐시 + 로컬 파일 시스템 |
| **분석** | Firebase Analytics | 무료, Apple 통합 용이 |
| **푸시 알림** | APNs | iOS 표준, 신뢰성 높음 |
| **테스트** | XCTest + Combine | 표준 테스트 프레임워크 |

**대안 검토**:
- Vapor/Kitura (백엔드): Python 기존 코드와 호환성 고려 → **Node.js 선택**
- Core Data: SQLite보다 복잡하고 쿼리 제어 부족 → **SQLite 선택**
- RxSwift: 과도한 의존성 → **표준 Combine 선택**

### 2.2 백엔드 API 서버

| 계층 | 선택 기술 | 사유 |
|------|---------|------|
| **런타임** | Node.js 18+ 또는 Python FastAPI | JavaScript 에코시스템 강함 / Python 기존 코드 재사용 |
| **프레임워크** | Express.js (Node) 또는 FastAPI (Python) | 가벼움, 빠른 개발, 커뮤니티 활발 |
| **데이터베이스** | PostgreSQL | JSONB 지원, 확장성, ACID 보장 |
| **캐싱** | Redis | 실시간 데이터 캐싱, 푸시 토큰 저장 |
| **배포** | Docker + AWS ECS / Google Cloud Run | 스케일링, 비용 효율성 |
| **모니터링** | DataDog / Sentry | 에러 추적, 성능 모니터링 |

**권장**: **Node.js + Express** (빠른 프로토타입) 또는 **Python FastAPI** (기존 코드 통합)

### 2.3 알림 시스템

| 요소 | 선택 | 사유 |
|------|------|------|
| **푸시 알림** | Firebase Cloud Messaging (FCM) + APNs | 통합 관리, 무료, 신뢰성 |
| **스케줄링** | GitHub Actions (기존) + Cloud Scheduler | 기존 인프라 활용, 비용 최소화 |
| **메시지 브로커** | SQS (AWS) 또는 Redis Pub/Sub | 비동기 처리, 실패 재시도 |

---

## 3. MVP 정의 & 기능 우선순위

### Phase 1 MVP (3개월, 팀 규모: iOS 1명 + 백엔드 1명)

#### 코어 기능

1. **공고 브라우징** (45% 영향도)
   - ✅ 최신 공고 목록 조회 (무한 스크롤)
   - ✅ 지역별 탭 필터링 (기본 8개 지역)
   - ✅ 공고 상세 페이지 (웹뷰 기반)
   - ✅ 새로고침 (Pull-to-Refresh)

2. **저장 기능** (20% 영향도)
   - ✅ 찜한 공고 로컬 저장 (SQLite)
   - ✅ 찜 목록 별도 탭
   - ✅ 찜 공고 개수 뱃지 표시

3. **검색** (20% 영향도)
   - ✅ 공고명 검색 (로컬)
   - ✅ 지역명 검색
   - ✅ 최근 검색어 저장 (최대 10개)

4. **설정** (15% 영향도)
   - ✅ 관심 지역 선택 (체크박스)
   - ✅ 알림 ON/OFF
   - ✅ 조용한 시간 설정
   - ✅ 앱 정보 & 피드백

#### 제외 (Phase 2+)
- ❌ 비교 기능
- ❌ 고급 필터링 (가격대, 입주시기)
- ❌ 실시간 알림
- ❌ 오프라인 모드 고도화

### Phase 2 (3개월, 팀 규모: iOS 1 + 백엔드 1)
- 비교 기능 (최대 3개 동시 비교)
- 고급 필터링 (가격대, 공급유형, 청약일자 범위)
- 백엔드 API 완성
- 사용자 선호도 추적
- Firebase Analytics 연동

### Phase 3 (2개월, 팀 규모: iOS 1 + 백엔드 1)
- 실시간 푸시 알림
- Firebase Cloud Messaging 연동
- 알림 히스토리 조회
- 관심 조건 기반 알림 필터링
- A/B 테스트 인프라

---

## 4. 개발 로드맵

### Timeline: 8개월 (Phase 1~3)

```
Phase 1: MVP          Phase 2: 고도화         Phase 3: 실시간 알림
(0~3개월)             (3~6개월)               (6~8개월)
├─ iOS 구조           ├─ 비교 UI/로직         ├─ FCM 구축
├─ 공고 목록 & 상세   ├─ 필터링 로직          ├─ 알림 자동화
├─ 찜하기 (SQLite)    ├─ 백엔드 API           ├─ A/B 테스트
├─ 기본 검색          ├─ 분석 대시보드         ├─ 베타 테스트
├─ 설정 UI            ├─ TestFlight Beta      └─ App Store 출시
├─ TestFlight Beta1   └─ App Store 1.0
└─ 내부 QA
```

### Phase 1 상세 일정 (12주)

| 주차 | 1~2 | 3~4 | 5~6 | 7~8 | 9~10 | 11~12 |
|------|-----|-----|-----|-----|------|-------|
| **작업** | 프로토타입 & 설정 | 데이터 계층 | UI - 목록 | UI - 상세 & 찜 | 검색 & 필터 | 설정 & QA |
| **산출물** | 프로젝트 초기화 | SQLite 스키마 | NoticeListView | FavoritesView | SearchView | SettingsView |
| **담당** | iOS 1명 | iOS 1명 | iOS 1명 | iOS 1명 | iOS 1명 | iOS 1명 + QA |

### 마일스톤

| 마일스톤 | 일정 | 산출물 |
|---------|------|--------|
| M1: 프로토타입 완성 | 8주 | Figma 디자인 + 로우파이 프로토타입 |
| M2: MVP 알파 | 12주 | TestFlight 1.0.0 (내부 테스트) |
| M3: 공개 베타 | 14주 | TestFlight 1.0.0 (확대 테스트) |
| M4: App Store 출시 | 16주 | 공개 버전 1.0.0 |
| M5: Phase 2 완성 | 24주 | v1.1 (비교/필터 기능) |
| M6: Phase 3 완성 | 32주 | v1.2 (실시간 알림) |

---

## 5. 리스크 분석 & 완화 방안

| # | 리스크 | 영향도 | 발생확률 | 완화 방안 |
|---|--------|--------|---------|-----------|
| 1 | iOS 14 호환성 요구 변경 | 중 | 중 | iOS 16+ 고정, 요구 변경 시 재평가 |
| 2 | 웹뷰 로딩 느림 | 중 | 높음 | 캐싱 강화, 요청 최적화, 프로그레시브 로딩 |
| 3 | 백엔드 API 개발 지연 | 높음 | 중 | MVP는 직접 posts_index.json 호출, API는 Phase 2 |
| 4 | 푸시 알림 인증 (APNs) 설정 복잡 | 중 | 낮음 | Apple Developer 계정 조기 확보, 문서 준비 |
| 5 | 데이터 동기화 오류 | 높음 | 중 | 오프라인/온라인 상태 감지, 재시도 로직 |
| 6 | App Store 심사 거부 | 높음 | 낮음 | 가이드 조기 검토, 법적 문구 준비 |
| 7 | 서버 인프라 비용 폭증 | 중 | 낮음 | CDN 캐싱, 데이터 압축, 읽기 전용 최적화 |
| 8 | 사용자 데이터 보호 (GDPR/PIPA) | 높음 | 낮음 | 개인정보 보호정책 수립, HTTPS/TLS 암호화 |

**완화 우선순위**: 3 > 5 > 6 > 2

---

## 6. 팀 구성 & 예상 일정

### Phase 1 (3개월, 4명)

- **iOS 개발자** (1명, 시니어)
  - SwiftUI/SQLite 전문가
  - 네트워킹/캐싱 최적화
  - 역할: 코어 앱 아키텍처, UI 구현

- **백엔드 개발자** (1명)
  - Node.js/Express 또는 Python FastAPI
  - 역할: 초기 API 프로토타입 (선택사항, MVP는 직접 호출)

- **QA/테스트 엔지니어** (1명)
  - 기능/성능/회귀 테스트
  - TestFlight 배포 관리

- **PM/기획자** (0.5명)
  - 기능 스펙 정의
  - 우선순위 조정
  - 이해관계자 커뮤니케이션

### Phase 2 (3개월, 추가 인력)
- iOS 개발자 (1명 추가) → 총 2명
- 백엔드 개발자 (0.5명 증원) → 전담 1명 (데이터베이스 설계)
- 디자이너 (0.5명) → UI/UX 고도화

### Phase 3 (2개월)
- 인력 유지
- DevOps 엔지니어 (0.5명) → 알림 인프라 구축

### 총 소요 기간: 8개월
- **병렬 작업**: iOS 개발과 API 프로토타입 동시 진행 (Phase 1 4주차~)
- **의존성 최소화**: MVP는 기존 JSON 직접 호출로 우회 가능

---

## 7. 기술적 세부 설계

### 7.1 iOS 앱 아키텍처 (MVVM)

```swift
// Core 모델
struct Notice: Codable {
  let notice_id: String
  let apt_name: String
  let region: String
  let notice_date: String
  let price_range: String
  let special_supply_date: String
  let rank1_date: String
  let post_url: String
  let notice_url: String
}

// ViewModel
@MainActor
class NoticeListViewModel: ObservableObject {
  @Published var notices: [Notice] = []
  @Published var filteredNotices: [Notice] = []
  @Published var isLoading = false
  @Published var selectedRegion = "전체"
  
  private let apiService: APIService
  private let dbService: DatabaseService
  
  func fetchNotices() async {
    // 1. 캐시 확인
    if let cached = dbService.loadNoticeCache() {
      self.notices = cached
    }
    // 2. 원격 호출
    let fresh = await apiService.fetchNotices()
    // 3. 캐시 업데이트
    dbService.saveNotices(fresh)
    self.notices = fresh
  }
}

// View
struct NoticeListView: View {
  @StateObject var viewModel: NoticeListViewModel
  
  var body: some View {
    VStack {
      // 지역 필터 탭
      // 공고 목록 (List + infinite scroll)
      // Pull-to-Refresh
    }
  }
}
```

### 7.2 데이터베이스 스키마 (SQLite)

```sql
-- Favorites (찜한 공고)
CREATE TABLE favorites (
  id INTEGER PRIMARY KEY,
  notice_id TEXT UNIQUE NOT NULL,
  apt_name TEXT NOT NULL,
  region TEXT,
  price_range TEXT,
  saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SearchHistory (검색 히스토리)
CREATE TABLE search_history (
  id INTEGER PRIMARY KEY,
  query TEXT NOT NULL,
  searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NoticeCache (오프라인용 공고 스냅샷)
CREATE TABLE notice_cache (
  id INTEGER PRIMARY KEY,
  notice_id TEXT UNIQUE NOT NULL,
  data TEXT NOT NULL, -- JSON
  cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- UserPreferences (사용자 설정)
CREATE TABLE user_preferences (
  id INTEGER PRIMARY KEY,
  key TEXT UNIQUE,
  value TEXT
);
```

### 7.3 백엔드 API 스펙 (OpenAPI 3.0)

```yaml
openapi: 3.0.0
info:
  title: APT Note API
  version: 1.0.0
servers:
  - url: https://api.apt-note.com

paths:
  /api/notices:
    get:
      summary: 공고 목록 조회
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
        - name: offset
          in: query
          schema: { type: integer, default: 0 }
        - name: region
          in: query
          schema: { type: string }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  total: { type: integer }
                  notices: { type: array }

  /api/notices/{id}:
    get:
      summary: 공고 상세 조회
      parameters:
        - name: id
          in: path
          required: true
      responses:
        '200':
          content:
            application/json:
              schema: { $ref: '#/components/schemas/NoticeDetail' }

  /api/favorites:
    post:
      summary: 공고 찜하기
      requestBody:
        content:
          application/json:
            schema: { notice_id: string }
    get:
      summary: 찜한 공고 목록

  /api/search:
    get:
      parameters:
        - name: q
          in: query
          schema: { type: string }
```

### 7.4 네트워킹 전략 (오프라인 대응)

```swift
// APIService with retry logic
class APIService {
  private let session = URLSession.shared
  private let cache = URLCache.shared
  
  func fetchNotices(useCache: Bool = true) async throws -> [Notice] {
    let url = URL(string: "https://apt-note.com/posts_index.json")!
    
    // 1순위: 캐시
    if useCache, let cached = cache.cachedResponse(for: URLRequest(url: url)) {
      return try JSONDecoder().decode([Notice].self, from: cached.data)
    }
    
    // 2순위: 네트워크
    var request = URLRequest(url: url)
    request.cachePolicy = .returnCacheDataElseLoad
    
    let (data, response) = try await session.data(for: request)
    guard (response as? HTTPURLResponse)?.statusCode == 200 else {
      throw APIError.invalidResponse
    }
    
    return try JSONDecoder().decode([Notice].self, from: data)
  }
}
```

---

## 8. 기존 시스템과의 통합 포인트

### 8.1 데이터 소스 활용

**Phase 1 MVP에서:**
1. `https://apt-note.com/posts_index.json` 직접 호출 (변경 불필요)
2. 상세 공고는 `https://apt-note.com/posts/{notice_id}/post.html` 웹뷰로 표시

**Phase 2+에서:**
1. 새 백엔드 API 구축 (PostgreSQL 데이터베이스)
2. 기존 posts_index.json을 API 엔드포인트로 변환
3. 사용자 데이터 (favorites, preferences) 관리

### 8.2 Python 파이프라인과의 연계

**변경 최소화**:
- 기존 `output/data_cache/notices/{notice_id}.json` 구조 유지
- `output/posts_index.json` 갱신 주기 유지 (일일)
- HTML 렌더링 로직 변경 불필요

**추가 기능**:
- 새 공고 감지 시 Firebase Cloud Messaging 토큰으로 푸시 발송 (Phase 3)
- 사용자 선호도 데이터 로깅 (분석용, Phase 2)

---

## 9. 운영 & 배포 전략

### 9.1 배포 체인

```
Local Dev → GitHub → Xcode Cloud → TestFlight → App Store
     ↓           ↓         ↓           ↓         ↓
  Swift Build   CI/CD    자동 빌드   베타 테스트  공개 릴리스
    (20min)    (5min)    (30min)    (14일)     (1~3일)
```

### 9.2 버전 관리

- **Semantic Versioning**: v{major}.{minor}.{patch}
- **App Store Version**: 1.0.0 (Phase 1)
- **Build Number**: 자동 증분 (Xcode)
- **변경로그**: CHANGELOG.md 유지

### 9.3 모니터링 & 분석

- **Crash Reporting**: Firebase Crashlytics
- **Analytics**: Firebase Analytics (이벤트: 공고 조회, 찜하기, 검색)
- **Performance**: Core Web Vitals (LCP, FID, CLS) 추적
- **User Retention**: 주간/월간 활성 사용자 (DAU, MAU)

---

## 10. 참고할 기존 코드베이스 파일

기존 코드에서 iOS 앱 개발 시 참고할 주요 파일들:

- `API_FIELDS.md` — 청약홈 공공API 필드 매핑 (백엔드 API 설계 참조)
- `output/data_cache/notices/*.json` — 데이터 구조 참고 (iOS 모델 설계)
- `pipeline/config.py` — API 엔드포인트, 환경변수 관리 (통합 포인트)
- `templates/blog_template.html` — 상세 페이지 HTML 구조 (웹뷰 렌더링)
- `pipeline/themes.py` — UI 테마 토큰 (iOS 디자인 시스템 참고)

---

## 요약

| 항목 | 내용 |
|------|------|
| **프로젝트 기간** | 8개월 (Phase 1~3) |
| **팀 규모** | 4~6명 |
| **예상 예산** | $150K~250K |
| **MVP 출시** | 3개월 후 |
| **App Store 출시** | 4개월 후 |
| **핵심 리스크** | 백엔드 API 개발 지연 (MVP는 기존 JSON 호출로 우회) |

### 성공 지표

- **Phase 1**: App Store 출시 (DAU 500+)
- **Phase 2**: 비교 기능 채택률 30%+
- **Phase 3**: 알림 구독자 60%+, 푸시 오픈율 40%+

---

**다음 단계**:
1. 경영진 승인 및 예산 배정
2. iOS 개발팀 구성 (시니어 개발자 1명)
3. 디자인 시스템 수립 (Figma)
4. GitHub 레포지토리 생성 (별도 리포 또는 monorepo)
5. Xcode Cloud CI/CD 파이프라인 구성

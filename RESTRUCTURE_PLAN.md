# 🏗️ KR_APT_DOC_READER 리아키텍처링 계획

**작성일**: 2026-04-24  
**상태**: 🔴 긴급 - 현재 구조 유지 불가능  
**목표**: DB 기반 아키텍처 + 재설계된 홈페이지

---

## 📋 현재 문제점 분석

### 1️⃣ 필드명 매핑 혼란
```
청약홈 API: HSSPLY_ADRES (원본)
  ↓ (매핑)
collector.py: supply_address
  ↓ (전달)
orchestrator.py: supply_address
  ↓ (저장)
html_renderer.py: supply_address
  ↓ (렌더링)
HTML 템플릿: {{SUPPLY_LOCATION}}
```

**문제**: 4단계 매핑으로 인한 추적 불가, 필드명 불일치 에러 빈번

### 2️⃣ 데이터 구조의 비일관성
- PostData: Python dataclass (메모리만 사용)
- 저장소: JSON 파일 (output/posts/*/post_meta.json)
- 검색/필터링: 불가능
- 데이터 관계: 없음 (아파트 ↔ 포스팅 연결 불가)

### 3️⃣ 홈페이지 구조의 한계
- 정적 HTML (index.html) → 수정 어려움
- 동적 콘텐츠: JavaScript로 무리하게 처리
- 검색/필터: 구현 불가능
- SEO: 제한적

### 4️⃣ 포스팅 생성 파이프라인의 복잡성
- 7개 Agent + 5단계 처리
- 필드명 변환이 곳곳에 산재
- 에러 추적 어려움

---

## 🎯 목표 상태

```
청약홈 API
    ↓
수집기 (collector.py)
    ↓
PostgreSQL DB
    ├─ apartments (단지)
    ├─ postings (포스팅)
    ├─ postings_content (콘텐츠)
    └─ postings_metadata (메타)
    ↓
FastAPI 백엔드
    ├─ /api/apartments
    ├─ /api/postings
    └─ /api/search
    ↓
프론트엔드 (React/Vue)
    ├─ 목록 페이지 (검색/필터)
    ├─ 상세 페이지 (포스팅)
    └─ 관리자 대시보드
```

**장점**:
- ✅ 데이터 관계 명확
- ✅ 필드명 추적 용이
- ✅ 검색/필터 가능
- ✅ 데이터 무결성
- ✅ 확장성

---

## 📐 DB 스키마 (PostgreSQL)

### apartments 테이블
```sql
id (PK)
api_notice_id (청약홈 API PBLANC_NO)
apt_name (HOUSE_NM)
supply_address (HSSPLY_ADRES) -- 원본 필드명 그대로
location (시/구/동 파싱)
supply_scale
total_units
is_hot_zone
regulated_zone
readmission_limit
live_requirement
price_cap
land_type
constructor
notice_url
created_at
updated_at
```

### postings 테이블
```sql
id (PK)
apartment_id (FK)
post_title
post_subtitle
post_slug (URL 친화적)
theme
quality_score
is_published
created_at
updated_at
```

### postings_content 테이블
```sql
id (PK)
posting_id (FK)
-- LLM 생성 필드 (한 번 생성 후 수정 가능)
apt_intro
location_intro
financial_intro
qa_intro
schedule_desc
tax_desc
unit_type_desc
-- 구조화 데이터
subway_score, subway_detail
school_score, school_detail
life_score, life_detail
medical_score, medical_detail
eligibility_special (JSON)
eligibility_rank1 (JSON)
eligibility_rank2 (JSON)
qa_blocks (JSON)
seo_tags (JSON)
created_at
updated_at
```

### postings_metadata 테이블
```sql
id (PK)
posting_id (FK)
special_supply_date
rank1_date
rank2_date
winner_date
move_in_date
contract_ratio
midterm_ratio
balance_ratio
loan_info
resale_restriction
created_at
updated_at
```

---

## 🔧 마이그레이션 전략

### Phase 1: 기반 구축 (2시간)
- [ ] PostgreSQL 설정 (또는 SQLite 임시)
- [ ] SQLAlchemy 모델 정의
- [ ] 기존 JSON 데이터 → DB 마이그레이션 스크립트

### Phase 2: 파이프라인 연동 (2시간)
- [ ] orchestrator.py → DB 저장 으로 변경
- [ ] 필드명 정리 (HSSPLY_ADRES 원본 유지)
- [ ] 기존 포스팅 재생성 테스트

### Phase 3: 백엔드 API (3시간)
- [ ] FastAPI 기본 구조
- [ ] CRUD 엔드포인트
- [ ] 검색/필터 로직

### Phase 4: 프론트엔드 (4시간+)
- [ ] React 컴포넌트 재설계
- [ ] 목록 페이지
- [ ] 상세 페이지
- [ ] 관리자 대시보드

---

## 📊 현재 진행 상황

| 항목 | 상태 | 예상 시간 |
|------|------|---------|
| 현황 분석 | ✅ 완료 | 30분 |
| 계획 수립 | ✅ 완료 | - |
| DB 스키마 설계 | ✅ 완료 | - |
| **다음: SQLAlchemy 모델 작성** | ⏳ 2시간 | 1시간 |
| 마이그레이션 스크립트 | 예정 | 1시간 |
| 파이프라인 통합 | 예정 | 2시간 |

---

## 🚀 즉시 시작할 것

1. **PostgreSQL/SQLite 선택**
   - PostgreSQL (추천): 프로덕션급, 강력
   - SQLite (대안): 설정 간단, 로컬 개발용

2. **첫 단계 (지금부터 1시간)**
   - SQLAlchemy ORM 모델 작성
   - 마이그레이션 스크립트 (JSON → DB)
   - 테스트 실행

3. **다음 단계 (1~2시간 후)**
   - orchestrator.py 수정 (DB 저장)
   - 포스팅 재생성 테스트
   - 기존 데이터 검증

---

**시작?** Y/N

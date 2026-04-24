# 청약홈 APT 블로그 자동화 시스템 - 최종 아키텍처 인수인계 문서

**작성일**: 2026-04-25  
**프로젝트**: KR_APT_DOC_READER (PROJECT BALI)  
**상태**: Phase 2 완료, Phase 3 진행 중  
**핵심 기술**: Python 3.11+ | Gemini 3.1 Flash | SQLAlchemy ORM | FastAPI | ChromaDB

---

## 📌 프로젝트 개요

### 비즈니스 목표
부동산 청약홈의 분양공고를 자동으로 수집 → 분석 → **네이버 블로그 HTML 포스트 자동생성**

### 핵심 가치 제안
- 일일 3개 건의 자동 블로그 포스팅
- AI 기반 마케팅 콘텐츠 생성 (스마트 에디터 ONE 호환)
- 공공데이터 + LLM 기반 높은 정확도
- 확장 가능한 멀티테넌트 아키텍처

---

## 🎯 리디자인 이유 & 전략

### Phase 1: 초기 구조 (문제점)
```
❌ 모놀리식 구조
❌ API 키 관리 혼란
❌ 이미지 자동 수집 복잡도 높음
❌ 응답성 저하 (동기 호출)
❌ 에러 처리 미흡
```

### Phase 2: 리디자인 (현재 상태) ✅
```
✅ 마이크로서비스 기반 7단계 파이프라인
✅ 환경 변수 중앙화 (config.py)
✅ 비동기 처리 (asyncio + httpx)
✅ 데이터베이스 저장 (SQLAlchemy)
✅ 멀티테마 지원 (7개 CSS 팔레트)
✅ 정적 + 동적 렌더링 (manifest.json)
✅ 보안 강화 (path validation, file size limits)
```

### Phase 3: 계획 (진행 중) 🔄
```
🔄 웹 대시보드 (FastAPI)
🔄 포스팅 편집/업데이트
🔄 A/B 테스팅
🔄 Google Analytics 연동
🔄 SEO 최적화
```

---

## 🏗️ 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     데이터 수집 계층                          │
├─────────────────────────────────────────────────────────────┤
│  공공데이터포털 API (getAPTLttotPblancDetail)               │
│  ↓                                                           │
│  CheongYakAPI (agents/collector.py)                         │
│  - 주택관리번호 검색                                         │
│  - 공고번호 검색                                             │
│  - 주택형별 상세 조회                                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  7단계 LLM 파이프라인 계층                    │
├─────────────────────────────────────────────────────────────┤
│ Stage 1: 팩트 추출 (Gemini Flash)                           │
│   └─ 공고 핵심 정보 추출                                     │
│                                                             │
│ Stage 2: 청약 적격 검증                                     │
│   └─ 투기과열지구/조정대상 여부 확인                         │
│                                                             │
│ Stage 3: 규제사항 분석                                      │
│   └─ 전매제한, 분양가상한제 등                              │
│                                                             │
│ Stage 4: 단지 소개 콘텐츠 생성                              │
│   └─ 마케팅 톤 (150~200자)                                 │
│                                                             │
│ Stage 5: 입지 분석                                          │
│   └─ 교통/교육/상권 정보 (100~150자)                       │
│                                                             │
│ Stage 6: FAQ & 자금 계획                                    │
│   └─ Q&A 6개 + 납부 타임라인                               │
│                                                             │
│ Stage 7: 품질 평가                                          │
│   └─ 점수 산정 (MIN: 60점)                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   데이터베이스 저장 계층                      │
├─────────────────────────────────────────────────────────────┤
│ SQLAlchemy ORM (SQLite/PostgreSQL)                          │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ apartments (주택 정보)                               │    │
│ ├─────────────────────────────────────────────────────┤    │
│ │ - id (PK)                                           │    │
│ │ - notice_id (공고번호)                              │    │
│ │ - apt_name (단지명)                                 │    │
│ │ - location (위치)                                   │    │
│ │ - constructor (시공사)                              │    │
│ │ - is_hot_zone, is_adj_zone, is_price_cap (규제)    │    │
│ └─────────────────────────────────────────────────────┘    │
│                          ↓                                  │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ postings (포스팅 메타)                               │    │
│ ├─────────────────────────────────────────────────────┤    │
│ │ - id (PK)                                           │    │
│ │ - apartment_id (FK)                                 │    │
│ │ - post_slug (고유키: notice_id 기반)               │    │
│ │ - quality_score (60~100)                            │    │
│ │ - theme (claude/notion/airbnb/...)                 │    │
│ │ - created_at, updated_at                           │    │
│ └─────────────────────────────────────────────────────┘    │
│                          ↓                                  │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ posting_contents (HTML 본문)                        │    │
│ ├─────────────────────────────────────────────────────┤    │
│ │ - id (PK)                                           │    │
│ │ - posting_id (FK)                                   │    │
│ │ - content (33KB+ HTML)                              │    │
│ └─────────────────────────────────────────────────────┘    │
│                          ↓                                  │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ posting_metas (JSON 메타데이터)                      │    │
│ ├─────────────────────────────────────────────────────┤    │
│ │ - id (PK)                                           │    │
│ │ - posting_id (FK)                                   │    │
│ │ - metadata (JSON: price_range, dates, etc.)        │    │
│ └─────────────────────────────────────────────────────┘    │
│                                                             │
│ RAG 벡터 저장소: ChromaDB                                   │
│ └─ 공고 전문 임베딩 (팩트체크용)                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    렌더링 & 배포 계층                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌──────────────────────────────────┐                       │
│ │ 정적 프론트페이지                   │                       │
│ ├──────────────────────────────────┤                       │
│ │ templates/front_index_template    │                       │
│ │         ↓                          │                       │
│ │ output/index.html (초기화만)      │                       │
│ │         ↓ (JavaScript로드)         │                       │
│ │ manifest.json 동적 렌더링          │                       │
│ │   - 지역 필터 탭                    │                       │
│ │   - 카드 그리드 (12개/페이지)      │                       │
│ │   - 페이지네이션                    │                       │
│ └──────────────────────────────────┘                       │
│                                                             │
│ ┌──────────────────────────────────┐                       │
│ │ 동적 포스트 페이지                  │                       │
│ ├──────────────────────────────────┤                       │
│ │ BlogHTMLRenderer                  │                       │
│ │         ↓                          │                       │
│ │ output/posts/{notice_id}/          │                       │
│ │  └─ post.html (786행)             │                       │
│ │  └─ post_meta.json                │                       │
│ │                                   │                       │
│ │ 7개 CSS 테마 지원                  │                       │
│ │  - claude (파랑 기반)              │                       │
│ │  - notion, airbnb, stripe...      │                       │
│ └──────────────────────────────────┘                       │
│                                                             │
│ 배포 대상: Cloudflare Pages                                │
│   └─ manifest.json 호환성 완벽      │                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 데이터 구조 & 흐름

### 1단계: 데이터 수집 흐름
```
공공데이터포털 API
  ↓
CheongYakAPI.get_list()
  ├─ 조건: cond[RCRIT_PBLANC_DE::GTE]=START_DATE
  ├─ 응답: {data: [...], totalCount: N}
  └─ 필드 매핑: PBLANC_NO, HOUSE_NM, RCRIT_PBLANC_DE, ...
  ↓
NoticeDocument (정규화 구조체)
  ├─ notice_id (공고번호)
  ├─ apt_name (단지명)
  ├─ supply_address (공급위치)
  ├─ total_units (총 세대수)
  ├─ notice_date, special_supply_start, ...
  ├─ is_hot_zone, is_adj_zone, is_price_cap (규제)
  └─ raw_text (RAG용 원문)
```

### 2단계: LLM 파이프라인 흐름
```
NoticeDocument
  ↓
Stage 1: orchestrator_v2.stage1_extract_facts()
  ├─ Gemini: 키 정보 추출
  ├─ 출력: {notice_id, apt_name, location, price_range, ...}
  └─ 저장: SQLite apartments 테이블
  ↓
Stage 2-7: orchestrator_v2.run_pipeline_v2()
  ├─ Gemini: 각 단계별 LLM 호출
  ├─ 토큰 최적화: 요약 텍스트 사용
  └─ 패스쓰루: 이전 단계 결과 활용
  ↓
PostData 객체
  ├─ facts (stage1)
  ├─ content (stage4-6)
  ├─ images (이미지 URL)
  ├─ cta_links (행동 유도 링크)
  └─ metadata (메타데이터)
```

### 3단계: 데이터베이스 저장 흐름
```
PostData
  ↓
BlogHTMLRenderer.build_post_data()
  ├─ apartment: Apartment(notice_id, apt_name, ...)
  ├─ posting: Posting(post_slug=notice_id, quality_score=N)
  └─ content: PostingContent(html 본문)
  ↓
Database.save_post()
  ├─ INSERT apartments (or UPDATE)
  ├─ INSERT postings
  ├─ INSERT posting_contents
  ├─ INSERT posting_metas
  └─ COMMIT
```

### 4단계: 렌더링 및 배포 흐름
```
database
  ↓
1️⃣ index.html (최초 1회만 생성)
   └─ build_front_index_once() → /output/index.html
  ↓
2️⃣ manifest.json (매 포스팅마다 갱신)
   ├─ load_posts() → post_meta.json 수집
   ├─ 지역별 집계 → regions[]
   └─ build_manifest() → /output/manifest.json
  ↓
3️⃣ post.html (각 포스팅마다 생성)
   ├─ BlogHTMLRenderer.save_post()
   └─ /output/posts/{notice_id}/post.html
  ↓
JavaScript 동적 로딩 (클라이언트 사이드)
  ├─ index.html 로드
  ├─ JavaScript: fetch('./manifest.json')
  ├─ 지역 탭 동적 렌더링
  ├─ 카드 그리드 동적 렌더링
  ├─ 페이지네이션 (12개/페이지)
  └─ 링크: ./posts/{notice_id}/post.html
  ↓
Cloudflare Pages 배포
```

---

## 🔑 핵심 설계 원칙

### 1. 성능 최적화
- **비동기 처리**: asyncio + httpx
- **토큰 효율**: LLM 프롬프트 최소화 (Haiku → Flash)
- **캐싱**: ChromaDB 벡터 임베딩
- **정적 + 동적**: index.html은 정적, 콘텐츠는 동적

### 2. 확장성
- **멀티테마**: 7개 CSS 팔레트 (config에서 선택)
- **멀티테넌트**: 각 포스팅 독립적 관리
- **배치 처리**: run_batch_pipeline()
- **API 호환성**: manifest.json (Cloudflare Pages)

### 3. 신뢰성
- **에러 처리**: try-except + 폴백 로직
- **데이터 검증**: UNIQUE 제약 (post_slug)
- **로깅**: setup_logger() + LogStats
- **보안**: path.resolve(), file size limits (100KB)

### 4. 유지보수성
- **명확한 구조**: pipeline/ agents/ models/
- **설정 중앙화**: config.py (API 키, 품질 기준)
- **문서화**: 각 파일에 docstring
- **테스트**: --sample, --monitor, --quality 플래그

---

## 📁 주요 파일 구조

```
KR_APT_DOC_READER/
├── pipeline/
│   ├── config.py              ⭐ 전체 설정 (API 키, URL, 테마)
│   ├── models.py              📊 SQLAlchemy ORM 모델 4개
│   ├── database.py            🔗 DB 연결 + init
│   ├── orchestrator_v2.py     🧠 7단계 LLM 파이프라인 (1000+줄)
│   ├── html_renderer.py       🎨 BlogHTMLRenderer (33KB HTML)
│   ├── index_renderer.py      📄 manifest.json + index.html
│   ├── posting_monitor.py     📊 통계 및 품질 리포트
│   ├── logger.py              📝 로깅 시스템
│   │
│   └── agents/
│       ├── collector.py       📡 CheongYakAPI (공공데이터)
│       ├── pdf_policy.py      📋 모집공고 PDF 파싱
│       └── rag_store.py       🔍 ChromaDB 벡터 저장소
│
├── templates/
│   ├── front_index_template.html  🏠 프론트 페이지 (정적)
│   └── blog_template.html         📝 포스트 템플릿 (동적)
│
├── output/
│   ├── index.html             🌐 프론트 페이지 (생성)
│   ├── manifest.json          📊 포스팅 목록 (생성)
│   ├── posts/
│   │   └── {notice_id}/
│   │       ├── post.html      📄 각 포스팅
│   │       └── post_meta.json 🏷️ 메타데이터
│   └── [이미지, PDF 등]
│
├── run_v2.py                  🚀 메인 진입점
├── test_pipeline.py           ✅ 테스트 스크립트
└── .env                        🔑 환경 변수 (미커밋)
```

---

## 🔌 주요 API 엔드포인트

### 공공데이터포털 API
```
GET https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail
Parameters:
  - serviceKey: PUBLIC_DATA_API_KEY
  - page: 1
  - perPage: 10
  - cond[RCRIT_PBLANC_DE::GTE]: 2026-04-18  (모집공고일)
  - cond[HOUSE_MANAGE_NO::EQ]: 2026000001  (선택)

Response: {
  "data": [{
    "PBLANC_NO": "2026000001",
    "HOUSE_NM": "아파트명",
    "RCRIT_PBLANC_DE": "2026-04-25",
    "TOT_SUPLY_HSHLDCO": 100,
    ...
  }],
  "totalCount": 50,
  "currentCount": 10
}
```

### 내부 Python API
```python
# 수집
await collect_recent_notices(days=7, limit=10)

# 파이프라인
await run_pipeline_v2("2026000001")
await run_batch_pipeline(["2026000001", "2026000002"])

# 렌더링
build_front_index_once()
build_manifest()

# 모니터링
PostingMonitor().get_post_quality_report()
```

---

## 📋 실행 명령어

### 로컬 테스트
```bash
# 샘플 데이터 (API 키 불필요)
python run_v2.py --sample

# 실제 공고 수집 (API 키 필요)
python run_v2.py --api --days 7 --limit 3

# 배치 처리
python run_v2.py --batch notice_id_1 notice_id_2

# 품질 리포트
python run_v2.py --quality
```

### 모니터링
```bash
# 포스팅 통계
python run_v2.py --monitor

# 특정 포스팅 상세 검사
python posting_monitor.py
```

---

## 🚨 주요 제약사항 & 해결책

### 1. 공공데이터 지연
**문제**: 최신 공고가 API에 반영되지 않을 수 있음  
**해결책**:
- 180일 기간으로 조회
- 공고 목록 웹페이지 정기 모니터링
- API 키 활성화 상태 재확인

### 2. HTML 크기 제한
**문제**: 스마트 에디터 ONE 최대 크기 (~50KB)  
**해결책**:
- 현재: 33KB (여유 있음)
- 이미지 외부 링크화
- CSS 인라인 최소화

### 3. 네이버 블로그 제약
**문제**: 외부 CSS/JS 불가능  
**해결책**:
- 모든 스타일 인라인 CSS
- JavaScript 없음 (정적 HTML만)
- 색상은 CSS 변수로 관리

### 4. API 응답 구조 변동
**문제**: 공공데이터포털 API 응답 형식 변경 가능  
**해결책**:
- 다중 응답 형식 지원 (data + response.body.items)
- 필드명 정규화 (OpenAPI + CSV 호환)
- 에러 로깅 상세화

---

## 🎓 다음 개발자를 위한 조언

### 먼저 이해해야 할 것
1. **orchestrator_v2.py** - 7단계 LLM 로직의 핵심
2. **models.py** - ORM 데이터 구조
3. **html_renderer.py** - HTML 생성 로직
4. **collector.py** - API 통신

### 주의사항
- ⚠️ post_slug는 UNIQUE 제약 (notice_id 기반)
- ⚠️ HTML은 50KB 이하 유지
- ⚠️ 인라인 CSS만 사용 (블로그 호환)
- ⚠️ manifest.json은 매 포스팅마다 재생성

### 확장 포인트 (Phase 3)
- FastAPI 대시보드 (web/)
- Google Analytics 연동
- A/B 테스팅 엔진
- 포스팅 편집 UI

---

## 📞 문제 해결 체크리스트

| 증상 | 원인 | 해결책 |
|------|------|--------|
| 400 Bad Request | API 엔드포인트/파라미터 오류 | getAPTLttotPblancDetail 확인, 파라미터 구조 재검증 |
| 0건 조회 | 서버 데이터 부재 | --days 180으로 확장, API 키 활성화 확인 |
| UNIQUE 제약 위반 | 중복 notice_id | DB 초기화 (apt_reader.db 삭제) |
| HTML 크기 초과 | 콘텐츠 많음 | 이미지 삭제, CSS 최소화 |
| 매니페스트 오류 | post_meta.json 구조 변경 | build_manifest() 필드 매핑 재검증 |

---

## 🎯 최종 상태

✅ **Phase 2 완료**
- 7단계 LLM 파이프라인
- 멀티테마 HTML 렌더링
- 정적 + 동적 프론트엔드
- 데이터베이스 저장
- 보안 강화

🔄 **Phase 3 진행 중**
- 웹 대시보드
- 포스팅 편집
- A/B 테스팅
- Analytics

⚠️ **현재 이슈**
- 공공API 데이터 부재 (환경 재확인 필요)
- git 커밋 4개 pending (merge 필요)

---

**작성자**: Claude Code  
**최종 업데이트**: 2026-04-25 16:00 UTC  
**다음 담당자**: [이름 입력]

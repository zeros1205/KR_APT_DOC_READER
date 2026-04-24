# Orchestrator V2 - 청약홈 포스팅 자동화 파이프라인

## 개요

`orchestrator_v2.py`는 청약홈 분양공고를 수집하여 블로그 포스팅을 자동으로 생성하는 **7단계 LLM 기반 파이프라인**입니다.

**특징:**
- ✅ 공공데이터 API 통합 (청약홈 분양정보 조회)
- ✅ Gemini 3.1 Flash LLM 기반 콘텐츠 생성
- ✅ SQLAlchemy ORM 데이터베이스 저장
- ✅ 반응형 HTML 테마 (7가지 팔레트)
- ✅ manifest.json 동적 생성 (Cloudflare 호환)
- ✅ 배치 처리 지원 (여러 공고 동시 처리)
- ✅ API 키 부재 시 더미 데이터 폴백
- ✅ 종료 코드 기반 CI/CD 통합

---

## 아키텍처

### 7단계 파이프라인

```
Stage 1: 데이터 추출      ← 공공데이터 API / 더미 데이터
   ↓
Stage 2: 청약자격 확인    ← Gemini 3.1 Flash Lite
   ↓
Stage 3: 규제정보 확인    ← 공공데이터 + 하드코딩 정책
   ↓
Stage 4: 단지 소개 생성   ← Gemini 3.1 Flash Lite
   ↓
Stage 5: 입지 분석        ← Gemini 3.1 Flash (Google Grounding)
   ↓
Stage 6: Q&A + 자금계획   ← Gemini 3.1 Flash + 정책 정보
   ↓
Stage 7: 품질 평가        ← 자동 검증 (점수 기준)
   ↓
HTML 렌더링 + DB 저장 + manifest.json 업데이트
```

### 데이터 흐름

```
공고 ID (notice_id)
   ↓
run_pipeline_v2(notice_id)
   ├─ apartment_data (Stage 1-3)
   ├─ stage2_result (청약자격)
   ├─ stage3_result (규제정보)
   ├─ stage4_result (단지소개)
   ├─ stage5_result (입지분석)
   ├─ stage6_result (Q&A)
   ├─ stage7_result (품질평가)
   ↓
[DB 저장: Apartment + Posting + PostingContent + PostingMeta]
[HTML 렌더링: output/posts/{notice_id}/post.html]
[메타 저장: output/posts/{notice_id}/post_meta.json]
   ↓
build_manifest() → output/manifest.json
build_front_index_once() → output/index.html (첫 실행만)
```

---

## 사용법

### 1. 개발 환경 설정

```bash
# 저장소 클론
git clone https://github.com/zeros1205/KR_APT_DOC_READER.git
cd KR_APT_DOC_READER

# 의존성 설치
pip install -r requirements.txt

# .env 파일 생성 (API 키 설정)
cp .env.example .env
# .env 파일에 API 키 입력:
#   GEMINI_API_KEY=AIzaSy...
#   PUBLIC_DATA_API_KEY=xxx-xxx-xxx...
```

### 2. 샘플 테스트 (API 키 불필요)

```bash
# 더미 데이터로 전체 파이프라인 테스트
python run_v2.py --sample

# 직접 실행
python -m pipeline.orchestrator_v2 --sample
```

**예상 결과:**
- ✅ 7단계 모두 완료 (API 키 없으면 더미 데이터 사용)
- 📁 `output/posts/2024-sample-001/post.html` 생성
- 📊 `output/manifest.json` 업데이트

### 3. 단일 공고 처리

```bash
# CLI 인터페이스 (run_v2.py 권장)
python run_v2.py 2024-bundang-001

# 직접 실행
python -m pipeline.orchestrator_v2 2024-bundang-001
```

### 4. 배치 처리 (여러 공고)

```bash
# 3개 공고 순차 처리
python run_v2.py --batch 2024-bundang-001 2024-gangnam-002 2024-incheon-003

# 직접 실행
python -m pipeline.orchestrator_v2 --batch ID1 ID2 ID3
```

**출력 예시:**
```
============================================================
  배치 처리 완료: 3/3 성공
============================================================
```

### 5. CI/CD 통합 (GitHub Actions)

#### A. 수동 실행
```bash
# GitHub Actions → run_v2.py --sample 테스트
# https://github.com/zeros1205/KR_APT_DOC_READER/actions
# → "Test Orchestrator V2" → "Run workflow"
```

#### B. 자동 실행
```yaml
# .github/workflows/test_orchestrator_v2.yml
# 매 푸시 시 자동 실행
# 또는 수동으로 workflow_dispatch 트리거
```

#### C. 매일 자동화
```yaml
# .github/workflows/daily.yml
# 매일 UTC 00:00 (KST 09:00) 자동 실행
# 지난 7일 공고 수집 → 최대 3개 처리
```

---

## 파일 구조

```
pipeline/
├── orchestrator_v2.py          ← 메인 파이프라인 (7 stages)
├── html_renderer.py            ← HTML 렌더링 엔진
├── models.py                   ← SQLAlchemy ORM 모델
├── database.py                 ← DB 설정 및 세션
├── config.py                   ← 설정 (API 키, 경로, 테마)
├── themes.py                   ← 블로그 CSS 테마
└── index_renderer.py           ← index.html + manifest.json 생성

output/
├── posts/
│   └── {notice_id}/
│       ├── post.html           ← 생성된 블로그 포스팅
│       └── post_meta.json      ← 메타데이터
├── index.html                  ← 포스팅 목록 (정적)
└── manifest.json               ← 동적 업데이트 (Cloudflare)

run_v2.py                       ← 개선된 진입점 (권장)
run.py                          ← 기존 진입점 (레거시)
```

---

## API 키 설정

### 필수 키

| API | 용도 | 발급처 | 설정값 |
|-----|------|--------|--------|
| **Gemini API** | LLM (main) | https://ai.google.dev | `GEMINI_API_KEY` |
| **공공데이터** | 분양공고 조회 | https://data.go.kr | `PUBLIC_DATA_API_KEY` |

### 선택 키

| API | 용도 | 발급처 | 설정값 |
|-----|------|--------|--------|
| **Unsplash** | 이미지 수집 | https://unsplash.com/api | `UNSPLASH_ACCESS_KEY` |
| **Pexels** | 이미지 수집 | https://pexels.com/api | `PEXELS_API_KEY` |

### 설정 방법

**로컬 개발:**
```bash
# .env 파일 생성
cat > .env << EOF
GEMINI_API_KEY=AIzaSy...
PUBLIC_DATA_API_KEY=xxx-xxx-xxx...
BLOG_THEME=claude
EOF
```

**GitHub CI/CD:**
```
Settings → Secrets and variables → Actions → New repository secret
- GEMINI_API_KEY
- PUBLIC_DATA_API_KEY
```

---

## 출력 예시

### post.html (33KB+)
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <title>샘플 아파트 청약안내</title>
  <meta name="description" content="샘플 아파트 청약 분양가·일정·입지·자격 한눈에">
  ...
</head>
<body>
  <!-- 헤더 + 태그 -->
  <!-- 단지 소개 -->
  <!-- 분양가 테이블 -->
  <!-- 입지 분석 (별점 4개) -->
  <!-- 자금 납부 일정 -->
  <!-- 세금 정보 -->
  <!-- Q&A (6개) -->
  <!-- 면책 고지 + SEO 태그 -->
</body>
</html>
```

### post_meta.json
```json
{
  "apt_name": "샘플 아파트",
  "title": "샘플 아파트 청약 완벽 분석",
  "location": "서울 / 강남구",
  "price_range": "4억~8억",
  "special_supply_date": "2024-05-15",
  "rank1_date": "2024-05-20",
  "region_category": "서울",
  "theme": "claude"
}
```

### manifest.json
```json
{
  "metadata": {
    "generated_at": "2026-04-24T14:06:03.123456",
    "total_posts": 5,
    "version": "2.0"
  },
  "regions": [
    {"code": "all", "name": "전체", "count": 5},
    {"code": "서울", "name": "서울", "count": 2},
    {"code": "경기도", "name": "경기도", "count": 3}
  ],
  "posts": [
    {
      "id": "2024-sample-001",
      "title": "샘플 아파트 청약 완벽 분석",
      "location": "서울 / 강남구",
      "price_range": "4억~8억",
      "timestamp": "2026-04-24T14:06:03"
    }
  ]
}
```

---

## 설정 옵션

### config.py

```python
# LLM 모델 선택
LLM_MODEL = "gemini-1.5-flash"      # 메인 LLM
LLM_LITE_MODEL = "gemini-1.5-flash" # 경량 LLM (청약자격)

# 블로그 테마 (7가지 지원)
BLOG_THEME = "claude"  # claude|notion|intercom|airbnb|stripe|apple|mintlify

# 데이터베이스
DATABASE_URL = "sqlite:///./apt_reader.db"  # SQLite
# DATABASE_URL = "postgresql://user:password@localhost/apt_reader"  # PostgreSQL

# API 엔드포인트
APARTMENT_API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
```

---

## 트러블슈팅

### Q: "API key not found" 오류
**A:** .env 파일이 프로젝트 루트에 있고 `GEMINI_API_KEY` 값이 설정되어 있는지 확인하세요.
```bash
# 확인
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GEMINI_API_KEY'))"
```

### Q: "UNIQUE constraint failed" 오류
**A:** 같은 공고 ID를 두 번 처리하면 발생합니다. DB를 초기화하거나 다른 ID로 테스트하세요.
```bash
rm -f apt_reader.db
python run_v2.py --sample
```

### Q: HTML이 비어있어요
**A:** Gemini API 키가 없으면 더미 데이터를 사용합니다. 실제 API 키를 설정하면 LLM이 콘텐츠를 생성합니다.

### Q: 배치 처리 중 일부 실패
**A:** `--batch` 모드에서 일부 공고가 실패해도 나머지는 계속 처리됩니다. 로그를 확인하세요.

---

## 개발 로드맵

### Phase 1 (완료) ✅
- [x] 7단계 파이프라인 구현
- [x] HTML 렌더링 엔진
- [x] 데이터베이스 저장
- [x] manifest.json 생성
- [x] Gemini 3.1 Flash 통합
- [x] LLM 프롬프트 최적화

### Phase 2 (완료) ✅
- [x] 배치 처리 지원
- [x] run_v2.py 진입점
- [x] 공공API 자동 수집
- [x] 로깅 및 모니터링 (logger.py + posting_monitor.py)
- [x] 모니터링 대시보드 (--monitor, --quality 플래그)

### Phase 3 (진행 중) 🔄
- [ ] 포스팅 수정/업데이트 기능
- [ ] 웹 UI 대시보드
- [ ] A/B 테스트 지원
- [ ] 구글 애널리틱스 연동
- [ ] 메일 알림 기능

---

## 기여 가이드

```bash
# 1. feature 브랜치 생성
git checkout -b feature/your-feature

# 2. 변경사항 적용
python run_v2.py --sample  # 테스트

# 3. 커밋
git commit -m "feat: your feature description"

# 4. PR 생성
git push origin feature/your-feature
# → https://github.com/zeros1205/KR_APT_DOC_READER/pull/new/feature/your-feature
```

---

## 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 문의

- 이슈: https://github.com/zeros1205/KR_APT_DOC_READER/issues
- 토론: https://github.com/zeros1205/KR_APT_DOC_READER/discussions

---

**마지막 업데이트:** 2026-04-24 14:06 UTC

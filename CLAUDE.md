# PROJECT BALI — Claude 작업 지침

## 프로젝트 개요
청약홈 분양공고 데이터를 수집·분석하여 네이버 블로그 HTML 포스팅을 자동생성하는 파이프라인.
발행 방식: 스마트에디터 ONE → [HTML] → 전체 붙여넣기 → 발행 (스크립트/외부CSS 불가, 인라인 스타일만 허용).

## 블로그 글 구조 (스토리텔링 흐름)
딱딱한 공공기관 요약표 형식이 아닌, 마케팅 담당자가 고객을 처음 만나 대화하듯 자연스럽게 흘러야 한다.

```
1. 헤더 배너 (브랜드 + 제목)
2. 단지 소개 인사 (apt_intro: 마케터 어투, 150~200자) → 핵심 요약 테이블 → 조감도 이미지
3. 타입별 분양가 테이블 + 평면도 플레이스홀더
4. 입지 소개 (location_intro: 지역 특색 산문, 100~150자) → 별점 카드 4개
5. 자금 계획 도입 (financial_intro, 80~100자) → 납부 타임라인
6. 세금 정리 테이블
7. 청약 일정 캘린더
8. Q&A 도입 (qa_intro, 60~80자) → Q&A 블록 6개
9. 면책 고지 + SEO 태그
```

## 테마 시스템
`config.py`의 `BLOG_THEME` 값으로 디자인을 전환한다.
지원 테마: `claude` | `notion` | `intercom` | `airbnb` | `stripe` | `apple` | `mintlify`
각 테마의 CSS 토큰은 `pipeline/themes.py`의 `THEMES` 딕셔너리에 정의.

## 디자인 가이드라인

### 타이포그래피 계층 구조
- 본문 폰트: `Pretendard` 우선, 폴백: `Inter, -apple-system, system-ui, sans-serif`
- 헤드라인과 본문의 폰트 크기 대비는 3배 이상 유지 (시각적 위계 확보)

### 컬러 시스템 (사용자 지정 기본값, 테마 미적용 시)
- 주색상 Primary: `#3B82F6` (신뢰도 상징)
- 보조색상 Secondary: `#F59E0B` (행동 유도 및 강조)
- 명도 대비: 모든 텍스트와 배경의 대비 최소 4.5:1 이상 (WCAG AA)

### 상호작용 규칙
- 버튼 hover: 배경색 명도 10% 감소, transition 200ms
- 모든 클릭 가능 요소: `cursor: pointer` 필수

### 웹 접근성 (WCAG 2.1 AA)
- 이미지: 명확한 `alt` 텍스트 필수
- 모든 폼 입력 필드: 연결된 `<label>` 필수
- 키보드 포커스 링(focus ring) 제거 금지

### 성능 제약
- 애니메이션: `transform`과 `opacity` 속성만 사용 (브라우저 부하 최소화)
- 단일 책임 원칙: 컴포넌트 코드 크기 최소화

### 모바일 퍼스트
- 터치 대상(버튼, 링크): 최소 44×44px 이상 확보
- 본문 텍스트 크기: 최소 16px (모바일 가독성)

### 콘텐츠 톤앤매너
- 친절하고 명확한 어조, 명령조 대신 제안형 문장
- 마케팅 담당자가 고객과 대화하는 산문체 (공문서 스타일 금지)

## 이미지 처리 원칙
- 단지 조감도 / 평면도 / 위치지도: 건설사 저작물 → PLACEHOLDER (직접 삽입 안내)
- 자동 수집 이미지(Unsplash/Pexels): CC0 라이선스 + 출처 자동 표기
- 입지 분석 섹션과 자금 계획 섹션: 이미지 없음 (섹션 자체 디자인으로 충분)

## API 키 관리

### 로컬 개발 (`.env` 파일)
```bash
ANTHROPIC_API_KEY=sk-ant-...          # Claude Haiku
OPENAI_API_KEY=sk-...                 # GPT-5.4
GEMINI_API_KEY=AIzaSy...              # Gemini Flash
UNSPLASH_ACCESS_KEY=...               # Unsplash 이미지
PEXELS_API_KEY=...                    # Pexels 이미지
PUBLIC_DATA_API_KEY=...               # 청약홈 OpenAPI
```

### GitHub Secrets (CI/CD 자동 실행)
모든 API 키는 **GitHub Repository Secrets**에 저장됨. Claude Code 스크립트에서 접근 필요 시:
```python
from pipeline.config import PUBLIC_DATA_API_KEY  # 자동 로드
```

**필수 키 설명:**
- `ANTHROPIC_API_KEY` — Claude Haiku (팩트 추출 보조 LLM)
- `OPENAI_API_KEY` — GPT-5.4 콘텐츠 생성/검증 + OpenAI Embeddings
- `GEMINI_API_KEY` — Gemini Flash (Q&A 팩트체크)
- `UNSPLASH_ACCESS_KEY` / `PEXELS_API_KEY` — 이미지 자동 수집
- `PUBLIC_DATA_API_KEY` — 청약홈 공공데이터 OpenAPI (데이터 검증용)

**PUBLIC_DATA_API_KEY 발급:**
1. https://www.data.go.kr 회원가입
2. "한국부동산원_청약홈 분양정보 조회 서비스" 검색 → 활용신청
3. 개발계정 즉시 발급 (40,000회/일)

## 파이프라인 구조
```
pipeline/
  config.py          ← API 키·경로·품질기준 설정
  orchestrator.py    ← 5-에이전트 파이프라인 (Haiku→GPT-5.4→Gemini→CTA→품질)
  html_renderer.py   ← PostData → HTML 렌더링
  themes.py          ← 테마 토큰 딕셔너리 (THEMES)
  image_finder.py    ← 이미지 수집 (PLACEHOLDER + Unsplash)
  agents/
    collector.py     ← 청약홈 API 수집 + 샘플 데이터
    rag_store.py     ← ChromaDB Vector DB
```

## 실행 명령어 요약
```bash
# 로컬 (Windows)
.venv\Scripts\Activate.ps1
python run.py --sample            # 샘플 테스트
python run.py --days 7 --limit 3  # 실제 공고 수집
python test_pipeline.py --step 3  # HTML 렌더링 테스트 (API 불필요)
python test_pipeline.py --step 6  # RAG 연동 전체 테스트

# GitHub Actions: .github/workflows/daily.yml
# 매일 UTC 00:00 (KST 09:00) 자동 실행 / workflow_dispatch 수동 실행
# 기본값: --days 7 --limit 3 / timeout 60분
```

### GitHub Actions 워크플로우

#### 📊 분양가·일정 감사 워크플로우
**파일**: `.github/workflows/audit_prices.yml`
**자동 트리거**: Daily 워크플로우 완료 후 자동 실행 (포스트 개수가 5개 배수일 때만)
**대상 데이터**: `main` 브랜치의 모든 포스트 (output/posts/*/post_meta.json)

**작동 원리**:
- Daily 워크플로우가 완료될 때마다 자동으로 시작
- 현재 포스트 개수가 5개, 10개, 15개... 등 5개 배수인 경우에만 감사 실행
- 그 외의 경우는 자동으로 스킵 (LLM 토큰 소비 절감)

**수동 실행** (선택사항):
1. GitHub → **Actions** 탭
2. **"분양가·일정 감사"** 워크플로우 선택
3. **Run workflow** 버튼 (main 브랜치)
4. **Run** 클릭

**결과**: 모든 포스트의 분양가·모집공고·일정 정보를 JSON으로 수집 → artifacts 저장

#### ⏰ 일일 자동 실행
**파일**: `.github/workflows/daily.yml`
**실행 주기**: 매일 UTC 00:00 (KST 09:00)
**실행 브랜치**: main
**수동 실행**: workflow_dispatch (Actions 탭 → Daily workflow → Run workflow)
**기본값**: `--days 7 --limit 3` (지난 7일, 최대 3개)

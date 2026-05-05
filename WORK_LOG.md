# 작업 내역 로그 — 정과장의 청약노트

> 기준일: 2026-04-21

---

## 체크리스트 (최신)

| # | 지시 내용 | 코드 수정 | 라이브 |
|---|-----------|:---------:|:------:|
| 1 | **프론트 페이지** — 12건/페이지 JS 페이지네이션 | Y | Y |
| 2 | **프론트 페이지** — 모집공고일 최신순 정렬 | Y | Y |
| 3 | **프론트 페이지** — 단지명 검색바 추가 (탭 메뉴 하단) | Y | Y |
| 4 | **상세 페이지** — 총세대수 vs 공급세대수 구분 표기 | Y | Y* |
| 5 | **입지 분석** — Gemini 작성 → Claude 검증 파이프라인 (신규 포스트) | Y | Y* |
| 6 | **입지 분석** — 기존 포스트 전체 재작성 | Y | N |
| 7 | **main 머지** — `claude/review-claude-md-nTSPo` → main | Y | Y |
| 8 | **헤더 우측 버튼** — 컬러테마·청약홈 버튼 흰색 변경 | Y | Y |
| 9 | **Cloudflare 빌드 복구** — `wrangler.jsonc` 추가 | Y | Y |
| 10 | **상세 페이지** — `모집공고문 바로가기` 버튼 제거 (전체 45개) | Y | Y* |
| 11 | **상세 페이지** — `전매제한 안내` 카드 빈 내용 → 안내 문구 추가 (전체) | Y | Y* |
| 12 | **상세 페이지** — apt_intro "총 N세대 규모로" → "총 N세대가 공급되며" (전체) | Y | Y* |
| 13 | **상세 페이지** — 네이버 지도 N 사각형 아이콘 → 블루그린 위치 핀 SVG 교체 (전체) | Y | Y* |
| 14 | **상세 페이지** — Section 1에 청약 규제 정보 카드 추가 (투기과열·실거주·전매제한) | Y | Y* |
| 15 | **헤더 컬러테마** — 팔레트 전환 시 포스트 바디 전체 accent 색상 반응하도록 CSS var 적용 | Y | Y* |

> **Y\*** : 코드 반영 완료, 다음 파이프라인 실행(신규 포스트)부터 적용  
> **#6** : `rewrite_location.py` 스크립트 및 GitHub Actions workflow 준비 완료. GitHub Actions → "기존 포스트 입지 분석 재작성" 수동 트리거 필요

---

## 상세 작업 내역

### #1 · #2 · #3 — 프론트 페이지 개편
**파일**: `pipeline/build_index.py`, `output/index.html`

- `load_posts()`: `*/post.html` glob으로 변경, `post_meta.json` 없는 포스트도 HTML 파싱으로 메타 추출
- 정렬: `rank1_date` 기준 최신순 내림차순
- 검색바: `#search-input` 입력 → `_applyFilters()` 실시간 필터
- 페이지네이션: `POSTS_PER_PAGE = 12`, `renderPagination()` / `goPage()` 함수, `#pagination` div
- `data-apt-name` 속성으로 카드별 단지명 검색 지원

---

### #4 — 총세대수 vs 공급세대수 구분
**파일**: `pipeline/orchestrator.py`, `pipeline/html_renderer.py`

- `FACT_EXTRACTION_PROMPT`: `total_households` (단지 전체 세대수), `notice_date` (모집공고일) 필드 추가
- `CONTENT_GEN_PROMPT`: 혼용 방지 원칙 추가
  - `total_households` 있으면 → "총 X세대 규모 단지" 언급 가능, 공급세대수는 별도 구분
  - `total_households` null이면 → 총세대수 추측·언급 절대 금지
- `PostData`: `total_households: str = ""` 필드 추가
- `save_post()`: `post_meta.json`에 `total_households` 저장

---

### #5 — 입지 분석 Gemini→Claude 파이프라인
**파일**: `pipeline/orchestrator.py`

파이프라인 7-에이전트 구조로 재편:

| Agent | 역할 | 모델 |
|-------|------|------|
| 1 | 팩트 추출 | Claude Haiku |
| **2** | **입지 분석 생성** | **Gemini Flash** |
| **3** | **입지 분석 검증** | **GPT-5.4** |
| 4 | 콘텐츠 생성 | GPT-5.4 |
| 5 | Q&A 팩트체크 | Gemini Flash |
| 6 | CTA 최적화 | — |
| 7 | 품질 검수 | — |

- `LOCATION_ANALYSIS_PROMPT`: 비수도권 지하철 언급 금지, 도보 거리 기준(5분≈400m), 별점 기준 명시
- `LOCATION_VERIFY_PROMPT`: GPT-5.4가 역명·학교명·비수도권 오류 교정
- `agent_location_analysis_gemini()` / `agent_location_verify_gpt()` 함수 추가
- `run_pipeline()`: location_data 생성 후 GPT-5.4 content에 병합(overwrite)
- Gemini 실패 시 GPT-5.4 생성값으로 자동 폴백

---

### #6 — 기존 포스트 입지 분석 재작성 (미실행)
**파일**: `rewrite_location.py`, `.github/workflows/rewrite_location.yml`

- `rewrite_location.py`: 기존 `post.html`에서 팩트 추출 → Gemini 분석 → Claude 검증 → HTML 패치
- GitHub Actions workflow: 수동 트리거(workflow_dispatch), dry-run 옵션 지원
- **실행 방법**: GitHub → Actions → "기존 포스트 입지 분석 재작성" → Run workflow

---

### #7 — main 브랜치 머지
`claude/review-claude-md-nTSPo` → `main` 머지

- 충돌 해소 전략: pipeline 파일은 main 버전 유지, post.html 11개는 feature 브랜치 버전 유지
- 결과: 45개 포스트(main 34개 + feature 11개) 통합

---

### #8 — 헤더 우측 버튼 흰색 변경
**파일**: `pipeline/shared_ui.py`, `output/index.html`, `output/posts/*/post.html` (43개)

- 팔레트 토글 버튼: `rgba(255,255,255,0.2/0.6)` → `#fff` (border + color)
- 청약홈 링크: `rgba(255,255,255,0.12/0.5)` → `#fff`
- hover 시: `rgba(255,255,255,0.7)` (살짝 dimming 효과 유지)
- SVG 아이콘: `fill="currentColor"`라 자동으로 흰색 적용
- 일괄 패치: `patch_posts6.py` 방식으로 43개 post.html Python 스크립트 일괄 처리

---

### #9 — Cloudflare Worker 빌드 복구
**파일**: `wrangler.jsonc`

- **원인**: `cloudflare/workers-autoconfig` 브랜치에만 있던 `wrangler.jsonc`가 main에 누락
- **증상**: `npx wrangler versions upload` 실행 시 "Missing entry-point to Worker script or to assets directory" 에러
- **해결**: `wrangler.jsonc` main에 추가
  ```json
  {
    "name": "kraptdocreader",
    "compatibility_date": "2026-04-21",
    "assets": { "directory": "output" }
  }
  ```
- main → `claude/review-claude-md-nTSPo` 동기화 (Cloudflare가 해당 브랜치를 바라보고 있었으므로)

---

## 배포 구조 메모

| 항목 | 내용 |
|------|------|
| 호스팅 | Cloudflare Workers (정적 에셋 서빙) |
| 서빙 브랜치 | `main` (Production branch) |
| 배포 트리거 | main push → Cloudflare 자동 빌드 |
| 빌드 명령 | `npx wrangler versions upload` |
| 에셋 경로 | `output/` 폴더 |
| 자동화 | GitHub Actions `daily.yml` — 매일 KST 09:00 실행 |
| GitHub Pages | 미사용 (private 저장소) |

---

## 미완료 항목

- **#6**: GitHub Actions에서 "기존 포스트 입지 분석 재작성" workflow 수동 실행 필요
- **build_index.py 정렬**: `rank1_date` 기준 정렬 확인 필요 (meta.json 없는 포스트의 날짜 파싱)

---

## 2026-05-05 작업 세션 (GitHub Copilot)

### 브랜치 상태 정리
- `codex/mobile-app-public-notices` → `origin/main` 기준 **rebase** 완료
  - 중복 커밋 자동 제거, 모바일앱 고유 커밋 7개만 정리
  - `git push --force-with-lease` 로 원격 반영

---

### SEO 개선

#### ads.txt 추가
- **파일**: `output/ads.txt`
- **내용**: `google.com, pub-8234120897033274, DIRECT, f08c47fec0942fa0`
- Google AdSense 인벤토리 인증용, 루트 디렉토리 배치 필수

#### Cloudflare www → apex 301 리다이렉트
- **설정 위치**: Cloudflare Dashboard → Rules → Redirect Rules
- **템플릿**: "Redirect from WWW to root" 사용
- **규칙**: `https://www.*` → `https://${1}` (301 Permanent)
- **효과**: PSI SEO 점수 36 → **100** (www 도메인 HTTP 522 오류 해결)

#### 포스트 JSON-LD 구조화 데이터 일괄 삽입
- **스크립트**: `tools/patch_seo_structured_data.py`
- **대상**: `output/posts/*/post.html` 183개 전체
- **추가 내용**:
  - `Article` 타입 JSON-LD (headline, datePublished, image, publisher, isPartOf)
  - `BreadcrumbList` JSON-LD (홈 → 단지명 2단계)
- **효과**: Google 리치 결과(Rich Result) 및 Google Discover 노출 조건 충족

#### OG 이미지 크기 메타 추가
- **파일**: `pipeline/html_renderer.py`, `templates/front_index_template.html`
- **추가 태그**: `og:image:width=1200`, `og:image:height=630`, `og:image:type=image/jpeg`
- **효과**: 카카오톡·SNS 공유 시 이미지 즉시 렌더링

---

### 성능 개선 (PageSpeed Insights)

#### 폰트 렌더링 차단 제거 (−3,160ms)
- **파일**: `pipeline/shared_ui.py`, `templates/front_index_template.html`, `tools/patch_font_preload.py`
- **변경**: `<link rel="stylesheet">` → `<link rel="preload" onload>` + `<noscript>` 폴백
- **대상**: 모든 포스트 HTML 184개 + `output/index.html` 일괄 적용
- **효과**: FCP/LCP 대폭 개선

#### CLS 0.378 → 0.012 수정
- **원인**: 카드 그리드 JS 동적 삽입 시 레이아웃 급변
- **수정 1**: `output/index.html` 카드 그리드 `min-height` 반응형 예약
  - 데스크톱(3열): `--cards-min-h: 3200px`
  - 태블릿(2열): `--cards-min-h: 5000px`
  - 모바일(1열): `--cards-min-h: 0px` (LCP 영향 방지)
  - 카드 로드 완료 후 `grid.style.minHeight = ''` 해제
- **수정 2**: 로고 `<img>` 태그에 `width="38" height="38"` 속성 추가 (`pipeline/shared_ui.py`)

#### JS 강제 리플로우 제거 (TBT 개선)
- **원인**: `_bindCardTitleMarquee()` — 카드마다 `scrollWidth`/`clientWidth` 읽기→쓰기 반복
- **제거**: 마퀴 애니메이션 JS 완전 제거 (CSS `is-marquee`, `card-title-pingpong` 삭제)
- **대체**: `text-overflow: ellipsis` (말줄임) + 배치 읽기/쓰기 방식 적응형 폰트 조정
  - 기본: 20px
  - 오버플로우 감지 시: 18px (단일 리플로우로 처리)
- **파일**: `output/index.html`, `pipeline/index_renderer.py`, `templates/front_index_template.html`

---

### 버그 수정

#### `remove_special_finance_ratio_bar_from_html` return 누락
- **파일**: `pipeline/html_renderer.py`
- **증상**: `test_pipeline.py --step 3` 실행 시 `TypeError: expected string, got NoneType`
- **원인**: 함수 마지막 `return html` 누락으로 `None` 반환
- **수정**: `return html` 추가

#### `test_pipeline.py` 필드명 불일치
- **변경**: `life_score` / `life_detail` → `feature_score` / `feature_detail`

---

### PSI 최종 결과 (2026-05-05 기준)

| 항목 | 이전 | 현재 |
|---|---|---|
| 성능 (데스크톱) | — | **97** |
| 성능 (모바일) | — | **74+** (개선 진행 중) |
| 접근성 | 68 | **95** |
| 권장사항 | 96 | **100** |
| SEO | 36 | **100** |

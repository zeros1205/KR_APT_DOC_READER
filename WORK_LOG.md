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
| **3** | **입지 분석 검증** | **Claude Sonnet** |
| 4 | 콘텐츠 생성 | Claude Sonnet |
| 5 | Q&A 팩트체크 | Gemini Flash |
| 6 | CTA 최적화 | — |
| 7 | 품질 검수 | — |

- `LOCATION_ANALYSIS_PROMPT`: 비수도권 지하철 언급 금지, 도보 거리 기준(5분≈400m), 별점 기준 명시
- `LOCATION_VERIFY_PROMPT`: Claude가 역명·학교명·비수도권 오류 교정
- `agent_location_analysis_gemini()` / `agent_location_verify_claude()` 함수 추가
- `run_pipeline()`: location_data 생성 후 Claude content에 병합(overwrite)
- Gemini 실패 시 Claude 생성값으로 자동 폴백

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

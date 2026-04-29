# 작업 로그 — 2026-04-29 (KST 09:30 ~ 19:30)

`apt-note.com` 정적 사이트의 분석·SEO 인프라 도입 + 배포 브랜치 정리. 약 10시간 동안 진행된 단일 세션 요약.

## 결과 요약

| 항목 | 결과 |
|---|---|
| Live deploy 브랜치 | `codex/golden-pipeline-recovery` → **`main`** 으로 전환 |
| GA4 (`G-D5SCQRYKSM`) | 모든 페이지 (홈/정책/186 단지) **라이브 적용 ✓** |
| Google "Site name in Search" 스키마 | 홈페이지 `WebSite` JSON-LD 적용 (재크롤 후 표시 예정) |
| Cloudflare Bot Fight Mode | OFF (GA 검증 차단 해소) |
| `codex/golden-pipeline-recovery` | **0건 변경** (read-only 보장) |
| main 폐기된 commit | 58개 (V2/DB 실험 잔재 등, 백업 없이 폐기 결정) |

## 작업 타임라인

### 1. 브랜치 동기화 — codex 클론
`claude/review-golden-pipeline-HXhKI`를 `origin/codex/golden-pipeline-recovery` (`9ffa56d`)으로 hard reset. 두 브랜치 byte-identical 확인. codex는 이후 어떤 작업에서도 안 건드림.

### 2. GA4 도입 (스니펫: `G-D5SCQRYKSM`)
사용자가 제공한 정확한 스니펫을 byte-for-byte 그대로 4개 렌더 경로에 삽입.

- **편집된 템플릿/렌더러** (3 templates + 1 renderer):
  - `templates/front_index_template.html` — `</head>` 직전
  - `templates/privacy_template.html` — `</head>` 직전
  - `templates/terms_template.html` — `</head>` 직전
  - `pipeline/html_renderer.py:1153` — post 페이지 `<head>` 빌더 (f-string 내부라 `{}` 이스케이프)
- **제외**: `templates/blog_template.html`은 body fragment(자체 `<head>` 없음)이므로 의도적 미삽입. post 페이지의 GA는 `pipeline/html_renderer.py`에서 처리됨.
- **신규 도구**: `tools/inject_analytics.py` — idempotent 정적 HTML 패치. 마커 `<!-- ga4-injected:G-D5SCQRYKSM -->` 으로 중복 방지. `output/` 재귀 스캔.
- **일괄 패치**: `output/index.html` + `output/privacy.html` + `output/terms.html` + `output/posts/*/post.html` = **189개 파일**.
- **Idempotent 검증**: 두 번째 실행 시 `modified=0, skipped=189`. ✓

### 3. Draft PR 생성 (#13)
`claude/review-golden-pipeline-HXhKI` → `main` Draft PR. CI(Cloudflare Pages 체크) success. 리뷰/코멘트 0건.

### 4. CLAUDE.md 정비
사용자 명시: "네이버 블로그 발행은 더 이상 안 함." `CLAUDE.md` 4행 수정 — "스마트에디터 ONE 발행" → "정적 사이트 (Cloudflare Pages) 단일 타깃, `<script>`/외부 CSS 허용". `templates/blog_template.html`이 body fragment로 남는 기술적 이유 보존. PR #13 본문도 동일 맥락으로 갱신.

### 5. Google SERP 사이트 이름 문제
검색 결과에 도메인(`apt-note.com`)이 그대로 표시되는 스크린샷 받음. 원인: 홈페이지에 `WebSite` JSON-LD 스키마 부재. 조치:
```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "정과장의 청약노트",
  "alternateName": "apt-note",
  "url": "https://apt-note.com/"
}
</script>
```
`templates/front_index_template.html`과 `output/index.html` 두 곳에 동시 삽입 (즉시 deploy + 미래 렌더 모두 커버). Google 재크롤 후 검색 결과의 도메인 표기가 사이트 이름으로 교체됨 (보통 며칠~수 주).

### 6. main force-push (대형 결정)
`codex/golden-pipeline-recovery`가 실제 deploy 브랜치임이 밝혀짐. main은 58 commit 뒤떨어진 V2/DB 실험 잔재. 사용자 결정: "백업 없이 force-push, 58 commit 폐기".

```bash
git push origin claude/review-golden-pipeline-HXhKI:main \
  --force-with-lease=main:062ea67
```

`062ea67` → `484b6e8` (forced update). PR #13은 head=base가 되어 자동 무효 → close.

### 7. Cloudflare Pages deploy 전환
사용자가 Cloudflare 대시보드에서 production branch를 `codex/golden-pipeline-recovery` → `main`으로 변경. 새 build 트리거됨.

### 8. GA 라이브 검증 — Cloudflare Bot Fight Mode 트러블슈팅
초기 증상: GA Tag Assistant + GA Admin "Test Installation" 모두 "tag not detected".

진단 흐름:
- 저장소 측 검증: origin/main:output/index.html 에 GA 3건 매치 ✓ (배포 측 문제로 좁힘)
- WebFetch로 라이브 fetch 시도 → **403 Forbidden**
- 사용자 Cloudflare Security 화면 스크린샷 공유:
  - **Block AI bots: Block on all pages** (ON) — AI 학습 크롤러만 차단, GA/SEO 무관
  - **Bot fight mode: JS Detections On** (ON) — Google 검증 크롤러까지 오탐 차단 → **이게 원인**
- 사용자가 Bot fight mode OFF → GA 정상 검출. ✓
- Block AI bots는 그대로 ON 유지 (AI 학습 데이터 보호 의도).

### 9. PSI 보고서 검토 시도 (보류)
사용자가 PageSpeed Insights URL 공유. 환경 제약(WebFetch 403, PSI API anonymous quota 429)으로 자동 fetch 불가. 스크린샷/JSON 공유 요청 → 미응답 상태로 보류.

## Commit 히스토리 (codex 9ffa56d 위에 5건)

| SHA | 시각 (UTC) | 메시지 |
|---|---|---|
| `a1f3b09` | 00:38 | feat(analytics): add GA4 (G-D5SCQRYKSM) snippet to all `<head>` renderers |
| `510f4d5` | 00:39 | tools: add inject_analytics.py for static HTML GA patching |
| `d360f2e` | 00:39 | chore(analytics): inject GA4 snippet into existing static pages (189 files) |
| `ea52d85` | 00:45 | docs(claude.md): drop Naver blog publishing constraint |
| `484b6e8` | 00:53 | feat(seo): add WebSite JSON-LD to homepage for Google site name |

이 5개 commit은 force-push로 `main`에 그대로 적용됨.

## 변경 파일 인덱스

**소스 5개**:
- `templates/front_index_template.html` (GA + WebSite JSON-LD)
- `templates/privacy_template.html` (GA)
- `templates/terms_template.html` (GA)
- `pipeline/html_renderer.py` (post `<head>` 빌더에 GA)
- `CLAUDE.md` (네이버 발행 제약 제거)

**신규 도구 1개**:
- `tools/inject_analytics.py`

**산출물 일괄 패치 189개**:
- `output/index.html`, `output/privacy.html`, `output/terms.html`
- `output/posts/*/post.html` (186개)

## 미해결·후속 작업

| 항목 | 우선순위 | 비고 |
|---|---|---|
| **모든 post.html `<title>` 정적 문제** | 🔴 높음 | `pipeline/html_renderer.py:1129` — 현재 모든 단지 페이지가 `<title>정과장의 청약노트</title>`로 동일. og:title은 동적인데 title만 정적. SEO 최대 손실점. |
| **방문자 증대 보고서** | 🟡 중간 | 사용자 요청으로 시작했으나 GA/사이트 이름 작업으로 우선순위 밀려 보류. `docs/visitor_growth_report.md`로 차기 작성. |
| **PSI 보고서 검토** | 🟡 중간 | 사용자가 스크린샷/JSON 공유 시 진행. |
| **GA DRY 리팩터** | 🟢 낮음 | 동일 스니펫이 5곳에 리터럴로 박혀 있음 (templates 3 + renderer + tool). `pipeline/shared_ui.py`에 `ANALYTICS_HEAD` 상수 1개 + `{{ANALYTICS_HEAD}}` 플레이스홀더로 통일 가능. |
| **Google Search Console / Naver Search Advisor 등록** | 🟡 중간 | 인덱싱 가속 + 검색 노출 모니터링용. verification 메타 태그 추가 작업 필요. |
| **post.html JSON-LD (Article / RealEstateListing)** | 🟢 낮음 | rich result 자격 확보. |
| **단지별 OG 이미지** | 🟢 낮음 | 현재 모든 페이지가 같은 `og-image.jpg` 공유 → SNS 공유 CTR 저하. |

## 학습된 함정

1. **`templates/blog_template.html`은 body fragment** — `<head>` 없음. post 페이지의 GA는 `pipeline/html_renderer.py:1123-1153`의 `<head>` 빌더(f-string)에서 처리. f-string 내 JS 중괄호는 `{{}}` 이스케이프 필수.
2. **Cloudflare Bot Fight Mode** — Free 플랜 기본 ON일 때가 많음. Google GA 검증 크롤러까지 오탐으로 차단 → "tag not detected"의 흔한 원인. `Block AI bots`(AI 학습 차단)와 분리된 별개 기능.
3. **사용자가 제공한 GA 스니펫의 byte-perfect 보존** — 마크다운 list item 안에 코드블록을 넣으면 indentation이 자동으로 prefix됨. 정확 보존 필요 시 list 밖 또는 별도 섹션에 두어야 함.
4. **Google "Site name in Search"**는 og:site_name 만으로는 부족. 홈페이지의 `WebSite` JSON-LD가 1차 신호.
5. **main이 deploy 브랜치가 아닐 수 있음** — Cloudflare Pages production branch 설정을 별도 확인. 코드 푸시만으로는 라이브 반영 안 됨.

## 보호된 자산

- `origin/codex/golden-pipeline-recovery` (`9ffa56d`) — **0건 push, 0건 변경**. 비상시 deploy 롤백 대상.
- `https://apt-note.com/` 라이브 가용성 — 모든 작업이 무중단으로 진행됨.

---
세션 ID: `01CLWubLJG6vWDG3b3ezfZCu`

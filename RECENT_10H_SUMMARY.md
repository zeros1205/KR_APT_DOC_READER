# 최근 10시간 작업 요약

- 작성 시각: 2026-04-24 07:25:21 +09:00
- 기준 브랜치: `main`
- 현재 반영 기준 HEAD: `b2fcecc`

## 요약

최근 10시간 동안의 작업은 크게 세 축으로 진행됐다.

1. 프런트 페이지(`output/index.html`) 복구 및 UI 정리
2. 상세 포스트 생성 파이프라인 리팩토링
3. PDF 기반 정보 추출 정확도 보정 및 자금 계획 계산 로직 제거

## 주요 변경 내역

### 1. 프런트 페이지 복구 및 안정화

- 카드 그리드가 사라졌던 `index.html`을 복구했다.
- 프런트 생성 경로를 최신 템플릿 기반으로 재구성했다.
- 헤더 검색창을 자동완성 레이어 방식으로 변경했다.
- sticky 지역 필터, 플로팅 최상단 버튼, 푸터 레이아웃, 로고, USER GUIDE 카드 등 UI를 정리했다.
- 배포 루트가 `output/`라는 점을 기준으로 다시 확인하고 운영 규칙에 반영했다.

관련 커밋:

- `4956917` `fix: restore index cards and refresh generated output flow`
- `2e4003c` `fix: restore cards on latest index layout`
- `bffb24b` `refactor: stabilize front page generation and ui`
- `d694806` `fix: restore static front deployment entrypoint`

### 2. 상세 포스트 생성 파이프라인 정리

- `힐스테이트 판교역` 최신 `post.html` 구조를 상세페이지 기준 템플릿으로 고정하는 방향으로 리팩토링을 진행했다.
- LangGraph 기반 상세 생성 경로를 묶고, 상세페이지 템플릿과 렌더러를 정리했다.
- 입지 분석 섹션 구조를 기존 카드형에서 3개 섹션 중심 서술형 구조로 바꾸는 리팩토링을 진행했다.

관련 커밋:

- `0a4b154` `refactor: rebuild detail post generation pipeline`

### 3. 테스트 PDF 정리

- Git에 추적되던 테스트용 PDF 3개를 삭제해 다시 살아나지 않도록 정리했다.

관련 커밋:

- `6d430b7` `chore: remove tracked test pdf files`

### 4. 신규 생성 포스트 반영

- GitHub Actions 워크플로우 실행 결과로 생성된 포스트를 반영하는 커밋이 올라왔다.
- 최근 생성 결과 기준으로 `output/posts/2026-04-23_e편한세상_부천_어반스퀘어/`가 생성되었고,
  `output/processed_notices.json`에는 `2026000152`가 기록됐다.

관련 커밋:

- `302aab2` `chore: refresh generated posts [skip ci]`
- `7597144` `chore: refresh generated posts [skip ci]`

### 5. PDF 다운로드/추출 및 자금 계획 로직 보정

- 파이프라인이 로컬 PDF를 우선 참조하던 흐름을 제거하고, `notice_url` 기반 온라인 PDF 다운로드를 기본 경로로 고정했다.
- `2026000152 e편한세상 부천 어반스퀘어` PDF 기준으로 규제표 추출 오류를 수정했다.
- 확인된 규제정보:
  - 규제지역 여부: `비규제지역`
  - 재당첨 제한: `없음`
  - 전매제한: `1년`
  - 거주의무기간: `없음`
  - 분양가상한제: `미적용`
  - 택지유형: `민간택지`
- `05 · 자금 계획`에서 분양가에 비율을 곱해 `약 얼마` 식으로 실제 금액을 계산하던 로직을 제거했다.
- 자금 관련 프롬프트도 강화하여,
  - 비율과 일정만 설명
  - 계산형 금액 문구 금지
  - 공고문에 실제 금액이 명시된 경우만 인용
  규칙을 추가했다.

관련 커밋:

- `b2fcecc` `fix: enforce online pdf parsing and remove financial amount calculations`

## 운영 이슈와 대응

### Cloudflare 404 이슈

- `output/index.html`이 빠진 상태의 버전이 배포되며 `apt-note.com` 루트가 404가 되는 문제가 발생했다.
- 이후 `output/index.html`, `robots.txt`, `sitemap.xml` 복구 및 재배포 경로를 점검했다.
- 배포 구조상 서비스 진입점은 `output/` 기준이라는 점을 운영 규칙으로 고정했다.

### Git/로컬 충돌 정리

- 파이프라인 수정 커밋 푸시 후 로컬 stash 복원 과정에서 `output/index.html`, `output/processed_notices.json`, `output/sitemap.xml`, 생성 포스트 파일에 충돌이 발생했다.
- 원격 최신 상태를 기준으로 충돌을 해소했고, 현재 작업 폴더는 clean 상태다.

## 현재 상태

- `origin/main` 반영 완료
- 로컬 작업 폴더 clean 상태
- 남아 있는 중점 과제:
  1. 신규 생성 포스트 품질 검증
  2. 필요 시 URL slug를 `notice_id` 기반으로 전환
  3. 1건 검증 후 대량 생성 워크플로우 실행

## 최근 10시간 커밋 목록

```text
b2fcecc fix: enforce online pdf parsing and remove financial amount calculations
7597144 chore: refresh generated posts [skip ci]
6d430b7 chore: remove tracked test pdf files
d694806 fix: restore static front deployment entrypoint
0a4b154 refactor: rebuild detail post generation pipeline
302aab2 chore: refresh generated posts [skip ci]
bffb24b refactor: stabilize front page generation and ui
2e4003c fix: restore cards on latest index layout
4956917 fix: restore index cards and refresh generated output flow
```

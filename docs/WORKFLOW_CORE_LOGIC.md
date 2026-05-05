# 워크플로우 핵심 로직

이 문서는 GitHub Actions와 생성 스크립트가 지켜야 하는 계약이다. 워크플로우의 동작 기준은 대화 기록이 아니라 이 저장소의 코드와 이 문서에 남긴다.

## 전체 흐름

1. `codex-분양공고 데이터 가져오기`
   - 파일: `.github/workflows/codex-collect-notices.yml`
   - 실행 스크립트: `collect_notices_weekly.py`
   - 역할: 공공데이터 API와 청약Home 링크 정보를 수집해 `output/data_cache/notices/*.json`에 저장한다.
   - 원칙: 이 단계는 PDF를 다운로드하지 않는다. 민간분양 공고 데이터 캐시만 만든다.

2. `codex-청약홈 링크 목록 만들기`
   - 파일: `.github/workflows/codex-export-notice-urls.yml`
   - 실행 스크립트: `export_notice_urls.py`
   - 역할: 캐시된 공고 중 PDF가 필요한 민간분양 공고의 청약Home URL 목록을 `output/notice_url_exports/*_notice_urls.md`로 만든다.
   - 원칙: 사용자가 이 목록을 보고 청약Home에서 PDF를 내려받아 GitHub의 `input/pdfs/`에 올린다.

3. 사용자가 PDF 업로드
   - 위치: `input/pdfs/`
   - 권장 파일명: `{notice_id} {apt_name} 입주자모집공고문.pdf`
   - 예: `2026000174 더샵 중앙로역센터폴 입주자모집공고문.pdf`
   - 원칙: 페이지 생성은 이 폴더의 PDF를 근거 자료로 사용한다.

4. `codex-페이지 생성하기`
   - 파일: `.github/workflows/codex-generate-pages.yml`
   - 실행 스크립트: `generate_posts_from_cache.py`
   - 기본 입력: `require_pdf=true`
   - 역할: `output/data_cache/notices/*.json`과 `input/pdfs/*.pdf`를 조합해 상세 포스트와 프런트 카드 인덱스를 생성한다.
   - 산출물:
     - `output/posts/{notice_id}/post.html`
     - `output/posts/{notice_id}/post_meta.json`
     - `output/posts_index.json`
     - `output/posts_index.js`
     - `output/sitemap.xml`
     - `output/robots.txt`
     - `output/processed_notices.json`

5. `codex-모바일앱 빌드 검증`
   - 파일: `.github/workflows/codex-mobile-app.yml`
   - 역할: `mobile-app/**` 변경 시 Capacitor Android 디버그 빌드가 깨지지 않는지 검증한다.
   - 원칙: 웹 콘텐츠 생성 워크플로우가 아니며, 웹 데이터 변경은 앱이 웹/인덱스 데이터를 읽는 구조와 별도로 관리한다.

## PDF 우선 원칙

민간분양 상세 포스트의 규제/금융 정보는 PDF가 최우선이다.

- `generate_posts_from_cache.py`는 `input/pdfs/`, 상위 `PDF/`, `output/pdfs/` 순서로 `{notice_id}*.pdf`를 찾는다.
- PDF가 있으면 `pipeline/agents/pdf_policy.py`로 규제 정보를 추출한다.
- PDF가 있으면 `pipeline/agents/pdf_finance.py`로 계약금/중도금/잔금 구조를 추출한다.
- PDF에서 읽은 값 또는 캐시의 `manual_regulation`은 API/LLM 결과보다 우선한다.

반드시 PDF 우선으로 처리해야 하는 핵심 필드:

- `regulated_zone`
- `readmission_limit`
- `resale_restriction`
- `live_requirement`
- `price_cap`

## 재발 방지 규칙

`codex-페이지 생성하기`를 `require_pdf=true`로 실행할 때 민간분양 공고에 PDF가 있는데 정책 필드가 하나도 추출되지 않거나, 전매제한(`resale_restriction`)이 PDF 추출값 또는 `manual_regulation`으로 확인되지 않으면 포스트 생성을 실패시킨다.

이유:

- `--require-pdf`는 원래 "PDF 파일이 존재하는 공고만 생성"이라는 의미였다.
- 하지만 PDF 파일이 있어도 스캔본이거나 텍스트 레이어가 없으면 `pdfplumber`가 정책 문구를 못 읽을 수 있다.
- 이때 그대로 진행하면 API/LLM 기본값이 들어가 `전매제한 없음` 같은 잘못된 정보가 라이브에 나갈 수 있다.

실패 시 처리:

- PDF 추출 로직을 보강한다.
- 또는 사람이 PDF를 확인해 캐시 JSON에 `manual_regulation`을 명시한다.

예:

```json
"manual_regulation": {
  "resale_restriction": "6개월"
}
```

## 2026000174 사고 기록

공고 `2026000174 더샵 중앙로역센터폴`은 PDF 공고문에는 전매제한이 `6개월`로 기재되어 있었지만, 생성된 웹 포스트에는 `전매제한 없음`으로 노출되었다.

원인:

- PDF는 `input/pdfs/`에 있었지만 정책 텍스트 추출 결과가 비었다.
- 캐시의 `document.pdf_policy_text`도 비어 있었다.
- 생성 파이프라인이 PDF 정책 추출 실패를 치명 오류로 보지 않고 기본 추론값으로 계속 진행했다.

즉시 수정:

- `output/posts/2026000174/post.html`의 전매제한 표시를 `6개월`로 수정했다.
- `output/posts/2026000174/post_meta.json`의 `resale_restriction`을 `6개월`로 수정했다.
- `output/data_cache/notices/2026000174.json`에 `manual_regulation.resale_restriction = "6개월"`을 추가했다.

추가 보강:

- 앞으로 `require_pdf=true`인 민간분양 생성에서 PDF 정책 추출과 `manual_regulation`이 모두 비면 생성이 실패한다.

## 공공분양/국민임대/토지임대부 처리

공공분양, 국민임대, 행복주택, 토지임대부 등 민간분양이 아닌 유형은 상세 포스트를 만들지 않는 것이 기본 방향이다.

- 프런트 카드에는 노출한다.
- 카드 클릭 시 자체 포스트로 이동하지 않는다.
- 청약Home 이동 확인 팝업을 띄운 뒤 사용자가 확인하면 청약Home 공고 페이지를 새 창으로 연다.
- 관련 판정 로직은 `pipeline/public_notices.py`의 `is_public_notice_data`, `is_public_notice_doc`을 기준으로 한다.

## 수동 복구 절차

라이브 포스트와 PDF 내용이 다르면 다음 순서로 처리한다.

1. 해당 공고번호의 파일을 확인한다.
   - `output/data_cache/notices/{notice_id}.json`
   - `input/pdfs/{notice_id}*.pdf`
   - `output/posts/{notice_id}/post_meta.json`
   - `output/posts/{notice_id}/post.html`

2. PDF 기준 값이 맞는지 확인한다.

3. 캐시에 사람이 확인한 값을 넣는다.

```json
"manual_regulation": {
  "resale_restriction": "6개월",
  "readmission_limit": "없음",
  "live_requirement": "없음",
  "price_cap": "미적용"
}
```

4. 필요하면 해당 공고만 재생성한다.

```bash
python generate_posts_from_cache.py --notice-id {notice_id} --include-processed --require-pdf --skip-ui-freeze-check
```

5. 산출물을 확인하고 커밋한다.

## 운영상 주의

- 서비스 계정 비공개 키, Firebase Admin SDK 키, `.env`는 절대 커밋하지 않는다.
- `google-services.json`은 Android 앱 클라이언트 설정 파일이고, 서버 비공개 키가 아니다.
- `input/pdfs/`의 공고문 PDF는 페이지 생성 근거 자료이므로 공고별로 추적 가능해야 한다.
- 워크플로우 수정 시 이 문서도 함께 갱신한다.

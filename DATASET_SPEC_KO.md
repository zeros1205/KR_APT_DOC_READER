# 데이터셋 및 UI 동결 명세

## UI 동결 원칙

현재 웹페이지 디자인과 레이아웃은 반드시 유지한다.

아래 파일은 사용자 승인 없이 수정하지 않는다:

- `templates/blog_template.html`
- `templates/front_index_template.html`
- `pipeline/html_renderer.py`
- `pipeline/index_renderer.py`
- `pipeline/shared_ui.py`
- `output/jung_reader_logo.png`

리팩토링은 데이터 수집, 캐시, 에이전트, 오케스트레이션 계층에서만 진행한다.

## 데이터 수집 정책

데이터 추출 에이전트는 포스트 생성 파이프라인과 독립적으로 실행한다.

실행 일정:

- 매주 월요일 00:00 KST
- GitHub Actions cron 기준: 일요일 15:00 UTC

역할:

- 공공데이터 API를 호출해 신규 공고 데이터를 수집한다.
- `notice_url`은 상세 페이지의 `모집공고문 보기` 링크로 보존한다.
- `notice_url` 내부에서 PDF 다운로드 링크를 찾지 않는다.
- PDF 파일을 다운로드하거나 파싱하지 않는다.
- 수집된 공고 데이터를 재사용 가능한 캐시로 저장한다.
- 필수 필드 누락 여부를 검사한다.
- 누락된 필드와 관련된 데이터 호출만 재시도한다.
- 재시도 후에도 실패한 필드는 수동 검토 대상으로 표시한다.

## 캐시 구조

파이프라인 내부 기준 데이터는 JSON을 원본으로 사용한다.

```text
output/data_cache/
  index.json
  notices/
    <notice_id>.json
  manual_review/
    missing_fields.csv
```

Stage별 LLM 결과는 별도로 저장해 테스트와 재생성 과정에서 외부 호출을 반복하지 않는다.

```text
output/stages/<notice_id>/
  stage2_eligibility.json
  stage3_regulation.json
  stage4_intro.json
  stage5_location.json
  stage6_faq.json
  stage7_evaluation.json
```

## 필수 필드

아래 필드가 있어야 포스트 생성 준비가 완료된 공고로 본다.

- `notice_id`
- `house_manage_no`
- `apt_name`
- `supply_address`
- `region_name`
- `supply_type`
- `total_units`
- `notice_date`
- `rank1_local_start` 또는 다른 1순위 접수일
- `winner_date`
- `notice_url`

주택형 데이터는 API에서 제공되는 경우 필수로 저장한다. 주택형 API가 빈 결과를 반환하면 공고는 캐시하되 누락 상태를 기록한다.

## 누락 필드 상태

각 공고 캐시에는 아래 상태값을 포함한다.

```json
{
  "missing_fields": ["notice_url"],
  "requires_manual_input": true,
  "manual_status": "pending"
}
```

`manual_status` 값:

- `none`: 수동 입력 필요 없음
- `pending`: 수동 확인 또는 입력 필요
- `completed`: 수동 입력 완료

## Grounding 보강 정책

공공데이터 API로 회수할 수 없는 누락 또는 취약 필드는 Gemini Grounding으로 보강한다.

Grounding 사용 대상:

- 청약자격
- 규제 정보
- 재당첨 제한
- 전매제한
- 거주의무
- 분양가상한제 여부
- 입지 분석
- Q&A 사실 검증

Grounding 결과는 쿼리 메타데이터와 함께 캐시한다.

```json
{
  "field": "price_cap",
  "query": "오티에르 반포 아파트 분양 분양가상한제 여부",
  "value": "적용",
  "source": "gemini_grounding",
  "confidence": "high",
  "checked_at": "2026-04-26T00:00:00+09:00"
}
```

근거가 충분하지 않은 경우 추측하지 않고 `확인 필요`로 저장한다.

## 포스트 생성 정책

포스트 생성 파이프라인은 완성된 캐시 데이터를 읽어 실행한다.

포스트 생성 단계에서는 공공데이터 API를 다시 호출하지 않는다.

렌더링 계약은 기존 구조를 유지한다.

- 기존 상세 페이지 템플릿 구조 유지
- 기존 프런트 페이지 템플릿 구조 유지
- `notice_url`은 기존 모집공고문 버튼에 연결
- 포스트 생성 후 `pipeline/build_index.py` 실행


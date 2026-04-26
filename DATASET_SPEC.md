# Dataset and UI Freeze Spec

## UI Freeze Rule

The current web page design and layout must be preserved.

Do not change these files unless the user explicitly approves the UI impact first:

- `templates/blog_template.html`
- `templates/front_index_template.html`
- `pipeline/html_renderer.py`
- `pipeline/index_renderer.py`
- `pipeline/shared_ui.py`
- `output/jung_reader_logo.png`

Refactoring should stay in the data collection, cache, agent, and orchestration layers.

## Data Collection Policy

The data extraction agent runs independently from page generation.

Schedule target:

- Every Monday 00:00 KST
- GitHub Actions cron equivalent: Sunday 15:00 UTC

Responsibilities:

- Call the public data API for new notices.
- Preserve `notice_url` as the external "모집공고문 보기" link.
- Do not crawl `notice_url` for PDF download links.
- Do not download or parse PDF files from the notice page.
- Store collected notice data in a reusable cache.
- Validate required fields.
- Retry only the data calls related to missing fields.
- Mark unresolved missing fields for manual review.

## Cache Layout

Pipeline-readable JSON is the source of truth.

```text
output/data_cache/
  index.json
  notices/
    <notice_id>.json
  manual_review/
    missing_fields.csv
```

Stage-level LLM results are stored separately so repeated tests do not repeat external calls.

```text
output/stages/<notice_id>/
  stage2_eligibility.json
  stage3_regulation.json
  stage4_intro.json
  stage5_location.json
  stage6_faq.json
  stage7_evaluation.json
```

## Required Fields

These fields must be present for a notice to be considered ready for post generation:

- `notice_id`
- `house_manage_no`
- `apt_name`
- `supply_address`
- `region_name`
- `supply_type`
- `total_units`
- `notice_date`
- `rank1_local_start` or another rank-1 date
- `winner_date`
- `notice_url`

Unit type data is required when available from the API. If the unit type endpoint returns no rows, the notice is still cached but the missing status is recorded.

## Missing Field Status

Each cached notice includes:

```json
{
  "missing_fields": ["notice_url"],
  "requires_manual_input": true,
  "manual_status": "pending"
}
```

Valid `manual_status` values:

- `none`
- `pending`
- `completed`

## Grounding Policy

Gemini with grounding is used for missing or weak fields that cannot be recovered from the public data API.

Grounding is allowed for:

- Eligibility requirements
- Regulation fields
- Readmission limit
- Resale restriction
- Live requirement
- Price cap status
- Location analysis
- FAQ factual checks

Grounding results must be cached with query metadata:

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

If the result is not well supported, store `확인 필요` instead of guessing.

## Post Generation Policy

Post generation reads the completed cache and should not call the public data API.

Generation output must keep the existing renderer contract:

- Existing post template structure is preserved.
- Existing front page template structure is preserved.
- `notice_url` remains connected to the existing notice button.
- `pipeline/build_index.py` is run after post generation.


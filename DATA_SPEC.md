# 📊 데이터 연관성 스펙

**작성일**: 2026-04-24  
**목적**: 공공데이터 API → LLM 처리 → 웹 렌더링 전체 흐름 명시

---

## 🔄 데이터 흐름도

```
공공데이터 API (청약홈)
    ↓
NoticeDocument (agents/collector.py)
    ↓
orchestrator.py (7-Agent 파이프라인)
    ↓
PostData (html_renderer.py)
    ↓
blog_template.html (렌더링)
    ↓
웹페이지 (apt-note.com/posts/...)
```

---

## 📑 섹션별 데이터 매핑

### **SECTION 1️⃣: 단지 소개**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 |
|-----------|-----------|-----------|---------|---------|
| **헤더 단지명** | `{{APT_NAME}}` | `apt_name` | API | `getAPTLttotPblancDetail.resultCode` → `HOUSE_NM` |
| **헤더 소제목** | `{{POST_SUBTITLE}}` | `post_subtitle` | LLM | orchestrator.py (Agent 4) |
| **인사 버블** | `{{APT_INTRO}}` | `apt_intro` | LLM | orchestrator.py (Agent 4) |
| **분양가 범위** | `{{PRICE_RANGE_TYPED}}` | `price_range` / `unit_types[]` | API | `getAPTLttotPblancMdl.SPSPLY_PRIC` (유닛별) |
| **총 공급** | `{{TOTAL_UNITS}}` | `unit_types[]` 합계 | API | `getAPTLttotPblancMdl` 행 개수 |
| **입주 예정** | `{{MOVE_IN_DATE}}` | `move_in_date` | API | `getAPTLttotPblancDetail.MVNIN_SCHDUL_MO` |
| **공급 위치** | `{{SUPPLY_LOCATION}}` | `supply_location` | API | `getAPTLttotPblancDetail.SPLY_ADRES` |
| **공급 규모** | `{{SUPPLY_SCALE}}` | `supply_scale` | 계산 | 유닛타입 수 + 세대 수 |
| **규제지역** | `{{REGULATED_ZONE}}` | `regulated_zone` | LLM + API | orchestrator.py (PDF 추출) |
| **재당첨제한** | `{{READMISSION_LIMIT}}` | `readmission_limit` | LLM + API | orchestrator.py (PDF 추출) |
| **전매제한** | `{{RESALE_RESTRICTION_BADGE}}` | `resale_restriction` | LLM + API | orchestrator.py (PDF 추출) |
| **거주의무기간** | `{{LIVE_REQUIREMENT}}` | `live_requirement` | LLM + API | orchestrator.py (PDF 추출) |
| **분양가상한제** | `{{PRICE_CAP}}` | `price_cap` | LLM + API | orchestrator.py (PDF 추출) |
| **택지유형** | `{{LAND_TYPE}}` | `land_type` | LLM + API | orchestrator.py (PDF 추출) |

---

### **SECTION 2️⃣: 입지 분석**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 |
|-----------|-----------|-----------|---------|---------|
| **입지 소개** | `{{LOCATION_INTRO}}` | `location_intro` | LLM | orchestrator.py (Agent 3) |
| **교통 카드 - 별점** | `{{SUBWAY_SCORE}}` | `subway_score` | LLM | orchestrator.py (Agent 4 Q&A 분석) |
| **교통 카드 - 상세** | `{{SUBWAY_DETAIL}}` | `subway_detail` | LLM | orchestrator.py (Agent 3, Agent 4 검증) |
| **학군 카드 - 별점** | `{{SCHOOL_SCORE}}` | `school_score` | LLM | orchestrator.py (Agent 4 Q&A 분석) |
| **학군 카드 - 상세** | `{{SCHOOL_DETAIL}}` | `school_detail` | LLM | orchestrator.py (Agent 3) |
| **생활편의 - 별점** | `{{LIFE_SCORE}}` | `life_score` | LLM | orchestrator.py (Agent 4 Q&A 분석) |
| **생활편의 - 상세** | `{{LIFE_DETAIL}}` | `life_detail` | LLM | orchestrator.py (Agent 3) |
| **의료 카드 - 별점** | `{{MEDICAL_SCORE}}` | `medical_score` | LLM | orchestrator.py (Agent 4 Q&A 분석) |
| **의료 카드 - 상세** | `{{MEDICAL_DETAIL}}` | `medical_detail` | LLM | orchestrator.py (Agent 3) |

---

### **SECTION 3️⃣: 분양 일정 & 공급 정보**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 |
|-----------|-----------|-----------|---------|---------|
| **일정 서술** | `{{SCHEDULE_DESC}}` | `schedule_desc` | LLM | orchestrator.py (Agent 4) |
| **특별공급 날짜** | `{{SPECIAL_SUPPLY_DATE}}` | `special_supply_date` | API | `getAPTLttotPblancDetail.SPCL_CNTRCT_RQEST_STRT_DE` |
| **1순위 청약** | `{{RANK1_DATE}}` | `rank1_date` | API | `getAPTLttotPblancDetail.GNRL_CNTRCT_RQEST_STRT_DE` |
| **2순위 청약** | `{{RANK2_DATE}}` | `rank2_date` | API | `getAPTLttotPblancDetail.SCND_CNTRCT_RQEST_STRT_DE` |
| **당첨자 발표** | `{{WINNER_DATE}}` | `winner_date` | 계산 | 2순위 날짜 + 1~3일 |
| **타입별 분양가 표** | `<!-- {{UNIT_TYPE_ROWS}} -->` | `unit_types[]` | API | `getAPTLttotPblancMdl` 전체 |
| **3.3㎡당 가격** | (테이블 내) | `UnitType.price_per_3_3` | 계산 | `(가격 / 면적) × 3.3` |

---

### **SECTION 4️⃣: 청약 신청자격**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 |
|-----------|-----------|-----------|---------|---------|
| **특별공급 카드** | `{{ELIGIBILITY_SECTION}}` | `eligibility_special[]` | LLM | orchestrator.py (Agent 1, Agent 2) |
| **1순위 자격** | (동일 섹션) | `eligibility_rank1[]` | LLM | orchestrator.py (Agent 1, Agent 2) |
| **2순위 자격** | (동일 섹션) | `eligibility_rank2[]` | LLM | orchestrator.py (Agent 1, Agent 2) |

---

### **SECTION 5️⃣: 자금 계획**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 |
|-----------|-----------|-----------|---------|---------|
| **자금 도입** | `{{FINANCIAL_INTRO}}` | `financial_intro` | LLM | orchestrator.py (Agent 2b) |
| **계약금 비율** | `{{CONTRACT_RATIO}}` | `contract_ratio` | API | `getAPTLttotPblancDetail` 또는 기본값 10 |
| **중도금 비율** | `{{MIDTERM_RATIO}}` | `midterm_ratio` | API | `getAPTLttotPblancDetail` 또는 기본값 60 |
| **잔금 비율** | `{{BALANCE_RATIO}}` | `balance_ratio` | 계산 | `100 - contract_ratio - midterm_ratio` |
| **중도금 회차** | `{{MIDTERM_COUNT}}` | `midterm_count` | API | `getAPTLttotPblancDetail` 또는 기본값 6 |
| **계약금 설명** | (이미지 하단) | `contract_desc` | LLM | orchestrator.py (Agent 2b) |
| **중도금 설명** | (이미지 하단) | `loan_info` | LLM | orchestrator.py (Agent 2b) |
| **잔금 설명** | (이미지 하단) | `balance_desc` | LLM | orchestrator.py (Agent 2b) |

---

### **SECTION 6️⃣: Q&A**

| 웹 출력 영역 | 템플릿 토큰 | PostData 필드 | 데이터 유형 | 데이터 소스 | 요구사항 |
|-----------|-----------|-----------|---------|---------|--------|
| **Q&A 도입** | `{{QA_INTRO}}` | `qa_intro` | LLM | orchestrator.py (Agent 4) | 60~80자 |
| **Q&A 블록 1~6** | `{{QA_BLOCKS}}` | `qa_blocks[]` | LLM | orchestrator.py (Agent 4, Agent 5) | 6개 필수 |
| (각 블록 구성) | - | `QABlock.question` | LLM | Agent 4 |  |
| (각 블록 답변) | - | `QABlock.answer` | LLM | Agent 5 (팩트체크) |  |

---

## 📋 LLM 생성 데이터 요구사항

### **문자 수 제약**

| 필드 | 요구사항 | 현재 | 상태 |
|------|--------|------|------|
| `apt_intro` | 150~200자 | ❌ | 미검증 |
| `location_intro` | 100~150자 | ❌ | 미검증 |
| `financial_intro` | 80~100자 | ❌ | 미검증 |
| `qa_intro` | 60~80자 | ❌ | 미검증 |
| `schedule_desc` | 80~120자 | ❌ | 미검증 |
| `tax_desc` | 80~120자 | ❌ | 미검증 |
| `unit_type_desc` | 80~120자 | ❌ | 미검증 |
| `subway_detail` | 80~150자 | ❌ | 미검증 |
| `school_detail` | 80~150자 | ❌ | 미검증 |
| `life_detail` | 80~150자 | ❌ | 미검증 |
| `medical_detail` | 80~150자 | ❌ | 미검증 |

### **개수 제약**

| 필드 | 요구사항 | 현재 | 상태 |
|------|--------|------|------|
| `qa_blocks[]` | 정확히 6개 | ❌ | 동적 생성 |
| `seo_tags[]` | 5개 이상 | ❌ | 동적 생성 |
| `unit_types[]` | 1개 이상 | ✅ | API 검증 |
| `eligibility_special[]` | 0개 이상 | ⚠️ | 조건부 |
| `eligibility_rank1[]` | 0개 이상 | ⚠️ | 조건부 |
| `eligibility_rank2[]` | 0개 이상 | ⚠️ | 조건부 |

---

## 🔌 API 데이터 필드 매핑

### **공공데이터 API → NoticeDocument**

```python
# agents/collector.py - CheongYakAPI.get_detail()
{
    "HOUSE_NM": apt_name,                           # 단지명
    "SPLY_ADRES": supply_location,                  # 공급 위치
    "MVNIN_SCHDUL_MO": move_in_date,               # 입주예정
    "SPCL_CNTRCT_RQEST_STRT_DE": special_date,     # 특별공급
    "GNRL_CNTRCT_RQEST_STRT_DE": rank1_date,       # 1순위
    "SCND_CNTRCT_RQEST_STRT_DE": rank2_date,       # 2순위
    "NOTICE_URL": notice_url,                       # 공고문 링크
}

# agents/collector.py - CheongYakAPI.get_unit_types()
[
    {
        "HOUSE_TYPE": type_name,                    # 타입명
        "AREA": area_sqm,                           # 전용면적
        "SPLY_CNT": general_units,                  # 일반공급 세대
        "SPCL_SPLY_CNT": special_units,             # 특별공급 세대
        "MIN_PRIC": price_min,                      # 최저가
        "MAX_PRIC": price_max,                      # 최고가
    }
]
```

---

## ⚙️ LLM 처리 (orchestrator.py)

### **Agent 1: 팩트 추출**
```
입력: NoticeDocument (공고문 원문)
출력: 청약자격 기본 사항 (eligibility_special, rank1, rank2)
모델: Anthropic Claude Haiku
```

### **Agent 2: 청약자격 팩트체크**
```
입력: Agent 1 결과 + Google Grounding
출력: 검증된 청약자격 정보
모델: Google Gemini 3.1 Pro + Grounding
```

### **Agent 2b: 자금계획 세부**
```
입력: NoticeDocument + unit_types + 납부비율
출력: contract_desc, midterm_desc 등
모델: Google Gemini 3.1 Pro + Grounding
```

### **Agent 3: 입지 분석**
```
입력: supply_location + Google Grounding
출력: subway_detail, school_detail, life_detail, medical_detail
모델: Google Gemini 3.1 Pro
```

### **Agent 4: 콘텐츠 생성**
```
입력: 모든 기본 정보 + 입지 분석 결과
출력: apt_intro, location_intro, financial_intro, qa_intro, 
      unit_type_desc, schedule_desc, tax_desc, qa_blocks[] (6개)
모델: Google Gemini 3.1 Pro
```

### **Agent 5: Q&A 팩트체크**
```
입력: qa_blocks[] + Google Grounding
출력: 검증된 Q&A 답변 수정
모델: Google Gemini 3.1 Pro
```

---

## 🎯 다음 작업

1. **데이터 검증 로직 추가**
   - PostData 클래스에 `@validator` 데코레이터 추가
   - 문자 수 범위 검증
   - 필수 필드 검증

2. **품질 검사 강화**
   - orchestrator.py의 `compute_quality_score()` 확장
   - 문자 수 제약 반영
   - 개수 제약 반영

3. **LLM 프롬프트 개선**
   - 각 Agent의 프롬프트에 제약사항 명시
   - 예: `200자 이내의 마케팅 자연스러운 문체로 작성`


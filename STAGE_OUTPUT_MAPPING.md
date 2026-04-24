# 에이전트 산출물 → 데이터베이스 필드 매핑

## 블로그 포스팅 구조 (최종 HTML)

```
【헤더】
1. 제목 (post_title)
2. 부제 (post_subtitle)

【본문 섹션】
Section 1: 단지 소개
  - 인사말 (apt_intro)
  - 핵심 요약 테이블 (unit_types, total_units, location, supply_scale, price_range)
  - 조감도 이미지 (placeholder)

Section 2: 분양가 정보
  - 타입별 분양가 테이블 (unit_type_desc)
  - 평면도 (placeholder)

Section 3: 입지 분석
  - 총평 (location_intro)
  - 4개 별점 카드
    • 교통 (subway_score + subway_detail)
    • 교육 (school_score + school_detail)
    • 생활 (life_score + life_detail)
    • 의료 (medical_score + medical_detail)

Section 4: 자금 계획
  - 도입부 (financial_intro)
  - 납부 타임라인 (contract_ratio, midterm_ratio, balance_ratio)
  - 대출 정보 (loan_info)

Section 5: 세금 정보
  - 세금 설명 (tax_desc)
  - 취득세율 (acquisition_tax_rate)

Section 6: 청약 일정
  - 청약 일정 (schedule_desc)
  - 주요 날짜 (special_supply_date, rank1_date, rank2_date, winner_date, move_in_date)

Section 7: 청약 자격
  - 특별공급 (eligibility_special)
  - 1순위 (eligibility_rank1)
  - 2순위 (eligibility_rank2)
  - 규제 정보 (regulated_zone, readmission_limit, live_requirement, price_cap, resale_restriction)

Section 8: Q&A
  - 도입부 (qa_intro)
  - Q&A 블록 (qa_blocks)

【푸터】
9. SEO 태그 (seo_tags)
```

---

## Stage별 산출물 → 데이터베이스 필드 매핑

### 🔵 Stage 1: 데이터 추출 에이전트
**담당**: 공공데이터 API에서 원시 데이터 수집
**저장 위치**: `Apartment` 테이블

```
Apartment 테이블
├─ api_notice_id        ← Stage 1: 공고번호 (API)
├─ apt_name             ← Stage 1: 단지명 (API) [누락 시 ⚠️ 관리자 입력]
├─ supply_address       ← Stage 1: 공급 주소 (API) [누락 시 ⚠️ 관리자 입력]
├─ location             ← Stage 1: "지역/구간" 파싱 (API) [누락 시 ⚠️ 관리자 입력]
├─ supply_scale         ← Stage 1: 공급규모 (API) "30~70평"
├─ total_units          ← Stage 1: 공급세대수 (API)
├─ land_type            ← Stage 1: 토지의 유형 (API)
├─ constructor          ← Stage 1: 건설사 (API)
├─ notice_url           ← Stage 1: 공고 링크 (API)
└─ created_at           ← 자동

⚠️ 규제정보 필드들 (is_hot_zone, regulated_zone, readmission_limit, live_requirement, price_cap)
  → Stage 3에서 채워짐 (Apartment 테이블 업데이트)
```

**산출 형식**:
```python
apartment_data = {
    "api_notice_id": "2024-xxx",
    "apt_name": "분당 신도시 래미안",
    "supply_address": "경기도 성남시 분당구 ...",
    "location": "경기도 / 성남시",
    "supply_scale": "30~84평",
    "total_units": 590,
    "land_type": "도시개발사업",
    "constructor": "현대건설",
    "notice_url": "https://...",
    "missing_fields": ["price_range", "unit_types"],  # ⚠️ 알림
}
```

---

### 🟢 Stage 2: 청약자격 확인 에이전트
**담당**: 정부 정책 기반 청약자격 요건 정리
**저장 위치**: `PostingContent` 테이블 + `PostingMeta` 테이블

```
PostingContent 테이블
├─ eligibility_special  ← Stage 2: 특별공급 자격 요건 JSON배열
│  예: ["신혼부부 (혼인기간 7년이내)", "생애최초 구매자", "다자녀가정"]
├─ eligibility_rank1    ← Stage 2: 1순위 자격 요건 JSON배열
│  예: ["청약통장 24개월 이상 가입", "최근 2년간 월평균소득 이하", "무주택 세대주"]
└─ eligibility_rank2    ← Stage 2: 2순위 자격 요건 JSON배열
   예: ["1순위 탈락자", "주택소유자", "부양가족 포함"]

PostingMeta 테이블
├─ special_supply_date  ← Stage 2: 특별공급 접수 예정일 (일정정보에서 추출)
├─ rank1_date           ← Stage 2: 1순위 접수 예정일
└─ rank2_date           ← Stage 2: 2순위 접수 예정일
```

**산출 형식**:
```python
eligibility_data = {
    "eligibility_special": [
        "신혼부부 (혼인기간 7년 이내, 합산소득 기준 이하)",
        "생애최초 주택 구매자",
        "다자녀가정 (3명 이상)"
    ],
    "eligibility_rank1": [
        "청약예금 가입 24개월 이상 (월 50만원 이상 납입)",
        "최근 2년간 월평균소득 이하",
        "무주택 세대주 또는 1주택 소유자"
    ],
    "eligibility_rank2": [
        "세대주로 2주택 이상 소유 중",
        "청약 자격 완전 상실 대상자 제외",
        "신청 시점에 무주택 세대주"
    ],
    "special_supply_date": "2024-05-15",  # ← PostingMeta
    "rank1_date": "2024-05-20",           # ← PostingMeta
    "rank2_date": "2024-05-25",           # ← PostingMeta
}
```

---

### 🟡 Stage 3: 청약 규제 정보 에이전트
**담당**: 규제지역 및 제한 정보 정리
**저장 위치**: `Apartment` 테이블 + `PostingMeta` 테이블

```
Apartment 테이블 (업데이트)
├─ is_hot_zone          ← Stage 3: "Y" / "N" / "해당없음"
│  (투기과열지구 여부)
├─ regulated_zone       ← Stage 3: "청약과열지구" / "조정대상지역" / "해당없음"
├─ readmission_limit    ← Stage 3: "4년" / "-" (재당첨 제한기간)
├─ live_requirement     ← Stage 3: "2년" / "-" (거주의무기간)
└─ price_cap            ← Stage 3: "상한제 적용" / "미적용"

PostingMeta 테이블 (추가)
├─ resale_restriction   ← Stage 3: "3년" / "-" (전매제한)
└─ acquisition_tax_rate ← Stage 3: "1%" / "2%" (취득세율)
```

**산출 형식**:
```python
regulation_data = {
    "is_hot_zone": "N",                      # Apartment
    "regulated_zone": "조정대상지역",
    "readmission_limit": "4년",              # Apartment
    "live_requirement": "2년",
    "price_cap": "상한제 미적용",
    "resale_restriction": "3년",              # PostingMeta
    "acquisition_tax_rate": "1%",            # PostingMeta
}
```

---

### 🔴 Stage 4: 단지 소개 에이전트
**담당**: 아파트 단지의 팩트 기반 소개글 작성
**저장 위치**: `PostingContent` 테이블 + `Posting` 테이블

```
PostingContent 테이블
└─ apt_intro            ← Stage 4: 단지 소개글 (150~200자)
   "분당 신도시의 프리미엄 아파트. 현대건설이 개발하는 
    이 프로젝트는 590세대 규모로 30~84평 다양한 타입을 갖추었습니다.
    강남역 인근 최고의 입지에 위치하고 있습니다."

PostingContent 테이블 (추가)
├─ unit_type_desc      ← Stage 4: 타입별 분양가 설명
│  예: "30평: 4.5억~5억\n40평: 5.5억~6억\n70평: 7억~8억"
└─ schedule_desc        ← Stage 4: 청약 일정 설명
   예: "특별공급 5/15, 1순위 5/20-22, 2순위 5/25-27"

Posting 테이블
└─ post_title          ← Stage 4: 포스팅 제목
   "분당 신도시 래미안 프리미엄 분양 분석"
```

**산출 형식**:
```python
intro_data = {
    "apt_intro": "분당 신도시의 프리미엄 아파트. 현대건설이 개발하는 ...",
    "post_title": "분당 신도시 래미안 프리미엄 분양 분석",
    "unit_type_desc": "30평: 4.5억~5억\n40평: 5.5억~6억\n70평: 7억~8억",
    "schedule_desc": "특별공급 5/15, 1순위 5/20-22, 2순위 5/25-27",
}
```

---

### 🟣 Stage 5: 입지 분석 에이전트
**담당**: 아파트 위치의 지역 특성 및 장점 분석
**저장 위치**: `PostingContent` 테이블

```
PostingContent 테이블
├─ location_intro       ← Stage 5: 지역 총평 (200~500자)
│  "강남역에서 도보 5분 거리의 최고 접근성. 
│   서초초등학교, 강남중학교 등 명문 학군이 밀집해 있으며..."
│
├─ subway_score         ← Stage 5: 교통 별점 (★★★★★ 형식)
├─ subway_detail        ← Stage 5: 교통 상세 (개조식, 300~2000자)
│  "• 강남역 도보 5분
│   - 지하철 2호선 환승 가능
│   - 신분당선, 동대구선 연계 등..."
│
├─ school_score         ← Stage 5: 교육 별점
├─ school_detail        ← Stage 5: 교육 상세 (개조식, 300~2000자)
│  "• 서초초등학교: 명문 초등학교
│   - 학생 1인당 교사 비율 우수
│   - 입시 실적 상위권..."
│
├─ life_score           ← Stage 5: 생활 별점
├─ life_detail          ← Stage 5: 생활 상세 (개조식, 300~2000자)
│  "• 강남 상권: 국내 최대 커머셜 지역
│   - 식당, 카페, 쇼핑 시설 밀집..."
│
├─ medical_score        ← Stage 5: 의료 별점
└─ medical_detail       ← Stage 5: 의료 상세 (개조식, 300~2000자)
   "• 강남세브란스 병원: 도보 10분
    - 대학병원 수준의 의료진
    - 응급실 24시간 운영..."
```

**산출 형식**:
```python
location_data = {
    "location_intro": "강남역에서 도보 5분 거리의 최고 접근성...",
    "subway_score": "★★★★★",
    "subway_detail": "• 강남역 도보 5분\n  - 지하철 2호선 환승...",
    "school_score": "★★★★☆",
    "school_detail": "• 서초초등학교...",
    "life_score": "★★★★★",
    "life_detail": "• 강남 상권...",
    "medical_score": "★★★★☆",
    "medical_detail": "• 강남세브란스 병원...",
}
```

---

### 🟠 Stage 6: Q&A 작성 에이전트
**담당**: 청약 제도 + 단지 관련 FAQ 작성
**저장 위치**: `PostingContent` 테이블 + `PostingMeta` 테이블

```
PostingContent 테이블
├─ qa_intro             ← Stage 6: Q&A 도입부 (60~80자)
│  "청약 신청 전 꼭 알아야 할 것들을 Q&A로 정리했습니다."
│
├─ qa_blocks            ← Stage 6: Q&A 배열 (3~7개)
│  [
│    {"q": "이 아파트 청약에 신청하려면 어떤 자격이 필요한가요?",
│     "a": "【특별공급】신혼부부, 생애최초...\n【1순위】청약통장..."},
│    {"q": "투기과열지구라면 어떤 제한이 있나요?",
│     "a": "재당첨이 4년 제한됩니다..."},
│    {...}
│  ]
│
├─ financial_intro      ← Stage 6: 자금계획 도입부 (80~100자)
│  "효율적인 자금 계획이 성공의 첫 단계입니다."
│
└─ tax_desc             ← Stage 6: 세금 정보 설명 (300~1000자)
   "취득세, 재산세, 종부세 등 주의할 점들..."

PostingMeta 테이블 (추가)
├─ contract_ratio       ← Stage 6: 계약금 비율 (예: "10%")
├─ contract_amount      ← Stage 6: 계약금액 설명
├─ midterm_ratio        ← Stage 6: 기성금 비율 (예: "60%")
├─ midterm_count        ← Stage 6: 기성금 회차 (예: "6회")
├─ balance_ratio        ← Stage 6: 잔금 비율 (예: "30%")
└─ loan_info            ← Stage 6: 대출 정보
   "주택담보대출 최대 80% 가능
    금리: 연 3.5~4.5% (은행별 상이)"
```

**산출 형식**:
```python
qa_data = {
    "qa_intro": "청약 신청 전 꼭 알아야 할 것들...",
    "qa_blocks": [
        {
            "q": "이 아파트 청약에 신청하려면 어떤 자격이 필요한가요?",
            "a": "【특별공급】신혼부부, 생애최초...\n【1순위】청약통장 24개월..."
        },
        {
            "q": "1순위 해당지역 주민이 아니면 신청할 수 없나요?",
            "a": "아닙니다. 전국에서 신청 가능합니다..."
        },
        # ... 3~7개 Q&A
    ],
    "financial_intro": "효율적인 자금 계획이 성공의 첫 단계입니다.",
    "tax_desc": "취득세, 재산세, 종부세 등...",
    "contract_ratio": "10%",       # PostingMeta
    "contract_amount": "4억 (30평 기준)",
    "midterm_ratio": "60%",
    "midterm_count": "6회",
    "balance_ratio": "30%",
    "loan_info": "주택담보대출 최대 80% 가능..."  # PostingMeta
}
```

---

### 🔵 Stage 7: 스크립트 평가 에이전트
**담당**: 위 Stage 2~6 결과 평가 및 보완
**저장 위치**: `Posting.quality_score` (최종 품질 점수)

```
Posting 테이블
└─ quality_score       ← Stage 7: 최종 품질 점수 (0~100점)
   - 평가 기준:
     • Stage 2 정책 정확성 + 완성도
     • Stage 3 규제정보 정확성 + 완성도
     • Stage 4 단지소개 길이 + 톤 + 정보성
     • Stage 5 입지분석 정확성 + 형식 + 설득력
     • Stage 6 Q&A 다양성 + 정확성 + 형식
```

**평가 로직**:
```
if 모든 Stage 점수 >= threshold:
    ├─ quality_score = (avg_score)
    └─ ✅ 통과 → HTML 렌더링 진행
else:
    ├─ 부족 항목 명시
    ├─ 보완 지시사항 생성
    └─ 해당 Stage 재실행 요청
```

---

## 최종 데이터 흐름

```
Stage 1 출력
    ↓
【Apartment 테이블 저장】
  ├─ api_notice_id, apt_name, location, total_units 등
  └─ is_hot_zone, regulated_zone 등 규제필드 (Stage 3에서 업데이트)

Stage 2 출력
    ↓
【PostingContent + PostingMeta 부분 저장】
  ├─ eligibility_special/rank1/rank2
  └─ special_supply_date, rank1_date, rank2_date

Stage 3 출력
    ↓
【Apartment + PostingMeta 부분 업데이트】
  ├─ is_hot_zone, regulated_zone, readmission_limit (Apartment)
  └─ resale_restriction, acquisition_tax_rate (PostingMeta)

Stage 4 출력
    ↓
【PostingContent + Posting 부분 저장】
  ├─ apt_intro, unit_type_desc, schedule_desc (PostingContent)
  └─ post_title (Posting)

Stage 5 출력
    ↓
【PostingContent 부분 저장】
  └─ location_intro, subway_score/detail, school_score/detail,
     life_score/detail, medical_score/detail

Stage 6 출력
    ↓
【PostingContent + PostingMeta 부분 저장】
  ├─ qa_intro, qa_blocks, financial_intro, tax_desc (PostingContent)
  └─ contract_ratio, midterm_ratio, balance_ratio, loan_info (PostingMeta)

Stage 7 평가
    ↓
【Posting.quality_score 저장】
  └─ 0~100 점수

최종
    ↓
【HTML 렌더링】
  └─ PostingContent + PostingMeta 필드들을 HTML 템플릿에 삽입
```

---

## 누락된 필드 확인

**Stage 1에서 누락 가능**: `apt_name`, `supply_address`, `location`, `price_range`, `unit_types`
- → DB에 `NULL` 또는 `"[데이터 없음]"` 표시
- → 관리자 대시보드에서 수동 입력

**각 Stage별 필수 산출물**:
| Stage | 필수 산출물 | 누락 시 처리 |
|-------|-----------|----------|
| 2 | eligibility_special/rank1/rank2 | 기본값 [] |
| 3 | is_hot_zone, regulated_zone | 기본값 "해당없음", "-" |
| 4 | apt_intro, post_title | 기본값 apt_name 사용 |
| 5 | location_intro, subway_detail | 기본값 "-" |
| 6 | qa_blocks (3~7개) | 경고 후 재실행 |

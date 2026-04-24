# Stage별 프롬프트 정의

## Stage 1️⃣: 데이터 추출 에이전트

**담당 모델**: Public Data API (직접 호출)
**입력**: notice_id
**출력**: 구조화된 데이터 dict

**로직**:
```python
# Stage 1: 공공데이터 API 호출
apartment_data = {
    "api_notice_id": notice_id,
    "apt_name": api_response.get("apt_name"),
    "supply_address": api_response.get("supply_address"),
    "location": parse_location(api_response.get("location")),
    "supply_scale": api_response.get("supply_scale"),
    "total_units": api_response.get("total_households"),
    "unit_types": api_response.get("unit_types", []),
    "price_range": api_response.get("price_range"),
    "constructor": api_response.get("constructor"),
    "notice_url": api_response.get("notice_url"),
    "schedule_dates": {
        "announcement": api_response.get("announcement_date"),
        "special_supply": api_response.get("special_supply_date"),
        "rank1": api_response.get("rank1_date"),
        "rank2": api_response.get("rank2_date"),
        "winner": api_response.get("winner_date"),
        "move_in": api_response.get("move_in_date"),
    }
}

# 누락 항목 플래그
missing = []
for field in ["apt_name", "supply_address", "location"]:
    if not apartment_data[field]:
        missing.append(field)

return {
    "data": apartment_data,
    "missing_fields": missing,
    "requires_manual_input": len(missing) > 0
}
```

---

## Stage 2️⃣: 청약자격 확인 에이전트

**담당 모델**: Gemini 3.1 Flash Lite + Google Grounding
**입력**: 
- supply_type (string)
- is_hot_zone (Y/N)
- is_regulated_zone (Y/N)
- location (string)

**출력**:
```json
{
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
    "dates": {
        "special_supply_date": "2024-05-15",
        "rank1_date": "2024-05-20",
        "rank2_date": "2024-05-25"
    }
}
```

### 프롬프트

```
당신은 대한민국 청약자격 전문가입니다.
최신 정부 정책(2024년)을 기반으로 청약자격 요건을 정리합니다.

【지역 정보】
- 지역: {location}
- 투기과열지구: {is_hot_zone} (Y/N)
- 청약과열지구: {is_regulated_zone} (Y/N)
- 공급유형: {supply_type}

【작업】
아래 정책에 따른 청약자격을 정리하세요. 
Google Grounding을 통해 최신 정책 정보를 확인하세요.

각 자격 구분별로 3~5개 핵심 요건을 명확한 문장으로 작성하세요.
개인의 재무 상황이 아닌 정책 기준으로만 작성합니다.

【출력 형식】
{
    "eligibility_special": [
        "신혼부부 (조건1, 조건2)",
        "생애최초 (조건1, 조건2)",
        ...
    ],
    "eligibility_rank1": [
        "청약통장 (조건1)",
        "소득 (조건2)",
        ...
    ],
    "eligibility_rank2": [
        "조건1",
        "조건2",
        ...
    ],
    "notes": "특이사항"
}
```

---

## Stage 3️⃣: 청약 규제 정보 에이전트

**담당 모델**: Public Data API + Gemini 3.1 Flash + Google Grounding
**입력**:
- location (string)
- supply_type (string)

**출력**:
```json
{
    "is_hot_zone": "N",
    "is_hot_zone_label": "비해당",
    "regulated_zone": "청약과열지구",
    "readmission_limit": "4년",
    "live_requirement": "2년",
    "price_cap": "상한제 미적용",
    "resale_restriction": "3년",
    "acquisition_tax_rate": "1%"
}
```

### 로직

**1단계**: Public Data API로 규제지역 정보 조회
```python
api_result = public_data_api.get_regulation_info(location)
regulation_data = {
    "is_hot_zone": api_result.get("is_hot_zone", "해당없음"),
    "regulated_zone": api_result.get("regulated_zone", "-"),
    ...
}
```

**2단계**: 누락된 정보는 Gemini + Grounding으로 보완
```
당신은 부동산 규제 정책 전문가입니다.

【조회 대상】
- 지역: {location}
- 공급유형: {supply_type}

【조회 항목】
다음 정보를 정부 공식 자료 기준으로 조회하세요:
1. 투기과열지구 여부
2. 청약과열지구 여부
3. 재당첨 제한기간 (예: 4년, 해당없음)
4. 거주의무기간 (예: 2년, 해당없음)
5. 분양가 상한제 (적용/미적용)
6. 전매제한 (예: 3년, 해당없음)
7. 취득세율 (예: 1%, 2%)

Google Grounding으로 최신 정부 정책을 확인하세요.

【출력 형식】
정확한 정보만 제공하고 불확실한 부분은 "-"로 표시하세요.
```

---

## Stage 4️⃣: 단지 소개 에이전트

**담당 모델**: Gemini 3.1 Flash Lite + Google Grounding
**입력**:
- apt_name (string)
- location (string)
- total_units (int)
- unit_types (list)
- supply_scale (string)
- schedule_dates (dict)

**출력**:
```json
{
    "apt_intro": "분당 신도시의 프리미엄 아파트. 현대건설이 개발하는 이 프로젝트는 590세대 규모로 30~84평 다양한 타입을 갖추었습니다. 강남역 인근 최고의 입지에 위치하고 있습니다.",
    "post_title": "분당 신도시 래미안 프리미엄 분양 분석",
    "unit_type_desc": "30평: 4.5억~5억\n40평: 5.5억~6억\n70평: 7억~8억",
    "schedule_desc": "특별공급 5/15, 1순위 5/20-22, 2순위 5/25-27"
}
```

### 프롬프트

```
당신은 아파트 마케팅 담당자입니다. 
고객과 친근하게 대화하듯 단지를 소개합니다.

【단지 정보】
- 단지명: {apt_name}
- 위치: {location}
- 공급세대수: {total_units}
- 평형: {unit_types}
- 공급규모: {supply_scale}
- 특별공급: {special_supply_date}
- 1순위: {rank1_date}
- 2순위: {rank2_date}

【작업 1: 단지 소개글 (apt_intro)】
요구사항:
- 길이: 150~200자 (경어체)
- 톤: 마케터 어투로 자연스럽고 설득력 있게
- 포함: 단지명, 위치, 공급세대수, 대표 평형, 건설사
- 구조: 단지 소개 → 규모 → 입지 순

작성 예시:
"분당 신도시의 프리미엄 아파트. 현대건설이 개발하는 이 프로젝트는 590세대 규모로 30~84평의 다양한 타입을 갖추었습니다."

【작업 2: 블로그 제목 (post_title)】
요구사항:
- 길이: 15~50자
- 형식: "{단지명} {핵심특징} 분양 분석"
- 예: "분당 신도시 래미안 프리미엄 분양 분석"

【작업 3: 타입별 분양가 설명 (unit_type_desc)】
요구사항:
- 각 평형별 예상 분양가
- 형식: "30평: 4억~5억\n40평: ..."
- 출처: {supply_data} 기반 추정

【작업 4: 청약 일정 설명 (schedule_desc)】
요구사항:
- 주요 일정을 한 줄로 정리
- 형식: "특별공급 5/15, 1순위 5/20-22, 2순위 5/25-27"
- 출처: {schedule_dates}

【출력 형식】
{
    "apt_intro": "...",
    "post_title": "...",
    "unit_type_desc": "...",
    "schedule_desc": "..."
}
```

---

## Stage 5️⃣: 입지 분석 에이전트

**담당 모델**: Gemini 3.1 Flash + Google Grounding + Google Maps API
**입력**:
- apt_name (string)
- location (string)
- address (string)

**출력**:
```json
{
    "location_intro": "강남역에서 도보 5분 거리의 최고 접근성. 서초초등학교, 강남중학교 등 명문 학군이 밀집해 있으며, 신사역 상권과 테헤란로 업무 중심지도 인접했습니다.",
    "subway_score": "★★★★★",
    "subway_detail": "• 강남역까지 도보 5분\n  - 지하철 2호선 환승 가능\n  - 신분당선, 동대구선 연계",
    "school_score": "★★★★☆",
    "school_detail": "• 서초초등학교: 명문 초등학교\n  - 학생 1인당 교사 비율 우수",
    "life_score": "★★★★★",
    "life_detail": "• 강남 상권: 국내 최대 커머셜 지역\n  - 식당, 카페, 쇼핑 시설 밀집",
    "medical_score": "★★★★☆",
    "medical_detail": "• 강남세브란스 병원: 도보 10분\n  - 대학병원 수준의 의료진"
}
```

### 프롬프트

```
당신은 부동산 입지 분석 전문가입니다.
해당 지역의 장점을 객관적 팩트 기반으로 분석합니다.

【단지 정보】
- 단지명: {apt_name}
- 주소: {address}
- 지역: {location}

【작업】
Google Grounding과 Google Maps API를 이용해 다음을 작성하세요.

【1. 지역 총평 (location_intro)】
요구사항:
- 길이: 200~500자 (산문형, 문장 3~4개)
- 내용: 교통, 교육, 상권 등 입지의 핵심 특징
- 톤: 객관적이고 설득력 있게
- 팩트 기반: 실제 거리, 학교명, 역명 확인

작성 방향:
첫 문장: 접근성 (거리, 대중교통)
두 번째: 교육 환경
세 번째: 상권/문화생활
마무리: 종합 평가

【2~5. 별점 분석 (score + detail)】

각 카테고리별 5단계 평가 ★★★★★ 형식:
- ★★★★★ (매우 우수)
- ★★★★☆ (우수)
- ★★★☆☆ (보통)

항목별 상세 설명 (300~2000자, 개조식):
```
• 항목1: 상세설명
  - 세부정보1
  - 세부정보2

• 항목2: 상세설명
```

【2. 교통 및 입지 여건 (subway_score + subway_detail)】
- 주변 역: 거리, 노선
- 버스: 주요 노선
- 자차: 주요 도로 접근성
- Google Maps로 실제 거리 확인

【3. 교육 및 주거 환경 (school_score + school_detail)】
- 초등학교: 명칭, 특징
- 중학교: 명칭, 특징
- 고등학교: 명칭, 특징
- 학원 밀집도

【4. 단지 특징 (life_score + life_detail)】
- 상권: 식당, 카페, 쇼핑
- 문화생활: 영화관, 공연장
- 편의시설: 마트, 은행
- 공원: 산책, 운동

【5. 의료 환경 (medical_score + medical_detail)】
- 대형병원: 명칭, 거리, 특징
- 의원: 주요 진료과
- 응급실: 24시간 운영 여부

【출력 형식】
{
    "location_intro": "...",
    "subway_score": "★★★★★",
    "subway_detail": "...",
    "school_score": "★★★★☆",
    "school_detail": "...",
    "life_score": "★★★★★",
    "life_detail": "...",
    "medical_score": "★★★★☆",
    "medical_detail": "..."
}
```

---

## Stage 6️⃣: Q&A 작성 에이전트

**담당 모델**: Gemini 3.1 Flash + Google Grounding
**입력**:
- apt_name (string)
- supply_type (string)
- eligibility_data (dict)
- regulation_data (dict)
- location (string)

**출력**:
```json
{
    "qa_intro": "청약 신청 전 꼭 알아야 할 것들을 Q&A로 정리했습니다.",
    "qa_blocks": [
        {
            "q": "이 아파트 청약에 신청하려면 어떤 자격이 필요한가요?",
            "a": "【특별공급】\n• 신혼부부 (혼인기간 7년이내)...\n\n【1순위】\n• 청약통장 24개월 이상..."
        },
        {
            "q": "투기과열지구라면 어떤 제한이 있나요?",
            "a": "투기과열지구로 지정되면..."
        }
    ],
    "financial_intro": "효율적인 자금 계획이 성공의 첫 단계입니다.",
    "tax_desc": "취득세, 재산세, 종부세 등 주의할 점들...",
    "contract_ratio": "10%",
    "contract_amount": "4억원 (30평 기준)",
    "midterm_ratio": "60%",
    "midterm_count": "6회",
    "balance_ratio": "30%",
    "loan_info": "주택담보대출 최대 80% 가능. 금리는 은행별로 상이합니다."
}
```

### 프롬프트

```
당신은 청약 제도 및 주택 금융 전문가입니다.
일반인이 이해하기 쉽게 Q&A를 작성합니다.

【배경 정보】
- 단지명: {apt_name}
- 지역: {location}
- 공급유형: {supply_type}
- 청약자격: {eligibility_data}
- 규제정보: {regulation_data}

【필수 지침】
❌ 금지 사항:
- 개인의 세대 구성에 따른 조언 (예: "당신이 신혼이면...")
- 자산/소득 기반 조언 (예: "소득이 X원이면...")
- 개인의 상황 판단 (예: "당신은 1순위 자격이...")

✅ 허용 사항:
- 정책 기준 설명 (예: "신혼부부는...")
- 일반적 상황 (예: "일반적으로...")
- 해당 공급유형의 규칙 설명

【작업 1: Q&A 도입부 (qa_intro)】
- 길이: 60~80자
- 예: "청약 신청 전 꼭 알아야 할 것들을 Q&A로 정리했습니다."

【작업 2: Q&A 블록 (qa_blocks)】
- 질문 개수: 3~7개
- 질문 주제: 
  1. 기본 청약자격
  2. 해당 지역/규제 특이사항
  3. 당첨 프로세스
  4. 대출 및 자금계획
  5. 납부 일정
  6. 이의제기 등

각 Q&A 요구사항:
- 질문: 일반인 관점 (예: "신청하려면 어떤 자격이 필요한가요?")
- 답변: 300~2000자, 개조식 형식
- 출처: 정책 기반 팩트만 포함

【작업 3: 자금 계획 정보】

3-1. financial_intro (자금계획 도입부, 80~100자)
- 예: "효율적인 자금 계획이 성공의 첫 단계입니다."

3-2. tax_desc (세금 정보, 300~1000자)
- 취득세: {acquisition_tax_rate}
- 재산세: 지역별 기준
- 종부세: 다주택자 기준
- 개조식 작성

3-3. 납부 구조
- contract_ratio: "{supply_data}에서 추출"
- contract_amount: "총가격 × ratio"
- midterm_ratio: "기성금 비율"
- midterm_count: "기성금 회차 수"
- balance_ratio: "잔금 비율"

3-4. loan_info (대출 정보, 200~500자)
- 주택담보대출: 최대 LTV
- 금리: 현황 설명
- 기간: 일반 기준
- 조건: 기본 조건

【출력 형식】
{
    "qa_intro": "...",
    "qa_blocks": [
        {
            "q": "질문1",
            "a": "【분류1】\n• 항목1\n\n【분류2】\n• 항목2"
        },
        ...
    ],
    "financial_intro": "...",
    "tax_desc": "...",
    "contract_ratio": "10%",
    "contract_amount": "...",
    "midterm_ratio": "60%",
    "midterm_count": "6",
    "balance_ratio": "30%",
    "loan_info": "..."
}
```

---

## Stage 7️⃣: 스크립트 평가 에이전트

**담당 모델**: Gemini 3.1 Flash + 자동 검증
**입력**: Stage 2~6 모든 산출물
**출력**:
```json
{
    "quality_score": 85,
    "evaluation": {
        "stage2_score": 85,
        "stage2_issues": [],
        "stage3_score": 90,
        "stage3_issues": [],
        "stage4_score": 80,
        "stage4_issues": ["apt_intro가 200자 초과"],
        "stage5_score": 88,
        "stage5_issues": [],
        "stage6_score": 82,
        "stage6_issues": ["Q&A 3개만 작성됨 (권장 5~6개)"],
        "overall_status": "PASS"
    },
    "recommendations": [
        "Stage 4: apt_intro를 200자 이내로 단축하세요",
        "Stage 6: Q&A 2개 추가 작성 권장"
    ]
}
```

### 평가 기준

**Stage 2 (청약자격) 평가**
- 정책 정확성 (40%): Google Grounding 기반 최신 정책 반영
- 완성도 (30%): 3~5개 항목 충실성
- 명확성 (30%): 일반인 이해 가능성
- **기준점수**: 80점 이상

```python
def evaluate_stage2(eligibility_data):
    score = 100
    
    # 정책 정확성
    if not all(eligibility_data.get(k) for k in ["eligibility_special", "eligibility_rank1", "eligibility_rank2"]):
        score -= 20
    
    # 항목 수 확인
    special_count = len(eligibility_data.get("eligibility_special", []))
    rank1_count = len(eligibility_data.get("eligibility_rank1", []))
    if special_count < 3 or rank1_count < 3:
        score -= 15
    
    # 문장 길이 확인 (최대 30자/항목)
    for item in eligibility_data.get("eligibility_special", []):
        if len(item) > 30:
            score -= 5
            break
    
    return max(score, 0)
```

**Stage 3 (규제정보) 평가**
- 정확성 (50%): 공식 자료 기반
- 완성도 (50%): 필수 7개 항목 모두 충족
- **기준점수**: 85점 이상

```python
def evaluate_stage3(regulation_data):
    score = 100
    required_fields = [
        "is_hot_zone", "regulated_zone", "readmission_limit",
        "live_requirement", "price_cap", "resale_restriction", 
        "acquisition_tax_rate"
    ]
    
    missing = sum(1 for f in required_fields if not regulation_data.get(f))
    score -= missing * 10
    
    return max(score, 0)
```

**Stage 4 (단지소개) 평가**
- 길이 (20%): apt_intro 150~200자, post_title 15~50자
- 톤 (30%): 마케터 어투, 자연스러움
- 정보성 (30%): 핵심 정보 포함 (단지명, 규모, 평형)
- 형식 (20%): 구조적 완성도
- **기준점수**: 80점 이상

```python
def evaluate_stage4(intro_data):
    score = 100
    
    # apt_intro 길이
    intro_len = len(intro_data.get("apt_intro", ""))
    if intro_len < 150 or intro_len > 200:
        score -= 15
    
    # post_title 길이
    title_len = len(intro_data.get("post_title", ""))
    if title_len < 15 or title_len > 50:
        score -= 10
    
    # 핵심 정보 포함 확인
    intro = intro_data.get("apt_intro", "")
    if all(info in intro for info in ["세대", "평", "위치"]):
        pass
    else:
        score -= 15
    
    return max(score, 0)
```

**Stage 5 (입지분석) 평가**
- 정확성 (40%): 팩트 기반 (실제 거리, 학교명 등)
- 형식 (30%): 개조식, 길이 준수 (각 항목 300~2000자)
- 설득력 (30%): 장점 중심 서술, 별점과 설명 일관성
- **기준점수**: 85점 이상

```python
def evaluate_stage5(location_data):
    score = 100
    
    # 필수 필드 확인
    required = ["location_intro", "subway_score", "subway_detail",
                "school_score", "school_detail", "life_score", 
                "life_detail", "medical_score", "medical_detail"]
    
    if not all(location_data.get(f) for f in required):
        score -= 20
    
    # 길이 확인
    intro_len = len(location_data.get("location_intro", ""))
    if intro_len < 200 or intro_len > 500:
        score -= 15
    
    # 별점 형식 확인
    for key in ["subway_score", "school_score", "life_score", "medical_score"]:
        score_str = location_data.get(key, "")
        if not ("★" in score_str and len(score_str) <= 5):
            score -= 10
            break
    
    return max(score, 0)
```

**Stage 6 (Q&A) 평가**
- 질문 다양성 (25%): 3~7개, 주제 다양성
- 답변 정확성 (35%): 팩트 기반, 개인화 조언 없음
- 형식 (20%): 개조식, 길이 준수 (300~2000자)
- 금지사항 준수 (20%): 개인적 조언 없음
- **기준점수**: 80점 이상

```python
def evaluate_stage6(qa_data):
    score = 100
    
    # Q&A 개수
    qa_blocks = qa_data.get("qa_blocks", [])
    if len(qa_blocks) < 3 or len(qa_blocks) > 7:
        score -= 20
    
    # 답변 길이
    short_answers = sum(1 for qa in qa_blocks if len(qa.get("a", "")) < 300)
    if short_answers > 0:
        score -= 10
    
    # 금지 키워드 검사
    forbidden = ["당신", "귀하", "개인", "소득이", "자산이", "세대주이면"]
    for qa in qa_blocks:
        if any(keyword in qa.get("a", "") for keyword in forbidden):
            score -= 15
            break
    
    # financial_intro, tax_desc 확인
    if not qa_data.get("financial_intro") or not qa_data.get("tax_desc"):
        score -= 15
    
    return max(score, 0)
```

### 최종 평가 프롬프트

```
당신은 블로그 포스팅 품질 평가 전문가입니다.

【평가 대상】
- Stage 2: 청약자격 요건
- Stage 3: 규제정보
- Stage 4: 단지 소개
- Stage 5: 입지 분석
- Stage 6: Q&A 및 자금계획

【평가 방식】
각 Stage별로 자동 및 LLM 평가를 진행합니다.

1. 자동 검증:
   - 길이 확인
   - 필수 필드 확인
   - 형식 확인
   - 금지 키워드 확인

2. LLM 평가:
   - 팩트 정확성 (Google Grounding 확인)
   - 톤 및 스타일
   - 정보 충실성
   - 가독성

【최종 판정】
- 80점 이상: ✅ PASS → HTML 렌더링 진행
- 70~79점: ⚠️ WARNING → 해당 Stage 재작성 권장
- 70점 미만: ❌ FAIL → 해당 Stage 재작성 필수

【출력】
{
    "quality_score": 0~100,
    "evaluation": {
        "stage2": {...},
        "stage3": {...},
        ...
    },
    "overall_status": "PASS|WARNING|FAIL",
    "recommendations": ["...", "..."]
}
```

---

## 프롬프트 사용 가이드

### Gemini 3.1 Flash Lite (경량, 빠름)
- Stage 2: 청약자격
- Stage 4: 단지소개
- 용도: 정책 기반 정보, 마케팅 텍스트

### Gemini 3.1 Flash (표준)
- Stage 3: 규제정보
- Stage 5: 입지분석
- Stage 6: Q&A
- 용도: 복합 정보 분석, 상세 설명

### Google Grounding
- 모든 Gemini 호출에 포함
- 용도: 최신 정부 정책, 실제 지역 정보 확인

### Google Maps API
- Stage 5: 입지분석
- 용도: 실제 거리, 소요시간 측정

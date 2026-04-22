# 청약홈 분양정보 조회 서비스 API 필드 문서

**출처**: https://infuser.odcloud.kr/api/stages/37000/api-docs  
**서비스**: 한국부동산원 청약홈 공공데이터 OpenAPI

---

## 1. API 엔드포인트

### 1.1 APT 분양정보 상세조회
**엔드포인트**: `getAPTLttotPblancDetail`  
**설명**: APT 분양정보의 모집공고일, 청약일정 등 상세정보 조회

**주요 쿼리 파라미터**:
- `cond[HOUSE_NM::LIKE]`: 주택명 (아파트 이름으로 검색)
- `cond[HOUSE_MANAGE_NO::EQ]`: 주택관리번호 (정확한 검색)

---

### 1.2 APT 주택형별 상세조회
**엔드포인트**: `getAPTLttotPblancMdl`  
**설명**: 아파트의 주택형별 분양가 정보 조회

**주요 쿼리 파라미터**:
- `cond[HOUSE_MANAGE_NO::EQ]`: 주택관리번호 (필수)
- `cond[PBLANC_NO::EQ]`: 공고번호

---

## 2. 핵심 필드 매핑

| 항목 | 필드명 | 엔드포인트 | 설명 | 형식 |
|------|--------|-----------|------|------|
| **분양가 (최고)** | `LTTOT_TOP_AMOUNT` | getAPTLttotPblancMdl | 공급금액(분양최고금액) | 만원 단위 |
| **분양가 (최저)** | LTTOT_BTM_AMOUNT* | getAPTLttotPblancMdl | 공급금액(분양최저금액) | 만원 단위 |
| **모집공고일** | `RCRIT_PBLANC_DE` | getAPTLttotPblancDetail | 공고가 나온 날짜 | YYYY-MM-DD |
| **특별공급 접수 시작일** | `SPSPLY_RCEPT_BGNDE` | getAPTLttotPblancDetail | 특별공급 청약 시작일 | YYYY-MM-DD |
| **특별공급 접수 종료일** | `SPSPLY_RCEPT_ENDDE` | getAPTLttotPblancDetail | 특별공급 청약 종료일 | YYYY-MM-DD |
| **1순위 해당지역 시작일** | `GNRL_RNK1_CRSPAREA_RCPTDE` | getAPTLttotPblancDetail | 1순위 해당지역 접수 시작 | YYYY-MM-DD |
| **1순위 해당지역 종료일** | `GNRL_RNK1_CRSPAREA_ENDDE` | getAPTLttotPblancDetail | 1순위 해당지역 접수 종료 | YYYY-MM-DD |
| **1순위 경기지역 시작일** | `GNRL_RNK1_ETC_GG_RCPTDE` | getAPTLttotPblancDetail | 1순위 경기지역 접수 시작 | YYYY-MM-DD |
| **1순위 경기지역 종료일** | `GNRL_RNK1_ETC_GG_ENDDE` | getAPTLttotPblancDetail | 1순위 경기지역 접수 종료 | YYYY-MM-DD |
| **1순위 기타지역 시작일** | `GNRL_RNK1_ETC_AREA_RCPTDE` | getAPTLttotPblancDetail | 1순위 기타지역 접수 시작 | YYYY-MM-DD |
| **1순위 기타지역 종료일** | `GNRL_RNK1_ETC_AREA_ENDDE` | getAPTLttotPblancDetail | 1순위 기타지역 접수 종료 | YYYY-MM-DD |
| **2순위 해당지역 시작일** | `GNRL_RNK2_CRSPAREA_RCPTDE` | getAPTLttotPblancDetail | 2순위 해당지역 접수 시작 | YYYY-MM-DD |
| **2순위 해당지역 종료일** | `GNRL_RNK2_CRSPAREA_ENDDE` | getAPTLttotPblancDetail | 2순위 해당지역 접수 종료 | YYYY-MM-DD |
| **2순위 경기지역 시작일** | `GNRL_RNK2_ETC_GG_RCPTDE` | getAPTLttotPblancDetail | 2순위 경기지역 접수 시작 | YYYY-MM-DD |
| **2순위 경기지역 종료일** | `GNRL_RNK2_ETC_GG_ENDDE` | getAPTLttotPblancDetail | 2순위 경기지역 접수 종료 | YYYY-MM-DD |
| **2순위 기타지역 시작일** | `GNRL_RNK2_ETC_AREA_RCPTDE` | getAPTLttotPblancDetail | 2순위 기타지역 접수 시작 | YYYY-MM-DD |
| **2순위 기타지역 종료일** | `GNRL_RNK2_ETC_AREA_ENDDE` | getAPTLttotPblancDetail | 2순위 기타지역 접수 종료 | YYYY-MM-DD |

*현재 사용 중이 아님

---

## 3. post_meta.json 필드 매핑

```json
{
  "price_range": "LTTOT_TOP_AMOUNT (주택형별 min~max)",
  "notice_date": "RCRIT_PBLANC_DE",
  "special_supply_date": "SPSPLY_RCEPT_BGNDE (첫 시작일)",
  "rank1_date": "GNRL_RNK1_CRSPAREA_RCPTDE (또는 첫 번째 1순위 시작일)",
  "rank2_date": "GNRL_RNK2_CRSPAREA_RCPTDE (또는 첫 번째 2순위 시작일)"
}
```

---

## 4. 기본 식별자

| 필드명 | 설명 | 예시 |
|--------|------|------|
| `HOUSE_MANAGE_NO` | 주택관리번호 (고유 ID) | 2026000051 |
| `PBLANC_NO` | 공고번호 | 2026000051 |
| `HOUSE_NM` | 주택명 (아파트 이름) | 아산탕정자이 메트로시티 |

---

## 5. API 호출 예시

### 검색 (아파트명으로)
```
GET https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail
  ?serviceKey=YOUR_API_KEY
  &page=1
  &perPage=100
  &cond[HOUSE_NM::LIKE]=힐스테이트
```

### 상세 조회 (주택관리번호로)
```
GET https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail
  ?serviceKey=YOUR_API_KEY
  &cond[HOUSE_MANAGE_NO::EQ]=2026000085
```

### 주택형별 조회
```
GET https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl
  ?serviceKey=YOUR_API_KEY
  &cond[HOUSE_MANAGE_NO::EQ]=2026000085
```

---

## 6. 중요 노트

1. **분양가**: 상세조회 응답에 없음. 주택형별 조회(Mdl)에서만 제공
2. **날짜 형식**: YYYY-MM-DD 또는 YYYYMMDD (API마다 상이)
3. **1순위/2순위**: 지역별(해당지역, 경기지역, 기타지역)로 세분화됨
4. **특별공급**: 특별공급 시작일(BGNDE)을 기본값으로 사용
5. **공고 검색**: 아파트명(LIKE) 또는 주택관리번호(EQ) 사용 권장

---

## 7. audit_prices_with_api.py에서 사용 중인 필드

✅ **정확한 필드명**:
- `RCRIT_PBLANC_DE` → notice_date
- `SPSPLY_RCEPT_BGNDE` → special_supply_date
- `GNRL_RNK1_CRSPAREA_RCPTDE` → rank1_date
- `GNRL_RNK2_CRSPAREA_RCPTDE` → rank2_date
- `LTTOT_TOP_AMOUNT` → price_range (주택형별 조회)

---

**마지막 업데이트**: 2026-04-22  
**버전**: 1.0

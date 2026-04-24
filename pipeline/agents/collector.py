"""
collector.py
────────────────────────────────────────────────────
청약홈 데이터 수집기 (두 가지 소스 지원)

[소스 A] 공공데이터포털 OpenAPI (실시간 권장)
  - 데이터셋 ID: 15098547
  - REST JSON, 영문 필드명
  - 엔드포인트:
      목록/상세: getAPTLttotPblancDetail
      주택형별: getAPTLttotPblancMdl

[소스 B] 공공데이터포털 파일 데이터 (연간 CSV)
  - 데이터셋 ID: 15101046
  - CSV, 한글 컬럼명
  - 활용 방법: 포털에서 CSV 직접 다운로드 후 로컬 로드

두 소스의 필드명을 NoticeDocument 단일 구조로 통합합니다.
────────────────────────────────────────────────────

API 기술문서:
  https://www.reb.or.kr/reb/na/ntt/selectNttInfo.do?mi=10251&bbsId=1268&nttSn=79889
  (최신: 기술문서_청약홈 분양정보 조회 서비스_260129.docx)
"""

import sys
import os
import re
import csv
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

sys.path.append(str(Path(__file__).parent.parent))
from config import PUBLIC_DATA_API_KEY, OUTPUT_DIR


# ══════════════════════════════════════════════════
# 1. NoticeDocument 데이터 구조
# ══════════════════════════════════════════════════

@dataclass
class NoticeDocument:
    """수집된 분양 공고 정규화 구조체"""
    # 식별
    notice_id: str           # 공고번호 (PBLANC_NO / 공고번호)
    house_manage_no: str     # 주택관리번호

    # 단지 기본
    apt_name: str            # 주택명 (단지명)
    house_type: str          # 주택구분코드명 (민영/공공)
    house_detail_type: str   # 주택상세구분코드명
    supply_type: str         # 분양구분코드명

    # 위치
    region_code: str         # 공급지역코드
    region_name: str         # 공급지역명 (시도명)
    supply_address: str      # 공급위치

    # 규모
    total_units: str         # 공급규모 (총 세대수)

    # 청약 일정
    notice_date: str         # 모집공고일
    special_supply_start: str   # 특별공급 접수시작일
    special_supply_end: str     # 특별공급 접수종료일
    rank1_local_start: str   # 해당지역 1순위 시작
    rank1_local_end: str     # 해당지역 1순위 종료
    rank1_near_start: str    # 경기지역 1순위 시작
    rank1_near_end: str      # 경기지역 1순위 종료
    rank1_etc_start: str     # 기타지역 1순위 시작
    rank1_etc_end: str       # 기타지역 1순위 종료
    rank2_local_start: str   # 해당지역 2순위 시작
    rank2_local_end: str     # 해당지역 2순위 종료
    rank2_near_start: str    # 경기지역 2순위 시작
    rank2_near_end: str      # 경기지역 2순위 종료
    rank2_etc_start: str     # 기타지역 2순위 시작
    rank2_etc_end: str       # 기타지역 2순위 종료
    winner_date: str         # 당첨자발표일
    contract_start: str      # 계약시작일
    contract_end: str        # 계약종료일
    move_in_month: str       # 입주예정월 (YYYY-MM)

    # 사업자
    constructor: str         # 건설업체명(시공사)
    developer: str           # 사업주체명(시행사)
    contact: str             # 문의처
    homepage: str            # 홈페이지주소
    notice_url: str          # 모집공고홈페이지주소

    # 규제 여부 (Y/N)
    is_hot_zone: str         # 투기과열지구
    is_adj_zone: str         # 조정대상지역
    is_price_cap: str        # 분양가상한제
    is_redevelop: str        # 정비사업
    is_public_dist: str      # 공공주택지구
    is_large_dev: str        # 대규모택지개발지구
    is_metro_private: str    # 수도권내민영공공주택지구

    # 원문 텍스트 (RAG용)
    raw_text: str = ""
    tables: list = field(default_factory=list)
    pdf_path: str | None = None
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def supply_date(self) -> str:
        """1순위 접수 시작일 (대표 청약일)"""
        return self.rank1_local_start or self.rank1_near_start or self.rank1_etc_start

    @property
    def region(self) -> str:
        return self.region_name

    @property
    def district(self) -> str:
        parts = self.supply_address.split()
        return parts[1] if len(parts) > 1 else ""

    def to_rag_text(self) -> str:
        """RAG 임베딩용 텍스트"""
        flags = []
        if self.is_hot_zone == "Y":   flags.append("투기과열지구")
        if self.is_adj_zone == "Y":   flags.append("조정대상지역")
        if self.is_price_cap == "Y":  flags.append("분양가상한제 적용")
        if self.is_redevelop == "Y":  flags.append("정비사업")

        table_text = "\n".join(
            " | ".join(str(c) for c in row)
            for t in self.tables for row in t
        )

        return f"""
[단지명] {self.apt_name}
[주택구분] {self.house_type} / {self.house_detail_type}
[공급지역] {self.region_name}
[공급위치] {self.supply_address}
[총 공급세대] {self.total_units}세대
[모집공고일] {self.notice_date}
[특별공급] {self.special_supply_start} ~ {self.special_supply_end}
[1순위 청약] 해당지역: {self.rank1_local_start} ~ {self.rank1_local_end}
[2순위 청약] 해당지역: {self.rank2_local_start} ~ {self.rank2_local_end}
[당첨자발표] {self.winner_date}
[계약] {self.contract_start} ~ {self.contract_end}
[입주예정] {self.move_in_month}
[시공사] {self.constructor}
[시행사] {self.developer}
[문의처] {self.contact}
[규제사항] {', '.join(flags) if flags else '없음'}

{self.raw_text}

[표 데이터]
{table_text}
""".strip()


# ══════════════════════════════════════════════════
# 2. OpenAPI 필드 매핑 (영문 → NoticeDocument)
#    소스: 청약홈 분양정보 조회 서비스 (15098547)
#    기술문서: 260129 기준
# ══════════════════════════════════════════════════

def _from_openapi(d: dict) -> dict:
    """OpenAPI 영문 JSON → 정규화 딕셔너리"""
    return {
        "notice_id":           str(d.get("PBLANC_NO", "")),
        "house_manage_no":     str(d.get("HOUSE_MANAGE_NO", "")),
        "apt_name":            d.get("HOUSE_NM", ""),
        "house_type":          d.get("HOUSE_SECD_NM", ""),
        "house_detail_type":   d.get("RENTBSNS_HOUSE_SECD_NM", ""),
        "supply_type":         d.get("SUBSCRPT_TYCD_NM", ""),
        "region_code":         d.get("SUBSCRPT_AREA_CODE", ""),
        "region_name":         d.get("SUBSCRPT_AREA_CODE_NM", ""),
        "supply_address":      d.get("HSSPLY_ADRES", ""),
        "total_units":         str(d.get("TOT_SUPLY_HSHLDCO", "")),
        "notice_date":         d.get("RCRIT_PBLANC_DE", ""),
        "special_supply_start":d.get("SPSPLY_RCEPT_BGNDE", ""),
        "special_supply_end":  d.get("SPSPLY_RCEPT_ENDDE", ""),
        "rank1_local_start":   d.get("GNRL_RNK1_CRSPAREA_RCPTDE", ""),
        "rank1_local_end":     d.get("GNRL_RNK1_CRSPAREA_ENDDE", ""),
        "rank1_near_start":    d.get("GNRL_RNK1_ETC_GG_RCPTDE", ""),
        "rank1_near_end":      d.get("GNRL_RNK1_ETC_GG_ENDDE", ""),
        "rank1_etc_start":     d.get("GNRL_RNK1_ETC_AREA_RCPTDE", ""),
        "rank1_etc_end":       d.get("GNRL_RNK1_ETC_AREA_ENDDE", ""),
        "rank2_local_start":   d.get("GNRL_RNK2_CRSPAREA_RCPTDE", ""),
        "rank2_local_end":     d.get("GNRL_RNK2_CRSPAREA_ENDDE", ""),
        "rank2_near_start":    d.get("GNRL_RNK2_ETC_GG_RCPTDE", ""),
        "rank2_near_end":      d.get("GNRL_RNK2_ETC_GG_ENDDE", ""),
        "rank2_etc_start":     d.get("GNRL_RNK2_ETC_AREA_RCPTDE", ""),
        "rank2_etc_end":       d.get("GNRL_RNK2_ETC_AREA_ENDDE", ""),
        "winner_date":         d.get("PRZWNER_PRESNATN_DE", ""),
        "contract_start":      d.get("CNTRCT_CNCLS_BGNDE", ""),
        "contract_end":        d.get("CNTRCT_CNCLS_ENDDE", ""),
        "move_in_month":       d.get("MVN_PREARNGE_YM", ""),
        "constructor":         d.get("CNSTRCT_ENTRPS_NM", ""),
        "developer":           d.get("BSNS_MBY_NM", ""),
        "contact":             d.get("MDHS_TELNO", ""),
        "homepage":            d.get("HMPG_ADRES", ""),
        "notice_url":          d.get("PBLANC_URL", ""),
        "is_hot_zone":         d.get("SPECLT_RDN_EARTH_AT", "N"),
        "is_adj_zone":         d.get("MDAT_TRGET_AREA_SECD", "N"),
        "is_price_cap":        d.get("PARCPRC_ULS_AT", "N"),
        "is_redevelop":        d.get("IMPRMN_BSNS_AT", "N"),
        "is_public_dist":      d.get("PUBLIC_HOUSE_EARTH_AT", "N"),
        "is_large_dev":        d.get("LRSCL_BLDLND_AT", "N"),
        "is_metro_private":    d.get("NPLN_PRVOPR_PUBLIC_HOUSE_AT", "N"),
    }


# ══════════════════════════════════════════════════
# 3. CSV 파일 필드 매핑 (한글 → NoticeDocument)
#    소스: 공공데이터포털 파일 데이터 (15101046)
#    컬럼 정의: www.stgdata.co.kr/data/15101046/fileDataSmpl.do
# ══════════════════════════════════════════════════

def _from_csv_row(d: dict) -> dict:
    """CSV 한글 컬럼 행 → 정규화 딕셔너리"""
    return {
        "notice_id":           d.get("공고번호", ""),
        "house_manage_no":     d.get("주택관리번호", ""),
        "apt_name":            d.get("주택명", ""),
        "house_type":          d.get("주택구분코드명", ""),
        "house_detail_type":   d.get("주택상세구분코드명", ""),
        "supply_type":         d.get("분양구분코드명", ""),
        "region_code":         d.get("공급지역코드", ""),
        "region_name":         d.get("공급지역명", ""),
        "supply_address":      d.get("공급위치", ""),
        "total_units":         str(d.get("공급규모", "")),
        "notice_date":         d.get("모집공고일", ""),
        "special_supply_start":d.get("특별공급접수시작일", ""),
        "special_supply_end":  d.get("특별공급접수종료일", ""),
        "rank1_local_start":   d.get("해당지역1순위접수시작일", ""),
        "rank1_local_end":     d.get("해당지역1순위접수종료일", ""),
        "rank1_near_start":    d.get("경기지역1순위접수시작일", ""),
        "rank1_near_end":      d.get("경기지역1순위접수종료일", ""),
        "rank1_etc_start":     d.get("기타지역1순위접수시작일", ""),
        "rank1_etc_end":       d.get("기타지역1순위접수종료일", ""),
        "rank2_local_start":   d.get("해당지역2순위접수시작일", ""),
        "rank2_local_end":     d.get("해당지역2순위접수종료일", ""),
        "rank2_near_start":    d.get("경기지역2순위접수시작일", ""),
        "rank2_near_end":      d.get("경기지역2순위접수종료일", ""),
        "rank2_etc_start":     d.get("기타지역2순위접수시작일", ""),
        "rank2_etc_end":       d.get("기타지역2순위접수종료일", ""),
        "winner_date":         d.get("당첨자발표일", ""),
        "contract_start":      d.get("계약시작일", ""),
        "contract_end":        d.get("계약종료일", ""),
        "move_in_month":       d.get("입주예정월", ""),
        "constructor":         d.get("건설업체명_시공사", ""),
        "developer":           d.get("사업주체명_시행사", ""),
        "contact":             d.get("문의처", ""),
        "homepage":            d.get("홈페이지주소", ""),
        "notice_url":          d.get("모집공고홈페이지주소", ""),
        "is_hot_zone":         d.get("투기과열지구", "N"),
        "is_adj_zone":         d.get("조정대상지역", "N"),
        "is_price_cap":        d.get("분양가상한제", "N"),
        "is_redevelop":        d.get("정비사업", "N"),
        "is_public_dist":      d.get("공공주택지구", "N"),
        "is_large_dev":        d.get("대규모택지개발지구", "N"),
        "is_metro_private":    d.get("수도권내민영공공주택지구", "N"),
    }


def _build_document(normalized: dict) -> NoticeDocument:
    """정규화 딕셔너리 → NoticeDocument"""
    return NoticeDocument(**{k: v for k, v in normalized.items()
                              if k in NoticeDocument.__dataclass_fields__})


# ══════════════════════════════════════════════════
# 4. OpenAPI 클라이언트
#    엔드포인트: 공공데이터포털 (data.go.kr)
#    서비스 ID: 15098547
# ══════════════════════════════════════════════════

# 공공데이터포털 파일 데이터 자동변환 API 기반
# (15098547 OpenAPI는 별도 활용신청 후 serviceKey 발급 필요)
API_BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"

class CheongYakAPI:
    """
    청약홈 분양정보 OpenAPI 클라이언트

    활용 신청 (필수):
      1. https://www.data.go.kr 회원가입
      2. "한국부동산원_청약홈 분양정보 조회 서비스" 검색
      3. 활용신청 → 개발계정 즉시 발급 (40,000회/일)
      4. .env 파일의 PUBLIC_DATA_API_KEY에 입력
    """

    def __init__(self, api_key: str = PUBLIC_DATA_API_KEY):
        self.api_key = api_key

    async def get_list(
        self,
        page: int = 1,
        per_page: int = 20,
        region_code: str | None = None,
        start_date: str | None = None,  # YYYY-MM-DD
    ) -> list[dict]:
        """
        APT 분양정보 상세 목록 조회 (getAPTLttotPblancDetail)

        파라미터 (기술문서 260129 기준):
          page, perPage: 페이지
          SUBSCRPT_AREA_CODE: 공급지역코드 (예: 41=경기)
          RCRIT_PBLANC_DE: 모집공고일 (YYYY-MM-DD)
        """
        params: dict = {
            "serviceKey": self.api_key,
            "page":       page,
            "perPage":    per_page,
        }
        if region_code:
            params["cond[SUBSCRPT_AREA_CODE::EQ]"] = region_code
        if start_date:
            params["cond[RCRIT_PBLANC_DE::GTE]"] = start_date

        return await self._get(f"{API_BASE}/getAPTLttotPblancDetail", params)

    async def get_detail(self, house_manage_no: str) -> dict:
        """
        APT 분양정보 상세 조회 (getAPTLttotPblancDetail)

        추가 응답 필드 (목록에 없음):
          - 분양가 정보 (공급금액 등)
          - 실거주의무 여부
          - 중도금 대출 정보 등
        """
        params = {
            "serviceKey":     self.api_key,
            "page":           1,
            "perPage":        1,
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
        }
        items = await self._get(f"{API_BASE}/getAPTLttotPblancDetail", params)
        return items[0] if items else {}

    async def get_unit_types(self, house_manage_no: str) -> list[dict]:
        """
        APT 분양정보 주택형별 상세 조회 (getAPTLttotPblancMdl)

        응답 필드:
          HOUSE_TY: 주택형 (예: 59A)
          SUPLY_AR: 공급면적
          EXCLUSE_AR: 전용면적
          GNRL_HOSP_CO: 일반공급 세대수
          SPSPLY_HOSP_CO: 특별공급 세대수
          LTTOT_TOP_AMOUNT: 분양가 상한금액 (만원)
          ...
        """
        params = {
            "serviceKey": self.api_key,
            "page":       1,
            "perPage":    50,
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
        }
        return await self._get(f"{API_BASE}/getAPTLttotPblancMdl", params)

    async def _get(self, url: str, params: dict) -> list[dict]:
        print(f"  [API] _get() 호출됨 - URL: {url}")
        print(f"  [API] 파라미터: {params}")

        if not self.api_key or "여기에" in str(self.api_key):
            print(f"  [API] serviceKey 미설정 → 샘플 데이터 사용")
            return []

        # API 키 상태 확인 (처음에만 한 번)
        if not hasattr(self, '_key_logged'):
            key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else "***"
            print(f"  [API] API 키 확인: {key_preview} (길이: {len(self.api_key)})")
            self._key_logged = True

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                print(f"  [API] GET 요청 시작...")
                resp = await client.get(url, params=params)
                print(f"  [API] 상태 코드: {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", [])
                total = data.get("totalCount", len(items))
                print(f"  [API] {len(items)}건 조회 (전체 {total}건)")
                return items
            except httpx.HTTPStatusError as e:
                print(f"  [API] HTTP 오류 {e.response.status_code}: {url}")
                print(f"  [API] 전체 응답: {e.response.text}")
                return []
            except Exception as e:
                print(f"  [API] 오류: {e}")
                import traceback
                traceback.print_exc()
                return []


# ══════════════════════════════════════════════════
# 5. CSV 파일 로더 (파일 데이터 소스 B)
# ══════════════════════════════════════════════════

def load_from_csv(csv_path: Path) -> list[NoticeDocument]:
    """
    공공데이터포털 CSV 파일 → NoticeDocument 목록
    (다운로드 경로: data.go.kr → 15101046 → 다운로드)

    CSV 인코딩: UTF-8 (BOM 포함 가능)
    """
    docs = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = _from_csv_row(dict(row))
            doc = _build_document(normalized)
            docs.append(doc)
    print(f"  [CSV] {len(docs)}건 로드: {csv_path.name}")
    return docs


# ══════════════════════════════════════════════════
# 6. 통합 수집 함수
# ══════════════════════════════════════════════════

_RESUPPLY_KEYWORDS = ("무순위", "잔여", "재공급", "취소후", "불법행위")


def _supply_category(supply_type: str) -> str:
    """공급 유형 → '신규' | '무순위/재공급' 구분"""
    if any(kw in supply_type for kw in _RESUPPLY_KEYWORDS):
        return "무순위/재공급"
    return "신규"


async def collect_from_api(days_back: int = 7) -> list[NoticeDocument]:
    """OpenAPI로 최근 N일 공고 수집"""
    print(f"[DEBUG] collect_from_api 시작: days_back={days_back}")
    api = CheongYakAPI()
    print(f"[DEBUG] CheongYakAPI 초기화 완료")
    today = datetime.now()
    start = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    print(f"[DEBUG] 시작일: {start}")

    raw_list = await api.get_list(per_page=50, start_date=start)
    if not raw_list:
        print("  [수집] 최근 공고 없음.")
        return []

    docs = []
    for item in raw_list:
        normalized = _from_openapi(item)
        doc = _build_document(normalized)
        category = _supply_category(doc.supply_type)
        print(f"  [수집] {doc.apt_name} — 공급유형: {doc.supply_type or '미확인'} ({category})")

        # 주택형별 데이터 추가
        if doc.house_manage_no:
            units = await api.get_unit_types(doc.house_manage_no)
            if units:
                unit_text = _units_to_text(units)
                doc.raw_text += f"\n\n[주택형별 정보]\n{unit_text}"
            else:
                # 무순위/재공급: 주택형 API 미지원 → 총 세대수 기반 텍스트 생성
                print(f"  ⚠️  {doc.apt_name}: 주택형별 API 데이터 없음 ({category})")
                if category == "무순위/재공급" and doc.total_units:
                    doc.raw_text += (
                        f"\n\n[공급 정보]\n"
                        f"공급유형: {doc.supply_type}\n"
                        f"잔여/공급 세대수: {doc.total_units}세대\n"
                        f"※ 분양가는 공고문 원문을 직접 확인하세요."
                    )

        docs.append(doc)

    print(f"\n  [수집 완료] {len(docs)}건")
    return docs


def _units_to_text(units: list[dict]) -> str:
    """주택형별 상세 응답 → 텍스트"""
    lines = []
    for u in units:
        house_type = u.get("HOUSE_TY", "")
        excl_ar    = u.get("EXCLUSE_AR", "")
        suply_ar   = u.get("SUPLY_AR", "")
        # GNRL_HOSP_CO / SPSPLY_HOSP_CO: API 문서 기준 필드명
        # SUPLY_HSHLDCO / SPSPLY_HSHLDCO: 일부 응답 변형 대비 폴백
        gnrl_cnt   = u.get("GNRL_HOSP_CO") or u.get("SUPLY_HSHLDCO", "")
        spsply_cnt = u.get("SPSPLY_HOSP_CO") or u.get("SPSPLY_HSHLDCO", "")
        top_price  = u.get("LTTOT_TOP_AMOUNT", "")
        low_price  = u.get("LTTOT_LOWPR_AMOUNT", "")
        price_str  = f"{low_price}~{top_price}" if low_price and top_price and low_price != top_price else (top_price or "-")
        lines.append(
            f"{house_type}타입 | 전용 {excl_ar}㎡ | 공급 {suply_ar}㎡ "
            f"| 일반 {gnrl_cnt}세대 | 특별 {spsply_cnt}세대 "
            f"| 분양가 {price_str}만원"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════
# 7. 샘플 데이터 (API 키 없을 때 테스트용)
# ══════════════════════════════════════════════════

def get_sample_document() -> NoticeDocument:
    """
    테스트용 샘플 공고 - 오티에르 반포 (실제 공공데이터)
    실제 데이터 구조(필드명)와 동일하게 구성
    """
    doc = NoticeDocument(
        notice_id           = "2026000058",
        house_manage_no     = "2026000058",
        apt_name            = "오티에르 반포",
        house_type          = "민영",
        house_detail_type   = "아파트",
        supply_type         = "분양",
        region_code         = "100",
        region_name         = "서울",
        supply_address      = "서울특별시 서초구 잠원동 59-10번지 외 3필지",
        total_units         = "86",
        notice_date         = "2026-03-31",
        special_supply_start= "2026-04-10",
        special_supply_end  = "2026-04-10",
        rank1_local_start   = "2026-04-13",
        rank1_local_end     = "2026-04-13",
        rank1_near_start    = "2026-04-14",
        rank1_near_end      = "2026-04-14",
        rank1_etc_start     = "2026-04-15",
        rank1_etc_end       = "2026-04-15",
        rank2_local_start   = "2026-04-15",
        rank2_local_end     = "2026-04-15",
        rank2_near_start    = "",
        rank2_near_end      = "",
        rank2_etc_start     = "",
        rank2_etc_end       = "",
        winner_date         = "2026-04-21",
        contract_start      = "2026-05-06",
        contract_end        = "2026-05-08",
        move_in_month       = "2026-07",
        constructor         = "㈜포스코이앤씨",
        developer           = "신반포21차아파트주택재건축정비사업조합",
        contact             = "15992510",
        homepage            = "https://오티에르반포.kr",
        notice_url          = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000058&pblancNo=2026000058",
        is_hot_zone         = "Y",
        is_adj_zone         = "Y",
        is_price_cap        = "N",
        is_redevelop        = "Y",
        is_public_dist      = "N",
        is_large_dev        = "N",
        is_metro_private    = "N",
    )

    doc.raw_text = """
[분양가 정보]
44.0000㎡ 전용: 분양가 1억4264만원 / 3.3㎡당 약 4,750만원
44.8507B㎡ 전용: 분양가 1억4416만원 / 3.3㎡당 약 4,750만원
45.0000㎡ 전용: 분양가 1억4453만원 / 3.3㎡당 약 4,750만원

[중도금 대출]
중도금 무이자 집단대출 가능 (분양가의 60%)

[전매 제한]
전매제한 3년

[주택형별 공급]
44.0000㎡ | 일반 5세대 | 특별 5세대 | 분양가 142,640만원
44.8507B㎡ | 일반 2세대 | 특별 1세대 | 분양가 144,160만원
45.0000㎡ 이상 | 일반 69세대 | 특별 (계속)

[입지 정보]
신분당선 반포역 인근 / 서초구 강남권 중심지
강남대로 접근성 우수
배정학교: (확인 필요)
인근: 신세계백화점 강남점 인근, 서울성모병원 인근
""".strip()

    doc.tables = [
        [["타입", "전용(㎡)", "일반공급", "특별공급", "분양가"],
         ["44.00", "44.00", "5", "5", "1.426억"],
         ["44.85B", "44.85", "2", "1", "1.441억"],
         ["45.00+", "45.00+", "69", "7", "1.445억+"]]
    ]
    return doc


# ══════════════════════════════════════════════════
# 단독 실행 테스트
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("수집기 테스트")
    print("=" * 55)

    doc = get_sample_document()
    print(f"단지명   : {doc.apt_name}")
    print(f"주소     : {doc.supply_address}")
    print(f"1순위    : {doc.rank1_local_start} ~ {doc.rank1_local_end}")
    print(f"당첨발표 : {doc.winner_date}")
    print(f"입주예정 : {doc.move_in_month}")
    print(f"시공사   : {doc.constructor}")
    print(f"투기과열 : {doc.is_hot_zone} / 분양가상한제: {doc.is_price_cap}")
    print(f"\n[RAG 텍스트 (앞 500자)]\n{doc.to_rag_text()[:500]}...")

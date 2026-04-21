"""
patch_policy_data.py — 기존 포스트 청약 규제 정보 실채움

처리 순서 (포스트마다):
  1. post_meta.json에서 notice_url → houseManageNo / pblancNo 파싱
  2. 청약홈 OpenAPI → SPECLT_RDN_EARTH_AT (투기과열지구 여부)
     실패 시 → post.html Q&A 텍스트 regex 폴백
  3. notice_url PDF 다운로드 → pdfplumber 텍스트 추출 → Claude Haiku 재추출
     실패 시 → post.html Q&A 텍스트 regex 폴백
  4. post.html 청약 규제 정보 카드 3항목 + 전매제한 안내 카드 패치
  5. post_meta.json 업데이트

실행:
  python patch_policy_data.py [--dry-run] [--limit N]
"""

import asyncio
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "pipeline"))

POSTS_DIR = ROOT / "output" / "posts"

# ── 환경변수 로드 ──────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── API 엔드포인트 ─────────────────────────────────────────────
APT_DETAIL_API = (
    "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"
)

# ── LLM 재추출 프롬프트 ────────────────────────────────────────
POLICY_EXTRACT_PROMPT = """아래는 아파트 분양 공고문 텍스트 일부입니다.
다음 세 항목을 공고문에서 정확히 추출하세요.

추출 항목:
1. resale_restriction: 전매제한 기간
   - "제한사항", "전매제한", "계약 조건", "소유권이전" 섹션에서 찾으세요
   - 예: "소유권이전등기일로부터 3년", "입주 후 6개월", "분양가상한제 적용 10년", "없음"
   - 조건별로 다를 경우 가장 긴 기간으로 요약
2. live_requirement: 실거주 의무 기간
   - "거주의무", "실거주 의무", "실거주기간" 항목에서 찾으세요
   - 예: "2년 이상 실거주", "없음", "해당 없음"
3. is_hot_zone: 투기과열지구 해당 여부
   - "규제지역", "투기과열지구", "청약조정대상지역" 항목에서 찾으세요
   - 반드시 "Y", "N", "해당없음" 중 하나만 반환
   - 공고에 없으면 null

공고문에서 명시적으로 확인된 내용만 추출하세요. 없으면 null.

[공고문 텍스트]:
{pdf_text}

JSON만 출력 (다른 텍스트 없이):
{{
  "resale_restriction": "...",
  "live_requirement": "...",
  "is_hot_zone": "Y/N/해당없음 또는 null"
}}"""


# ── 헬퍼: notice_url → houseManageNo / pblancNo ───────────────
def parse_house_ids(notice_url: str) -> tuple[str, str]:
    """URL 쿼리에서 houseManageNo, pblancNo 파싱"""
    if not notice_url:
        return "", ""
    try:
        qs = parse_qs(urlparse(notice_url).query)
        hmno = qs.get("houseManageNo", [""])[0]
        pbno = qs.get("pblancNo", [""])[0]
        return hmno, pbno
    except Exception:
        return "", ""


# ── 청약홈 OpenAPI 호출 → is_hot_zone ─────────────────────────
def fetch_hot_zone_from_api(house_manage_no: str, pblanc_no: str) -> str:
    """
    청약홈 API 호출 → SPECLT_RDN_EARTH_AT 값 반환
    성공: "Y" / "N" / "해당없음" 중 하나
    실패: ""
    """
    if not PUBLIC_DATA_API_KEY or not house_manage_no:
        return ""
    try:
        resp = requests.get(
            APT_DETAIL_API,
            params={
                "serviceKey": PUBLIC_DATA_API_KEY,
                "houseManageNo": house_manage_no,
                "pblancNo": pblanc_no,
                "page": 1,
                "perPage": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        if items:
            return str(items[0].get("SPECLT_RDN_EARTH_AT", "") or "")
    except Exception as e:
        print(f"    [API] 오류: {e}")
    return ""


# ── regex: post.html Q&A 텍스트에서 is_hot_zone 추출 ──────────
def regex_hot_zone(html: str) -> str:
    """
    post.html 본문(Q&A, 입지 설명 등)에서 투기과열지구 여부 추론
    """
    # "해당하지 않" 패턴 (비해당)
    not_zone_patterns = [
        r"투기과열지구\s*(?:및|·)\s*청약과열지역에\s*해당하지\s*않",
        r"투기과열지구에\s*해당하지\s*않",
        r"비투기과열지구",
        r"비규제\s*지역",
        r"규제지역에\s*해당하지\s*않",
        r"투기과열지구로\s*지정(?:되어\s*있지\s*않|되지\s*않)",
    ]
    for pat in not_zone_patterns:
        if re.search(pat, html):
            return "N"

    # "해당" 패턴 (해당) — 위 비해당 패턴 이후에 체크
    zone_patterns = [
        r"투기과열지구로\s*지정",
        r"투기과열지구에\s*해당(?!하지)",
        r"투기과열지구\s*적용",
    ]
    for pat in zone_patterns:
        if re.search(pat, html):
            return "Y"

    return ""


# ── regex: 텍스트에서 전매제한 / 실거주의무 추출 ────────────────
_RESALE_PATTERNS = [
    r"소유권이전등기일로부터\s*(\d+년)",
    r"전매제한\s*기간\s*[：:]\s*([^\n,。<]{3,40})",
    r"전매제한\s*[：:]\s*([^\n,。<]{3,40})",
    r"입주\s*후\s*(\d+년\s*(?:이상\s*)?전매제한)",
    r"분양가상한제\s*적용\s*(\d+년)",
    r"전매\s*제한\s*없음",
    r"전매제한\s*없음",
]

_LIVE_PATTERNS = [
    r"거주\s*의무\s*기간\s*[：:]\s*([^\n,。<]{3,30})",
    r"실거주\s*의무\s*[：:]\s*([^\n,。<]{3,30})",
    r"실거주\s*의무\s*(\d+년\s*이상)",
    r"거주\s*의무\s*(\d+년\s*이상)",
    r"실거주\s*의무\s*(없음|해당\s*없음|비해당)",
    r"거주\s*의무\s*(없음|해당\s*없음)",
]


def regex_extract_resale(text: str) -> str:
    for pat in _RESALE_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return ""


def regex_extract_live_req(text: str) -> str:
    for pat in _LIVE_PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return ""


# ── PDF 다운로드 → 텍스트 추출 ─────────────────────────────────
def download_pdf_text(notice_url: str, max_chars: int = 8000) -> str:
    """
    notice_url에서 PDF 다운로드 후 pdfplumber로 텍스트 추출.
    실패 시 "" 반환.
    """
    try:
        import pdfplumber
    except ImportError:
        print("    [PDF] pdfplumber 미설치 → 건너뜀")
        return ""

    if not notice_url:
        return ""

    try:
        resp = requests.get(
            notice_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        if "pdf" not in resp.headers.get("content-type", "").lower() and len(resp.content) < 1000:
            print("    [PDF] PDF 응답 아님")
            return ""

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name

        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages[:15]:  # 최대 15페이지
                t = page.extract_text() or ""
                text_parts.append(t)
                if sum(len(x) for x in text_parts) > max_chars:
                    break

        Path(tmp_path).unlink(missing_ok=True)
        return "\n".join(text_parts)[:max_chars]

    except Exception as e:
        print(f"    [PDF] 다운로드/추출 오류: {e}")
        return ""


# ── Claude Haiku LLM 추출 ──────────────────────────────────────
async def llm_extract_policy(pdf_text: str) -> dict:
    """
    Claude Haiku로 공고문 텍스트에서 전매제한·실거주의무·투기과열 추출
    """
    if not ANTHROPIC_API_KEY or not pdf_text.strip():
        return {}

    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": POLICY_EXTRACT_PROMPT.format(
                    pdf_text=pdf_text[:6000]
                ),
            }],
        )
        raw = resp.content[0].text.strip()
        # JSON 파싱
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(m.group()) if m else {}

    except Exception as e:
        print(f"    [LLM] Claude 오류: {e}")
        return {}


# ── hot_zone 값 표시 포맷 ──────────────────────────────────────
def fmt_hot_zone(v: str) -> str:
    if v in ("Y", "y"):
        return "해당 (투기과열지구)"
    if v in ("N", "n", "해당없음", "아니오", "비해당"):
        return "비해당"
    return v


# ── HTML 정책 카드 패치 ────────────────────────────────────────
def patch_policy_card_html(
    html: str,
    hot_zone: str,
    live_req: str,
    resale: str,
) -> tuple[str, bool]:
    """
    청약 규제 정보 카드의 3개 항목 값 교체.
    반환: (patched_html, changed)
    """
    changed = False

    def replace_label_value(label: str, new_val: str) -> bool:
        """label 다음 value div의 텍스트를 new_val로 교체. 변경 여부 반환."""
        nonlocal html
        pat = re.compile(
            r'(<div[^>]*>\s*' + re.escape(label) + r'\s*</div>\s*'
            r'<div[^>]*>)([^<]*)(</div>)',
            re.DOTALL,
        )
        new_html = pat.sub(lambda m: m.group(1) + new_val + m.group(3), html, count=1)
        if new_html != html:
            html = new_html
            return True
        return False

    if hot_zone:
        if replace_label_value("투기과열지구", hot_zone):
            changed = True

    if live_req:
        if replace_label_value("실거주 의무", live_req):
            changed = True

    if resale:
        if replace_label_value("전매제한", resale):
            changed = True

        # 전매제한 안내 카드도 업데이트
        resale_alert_pat = re.compile(
            r'(전매제한 안내</div>\s*<div[^>]*>)(공고문을 통해[^<]*|공고문 확인 필요)(</div>)',
            re.DOTALL,
        )
        new_html = resale_alert_pat.sub(
            lambda m: m.group(1) + resale + m.group(3),
            html, count=1
        )
        if new_html != html:
            html = new_html
            changed = True

    return html, changed


# ── 포스트 단위 처리 ───────────────────────────────────────────
async def process_post(post_dir: Path, dry_run: bool = False) -> bool:
    meta_path = post_dir / "post_meta.json"
    html_path = post_dir / "post.html"

    if not meta_path.exists() or not html_path.exists():
        print("  ─ 파일 없음, 건너뜀")
        return False

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")
    notice_url = meta.get("notice_url", "")

    # ── 1. houseManageNo / pblancNo 파싱 ────────────────────
    hmno, pbno = parse_house_ids(notice_url)
    if hmno:
        print(f"  [ID] houseManageNo={hmno}, pblancNo={pbno}")

    # ── 2. is_hot_zone ───────────────────────────────────────
    hot_zone_raw = ""

    # 2a. API 우선
    if hmno:
        hot_zone_raw = fetch_hot_zone_from_api(hmno, pbno)
        if hot_zone_raw:
            print(f"  [API] SPECLT_RDN_EARTH_AT = {hot_zone_raw!r}")

    # 2b. Q&A 텍스트 regex 폴백
    if not hot_zone_raw:
        hot_zone_raw = regex_hot_zone(html)
        if hot_zone_raw:
            print(f"  [REGEX] 투기과열지구 = {hot_zone_raw!r}")

    hot_zone = fmt_hot_zone(hot_zone_raw) if hot_zone_raw else ""

    # ── 3. 전매제한 / 실거주의무: PDF → LLM → regex ──────────
    resale = ""
    live_req = ""

    # 3a. PDF 다운로드 → LLM 추출
    pdf_text = download_pdf_text(notice_url)
    if pdf_text:
        print(f"  [PDF] {len(pdf_text):,}자 추출 완료")
        llm_result = await llm_extract_policy(pdf_text)
        if llm_result:
            resale = llm_result.get("resale_restriction") or ""
            live_req = llm_result.get("live_requirement") or ""
            llm_hz = llm_result.get("is_hot_zone") or ""
            # LLM이 PDF에서 hot_zone도 추출했고 아직 없으면 사용
            if not hot_zone and llm_hz and llm_hz.lower() != "null":
                hot_zone = fmt_hot_zone(llm_hz)
            print(f"  [LLM] resale={resale!r}, live_req={live_req!r}, hot_zone={llm_hz!r}")

    # 3b. PDF regex 폴백
    if pdf_text:
        if not resale:
            resale = regex_extract_resale(pdf_text)
        if not live_req:
            live_req = regex_extract_live_req(pdf_text)

    # 3c. HTML Q&A regex 폴백
    if not resale:
        resale = regex_extract_resale(html)
    if not live_req:
        live_req = regex_extract_live_req(html)

    print(f"  [결과] hot_zone={hot_zone!r}, resale={resale!r}, live_req={live_req!r}")

    # 아무 값도 없으면 패치 불필요
    if not hot_zone and not resale and not live_req:
        print("  ─ 추출 데이터 없음, 패치 건너뜀")
        return False

    # ── 4. HTML 패치 ─────────────────────────────────────────
    new_html, html_changed = patch_policy_card_html(html, hot_zone, live_req, resale)

    if not html_changed:
        print("  ─ HTML 변경 없음")
        # 그래도 meta는 업데이트할 수 있음

    # ── 5. meta.json 업데이트 ────────────────────────────────
    meta_updated = False
    if hot_zone and meta.get("is_hot_zone") != hot_zone:
        meta["is_hot_zone"] = hot_zone
        meta_updated = True
    if resale and meta.get("resale_restriction") != resale:
        meta["resale_restriction"] = resale
        meta_updated = True
    if live_req and meta.get("live_requirement") != live_req:
        meta["live_requirement"] = live_req
        meta_updated = True

    if not html_changed and not meta_updated:
        print("  ─ 변경 없음")
        return False

    if not dry_run:
        if html_changed:
            html_path.write_text(new_html, encoding="utf-8")
        if meta_updated:
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        print(f"  ✅ {'HTML + meta' if html_changed and meta_updated else 'HTML' if html_changed else 'meta'} 저장 완료")
    else:
        print(f"  (dry-run) 저장 건너뜀")

    return True


# ── 메인 ──────────────────────────────────────────────────────
async def main():
    dry_run = "--dry-run" in sys.argv
    limit_arg = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--limit"), None)
    limit = int(limit_arg) if limit_arg else None

    if dry_run:
        print("=== DRY-RUN 모드 (파일 수정 없음) ===\n")

    posts = sorted(POSTS_DIR.glob("*/post.html"))
    if limit:
        posts = posts[:limit]

    print(f"총 {len(posts)}개 포스트 처리 시작\n")

    changed_count = 0
    for post_path in posts:
        post_dir = post_path.parent
        name = post_dir.name
        print(f"[{name}]")
        try:
            if await process_post(post_dir, dry_run=dry_run):
                changed_count += 1
        except Exception as e:
            print(f"  ❌ 오류: {e}")
        print()
        # API rate limit 배려
        time.sleep(0.3)

    print(f"완료: {changed_count}/{len(posts)}개 파일 변경{'(dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    asyncio.run(main())

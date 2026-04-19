"""
test_pipeline.py
────────────────────────────────────────────────────
파이프라인 전체 흐름을 단계별로 테스트합니다.
OpenAI API 키 없이도 이미지 수집 / HTML 렌더링까지 테스트 가능합니다.

실행:
    python test_pipeline.py           # 전체 테스트
    python test_pipeline.py --step 1  # 1단계만
────────────────────────────────────────────────────
"""

import sys
import asyncio
import json
from pathlib import Path

# 경로 설정
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import os
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")


def sep(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


# ──────────────────────────────────────────────────
# STEP 1: 수집기 테스트 (API 키 불필요)
# ──────────────────────────────────────────────────

def test_step1_collector():
    sep("STEP 1: 데이터 수집기 (샘플 공고)")
    from agents.collector import get_sample_document

    doc = get_sample_document()
    print(f"  ✅ 단지명    : {doc.apt_name}")
    print(f"  ✅ 지역      : {doc.region} {doc.district}")
    print(f"  ✅ 공급일    : {doc.supply_date}")
    print(f"  ✅ 텍스트    : {len(doc.raw_text):,}자")
    print(f"  ✅ 표 수     : {len(doc.tables)}개")
    print(f"\n  [RAG 텍스트 미리보기]")
    print("  " + doc.to_rag_text()[:300].replace("\n", "\n  "))
    return doc


# ──────────────────────────────────────────────────
# STEP 2: 이미지 수집 테스트 (API 키 선택)
# ──────────────────────────────────────────────────

async def test_step2_images():
    sep("STEP 2: 이미지 수집")
    from image_finder import find_images_for_post, ImageType

    output_dir = BASE_DIR / "output"
    images = await find_images_for_post("테스트단지", output_dir)

    print(f"\n  [이미지 결과]")
    for slot_name, img in images.items():
        if img.image_type == ImageType.PLACEHOLDER:
            print(f"  🖼️  {slot_name:20s} → 플레이스홀더 ({img.slot_label})")
        else:
            status = "✅ 로컬저장" if img.local_path else "🔗 URL만"
            print(f"  {status}  {slot_name:20s} → {img.url[:60]}...")

    return images


# ──────────────────────────────────────────────────
# STEP 3: HTML 렌더링 테스트 (API 키 불필요)
# ──────────────────────────────────────────────────

async def test_step3_html_render(images: dict):
    sep("STEP 3: HTML 렌더링 (샘플 데이터 → post.html)")
    from html_renderer import (
        BlogHTMLRenderer, PostData, QABlock, UnitType, save_post
    )
    from image_finder import ImageResult, ImageType

    # 샘플 PostData 조립
    unit_types = [
        UnitType("59A", 59.99, 120, 80, 75000, 82000),
        UnitType("84A", 84.97, 200, 130, 95000, 110000),
        UnitType("84B", 84.98, 180, 132, 97000, 112000),
    ]

    qa_blocks = [
        QABlock(
            question="계약금 10% 낸 후, 중도금 대출 가장 유리한 은행은 어디인가요?",
            answer=(
                "힐스테이트 판교역은 <strong>중도금 무이자 집단대출</strong>이 제공됩니다. "
                "분양가의 60%를 6회 분납하며 이자는 시행사 부담입니다. "
                "집단대출 지정 은행은 계약 후 공지되며, DSR 규제(40%) 적용 대상이므로 "
                "<strong>사전에 한도 조회</strong>를 권장합니다."
            ),
        ),
        QABlock(
            question="1순위 청약 자격, 내가 해당되는지 확인하는 방법은?",
            answer=(
                "1순위 자격은 ① 청약통장 가입 2년 이상 ② 지역 거주요건 ③ 무주택 세대구성원 충족이 기본입니다. "
                "판교는 <strong>비투기과열지구</strong>로 조건이 완화되어 있으며, "
                "가점제 40% · 추첨제 60%로 가점이 낮은 30~40대도 기회가 있습니다."
            ),
        ),
        QABlock(
            question="이 단지 발코니 확장하면 얼마? 기본 인테리어 비용 비교",
            answer=(
                "84타입 발코니 확장 비용은 통상 <strong>500~700만원</strong> 수준입니다. "
                "계약 시 옵션 신청 시 입주 후 직접 시공 대비 30~40% 저렴합니다. "
                "도배·바닥재·조명 등 기본 인테리어는 84타입 기준 평균 <strong>1,500~2,500만원</strong> 소요됩니다."
            ),
        ),
    ]

    post_data = PostData(
        apt_name="힐스테이트 판교역 (샘플)",
        post_title="힐스테이트 판교역 청약 완벽 분석 | 중도금 무이자, 3가지 핵심 정보",
        post_subtitle="판교 신분당선 역세권 842세대, 청약 전 반드시 확인하세요",
        location="경기 성남시 분당구",
        supply_location="경기도 성남시 분당구 삼평동 123",
        supply_scale="지하 3층~지상 35층 / 5개동 / 842세대",
        price_range="7억 5천만 ~ 11억 2천만원",
        unit_types=unit_types,
        special_supply_date="2026.04.25",
        rank1_date="2026.04.28",
        rank2_date="2026.04.29",
        winner_date="2026.05.08",
        move_in_date="2028년 12월",
        loan_info="중도금 무이자 집단대출 (분양가의 60%)",
        resale_restriction="전매제한 3년",
        contract_ratio="10",
        contract_amount="7,500만 ~ 1억 1,200만원",
        midterm_ratio="60",
        midterm_count="6",
        balance_ratio="30",
        acquisition_tax_rate="1% (1주택, 취득가 6억 이하)",
        acquisition_tax_amount="약 950만 ~ 1,120만원",
        property_tax_rate="과세표준 × 0.1~0.4%",
        property_tax_amount="연 약 70~140만원 (추정)",
        capital_gains_tax_rate="1주택 2년 보유·거주 시 비과세 가능",
        capital_gains_tax_amount="비과세 요건 충족 시 0원",
        subway_score="★★★★★",
        subway_detail="신분당선 판교역 도보 5분",
        school_score="★★★★☆",
        school_detail="판교초 배정, 분당중·고 인근",
        life_score="★★★★☆",
        life_detail="현대백화점 판교점 도보 10분",
        medical_score="★★★☆☆",
        medical_detail="분당서울대병원 차량 10분",
        qa_blocks=qa_blocks,
        # 내러티브 산문 (샘플)
        apt_intro=(
            "안녕하세요! 오늘은 판교 한복판, 신분당선 바로 앞에 들어서는 "
            "<strong>힐스테이트 판교역</strong> 분양 정보를 꼼꼼하게 정리해드리려고 해요. "
            "842세대 대단지에 중도금 무이자까지, 실수요자라면 꼭 체크해보세요."
        ),
        location_intro=(
            "판교는 이제 강남 못지않은 생활 인프라를 자랑하는 지역이죠. "
            "테크노밸리 직장인들의 수요도 탄탄하고, 현대백화점·분당서울대병원도 가까워 "
            "4인 가족 실거주지로도 손색이 없는 입지입니다."
        ),
        financial_intro=(
            "청약 당첨만큼 중요한 게 바로 자금 준비인데요. "
            "계약금부터 잔금까지 언제 얼마가 필요한지 미리 파악해두면 훨씬 여유 있게 준비할 수 있어요."
        ),
        qa_intro=(
            "청약 준비하시면서 가장 많이 받는 질문들을 솔직하게 답해드릴게요. "
            "궁금하신 점이 있으면 댓글로 남겨주세요!"
        ),
        # 정보 블록 앞 서술 텍스트
        schedule_desc=(
            "특별공급부터 당첨자 발표까지 모든 일정을 한눈에 정리했어요. "
            "<strong>1순위 청약은 2026년 4월 28일</strong>이니 지금 바로 캘린더에 표시해두세요!"
        ),
        unit_type_desc=(
            "힐스테이트 판교역은 <strong>59㎡·84㎡ 두 가지 타입</strong>으로 구성돼요. "
            "실수요 중심의 중소형으로, 특히 84A·84B 타입이 물량의 절반 이상을 차지합니다."
        ),
        tax_desc=(
            "분양가가 7억을 넘는 만큼 취득세부터 미리 계산해두는 게 좋아요. "
            "입주 시점, 보유 기간, 매도 시점별로 내야 할 세금을 표로 정리했습니다."
        ),
        seo_tags=["힐스테이트판교역", "판교청약", "성남분양", "경기아파트청약", "판교역세권", "중도금무이자"],
        images=images,
        source_date="2026-04-15",
        read_time=8,
        theme="claude",
    )

    renderer = BlogHTMLRenderer()
    html = renderer.render(post_data)
    saved_path = save_post(post_data, html, BASE_DIR / "output")

    print(f"\n  ✅ HTML 길이  : {len(html):,}자")
    print(f"  ✅ 저장 경로  : {saved_path}")

    # 브라우저 미리보기용 경로
    html_file = saved_path / "post.html"
    print(f"\n  💡 미리보기: 아래 경로를 브라우저에서 열어보세요")
    print(f"     {html_file}")
    return saved_path


# ──────────────────────────────────────────────────
# STEP 4: OpenAI 연결 확인 (API 키 필요)
# ──────────────────────────────────────────────────

async def test_step4_openai():
    sep("STEP 4: OpenAI API 연결 확인")
    if not OPENAI_KEY or "여기에" in OPENAI_KEY:
        print("  ⏭️  OPENAI_API_KEY 미설정 → 건너뜀")
        print("     .env 파일에 실제 키를 입력하면 전체 파이프라인이 동작합니다.")
        return False

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_KEY)
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "respond with 'ok' only"}],
            max_tokens=5,
        )
        print(f"  ✅ OpenAI 연결 성공: {resp.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"  ❌ OpenAI 연결 실패: {e}")
        return False


# ──────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────

async def main():
    step = None
    if "--step" in sys.argv:
        idx = sys.argv.index("--step")
        step = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else None

    print("\n🏗️  PROJECT BALI - 파이프라인 테스트")
    print(f"   OpenAI  : {'✅ 설정됨' if OPENAI_KEY and '여기에' not in OPENAI_KEY else '⚠️  미설정'}")
    print(f"   Unsplash: {'✅ 설정됨' if UNSPLASH_KEY and '여기에' not in UNSPLASH_KEY else '⚠️  미설정 (기본이미지 사용)'}")

    doc    = None
    images = {}

    if step is None or step == 1:
        doc = test_step1_collector()

    if step is None or step == 2:
        images = await test_step2_images()

    if step is None or step == 3:
        if not images:
            images = await test_step2_images()
        await test_step3_html_render(images)

    if step is None or step == 4:
        await test_step4_openai()

    if step == 5:
        await test_step5_full_llm()

    if step == 6:
        await test_step6_rag()

    print("\n\n✅ 테스트 완료!")


# ──────────────────────────────────────────────────
# STEP 5: 실제 LLM 전체 파이프라인 (API 키 필요)
# ──────────────────────────────────────────────────

async def test_step5_full_llm():
    sep("STEP 5: 전체 LLM 파이프라인 (팩트추출 → 콘텐츠생성 → HTML)")

    if not OPENAI_KEY or "여기에" in OPENAI_KEY:
        print("  ⏭️  OPENAI_API_KEY 미설정 → 건너뜀")
        return

    from agents.collector import get_sample_document
    from orchestrator import run_pipeline

    doc = get_sample_document()
    print(f"  공고문: {doc.apt_name} ({len(doc.to_rag_text())}자)")
    print("  LLM 처리 중... (약 30~60초 소요)")

    result_path = await run_pipeline(doc.to_rag_text())

    if result_path:
        html_path = result_path / "post.html"
        print(f"\n  ✅ 완료: {result_path}")
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", str(html_path)])
    else:
        print("  ❌ 파이프라인 실패")


# ──────────────────────────────────────────────────
# STEP 6: RAG 연동 전체 파이프라인 (ChromaDB + OpenAI)
# ──────────────────────────────────────────────────

async def test_step6_rag():
    sep("STEP 6: RAG 연동 파이프라인 (NoticeDocument → RAG → 포스팅)")

    if not OPENAI_KEY or "여기에" in OPENAI_KEY:
        print("  ⏭️  OPENAI_API_KEY 미설정 → 건너뜀")
        return

    from agents.collector import get_sample_document
    from orchestrator import run_pipeline_from_doc

    doc = get_sample_document()
    print(f"  공고문: {doc.apt_name}")
    print(f"  RAG 청크 분할 + ChromaDB 저장 후 컨텍스트 조합 → LLM 처리")
    print("  (약 30~60초 소요)")

    result_path = await run_pipeline_from_doc(doc)

    if result_path:
        html_path = result_path / "post.html"
        print(f"\n  ✅ 완료: {result_path}")
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", str(html_path)])
    else:
        print("  ❌ 파이프라인 실패")


if __name__ == "__main__":
    asyncio.run(main())

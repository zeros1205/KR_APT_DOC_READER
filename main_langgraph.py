"""
main_langgraph.py
────────────────────────────────────────────────────
LangGraph 기반 통합 파이프라인 엔트리포인트

핵심 목적:
  - TypedDict 상태로 공고 수집/검증/생성/렌더링을 명시화
  - Validation 실패 시 Context Recovery 루프로 복귀
  - Quality Gate 실패 시 콘텐츠 재생성 루프로 복귀
  - 최종 결과는 기존 HTML 렌더링 산출물과 호환 유지
────────────────────────────────────────────────────
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
    _HAS_LANGGRAPH = True
except ModuleNotFoundError:  # pragma: no cover - runtime fallback
    END = "__end__"
    START = "__start__"
    StateGraph = None  # type: ignore[assignment]
    _HAS_LANGGRAPH = False

from pipeline.config import BLOG_THEME, MIN_QUALITY_SCORE, OUTPUT_DIR, OPENAI_API_KEY
from pipeline.html_renderer import BlogHTMLRenderer, PostData, build_post_data, save_post
from pipeline.agents.collector import NoticeDocument
from pipeline.agents.pdf_policy import extract_policy_from_pdf_text
from pipeline.orchestrator import (
    _derive_price_range,
    _fallback_content_generation,
    _fallback_location_analysis,
    _select_theme,
    agent_content_generation,
    agent_fact_extraction,
    agent_factcheck_qa,
    agent_location_analysis_gemini,
    agent_location_verify_gemini,
    agent_quality_check,
)

_LOCATION_KEYS = (
    "location_intro",
    "subway_score",
    "subway_detail",
    "school_score",
    "school_detail",
    "life_score",
    "life_detail",
    "medical_score",
    "medical_detail",
)


class PipelineState(TypedDict, total=False):
    doc: NoticeDocument
    notice_text: str
    pdf_policy_text: str
    facts: dict[str, Any]
    content: dict[str, Any]
    location_data: dict[str, Any]
    post_data: PostData
    saved_path: str
    score: int
    issues: list[str]
    validation_missing: list[str]
    needs_recovery: bool
    needs_quality_retry: bool
    recovery_round: int
    quality_round: int
    max_retries: int
    min_quality_score: int
    theme: str
    supply_type: str
    notice_url: str
    api_is_hot_zone: str
    error: str


def _merge_pdf_policy(facts: dict[str, Any], pdf_policy_text: str) -> dict[str, Any]:
    """PDF 원문에서 추출한 규제 정보를 사실 추출 결과에 덮어쓴다."""
    if not pdf_policy_text.strip():
        return facts

    policy = extract_policy_from_pdf_text(pdf_policy_text)
    if not policy:
        return facts

    merged = dict(facts)
    for key in (
        "regulated_zone",
        "readmission_limit",
        "resale_restriction",
        "live_requirement",
        "price_cap",
        "land_type",
        "is_hot_zone",
    ):
        value = policy.get(key)
        if value not in (None, "", [], "공고문 확인 필요"):
            merged[key] = value
    return merged


def _required_fact_keys() -> tuple[str, ...]:
    return ("apt_name", "rank1_date", "price_range", "unit_types")


async def initialize_context(state: PipelineState) -> dict[str, Any]:
    """RAG 또는 원문 폴백으로 notice_text를 준비한다."""
    doc = state.get("doc")
    notice_text = (state.get("notice_text") or "").strip()
    if notice_text:
        return {
            "notice_text": notice_text,
            "theme": state.get("theme") or _select_theme(doc.supply_type if doc else ""),
            "supply_type": state.get("supply_type") or (doc.supply_type if doc else ""),
            "notice_url": state.get("notice_url") or (doc.notice_url if doc else ""),
            "api_is_hot_zone": state.get("api_is_hot_zone") or (doc.is_hot_zone if doc else ""),
            "max_retries": state.get("max_retries", 2),
            "min_quality_score": state.get("min_quality_score", MIN_QUALITY_SCORE),
        }

    if doc is None:
        return {
            "notice_text": "",
            "error": "공고 문서가 없습니다.",
            "max_retries": state.get("max_retries", 2),
            "min_quality_score": state.get("min_quality_score", MIN_QUALITY_SCORE),
        }

    try:
        from pipeline.agents.rag_store import ApartmentRAGStore

        store = ApartmentRAGStore()
        store.add_notice(doc)
        notice_text = store.get_full_context(doc.notice_id)
        if not notice_text.strip():
            raise ValueError("RAG 컨텍스트 비어 있음")
    except Exception as e:
        notice_text = doc.to_rag_text()
        print(f"  [Graph] RAG 초기화 실패 → 원문 폴백: {e}")

    return {
        "notice_text": notice_text,
        "theme": state.get("theme") or _select_theme(doc.supply_type),
        "supply_type": state.get("supply_type") or doc.supply_type,
        "notice_url": state.get("notice_url") or doc.notice_url,
        "api_is_hot_zone": state.get("api_is_hot_zone") or doc.is_hot_zone,
        "max_retries": state.get("max_retries", 2),
        "min_quality_score": state.get("min_quality_score", MIN_QUALITY_SCORE),
    }


async def extract_facts_node(state: PipelineState) -> dict[str, Any]:
    """공고문에서 사실 데이터를 추출한다."""
    notice_text = state.get("notice_text", "")
    doc = state.get("doc")
    facts = await agent_fact_extraction(notice_text)
    facts = _merge_pdf_policy(facts, state.get("pdf_policy_text") or (doc.pdf_policy_text if doc else ""))

    if not facts.get("apt_name") and doc and doc.apt_name:
        facts["apt_name"] = doc.apt_name

    if facts.get("unit_types"):
        facts["price_range"] = _derive_price_range(facts["unit_types"]) or facts.get("price_range", "")
        facts["supply_total_units"] = sum(
            int(ut.get("general_units", 0) or 0) + int(ut.get("special_units", 0) or 0)
            for ut in facts["unit_types"]
        )
    return {"facts": facts, "error": ""}


def validate_facts_node(state: PipelineState) -> dict[str, Any]:
    """필수 데이터 누락 여부를 검사한다."""
    facts = state.get("facts") or {}
    missing = [key for key in _required_fact_keys() if not facts.get(key)]
    needs_recovery = bool(missing and state.get("recovery_round", 0) < 1)
    return {
        "validation_missing": missing,
        "needs_recovery": needs_recovery,
    }


async def recover_context_node(state: PipelineState) -> dict[str, Any]:
    """검증 실패 시 문맥을 보정해 재추출한다."""
    doc = state.get("doc")
    if not doc:
        return {"needs_recovery": False}

    recovery_round = state.get("recovery_round", 0) + 1
    notice_text = doc.to_rag_text()
    if doc.pdf_policy_text:
        notice_text = f"{notice_text}\n\n[PDF 원문]\n{doc.pdf_policy_text}"

    print(f"  [Graph] Context recovery #{recovery_round}")
    return {
        "notice_text": notice_text,
        "recovery_round": recovery_round,
        "needs_recovery": False,
    }


async def analyze_location_node(state: PipelineState) -> dict[str, Any]:
    facts = state.get("facts") or {}
    if not facts:
        return {"location_data": {}}

    location_data = await agent_location_analysis_gemini(facts)
    if not location_data:
        location_data = _fallback_location_analysis(facts, state.get("notice_text") or "")
    location_data = await agent_location_verify_gemini(location_data, facts)
    return {"location_data": location_data}


async def generate_content_node(state: PipelineState) -> dict[str, Any]:
    facts = state.get("facts") or {}
    location_data = state.get("location_data") or {}
    if not OPENAI_API_KEY.strip():
        content = _fallback_content_generation(facts, location_data)
    else:
        content = await agent_content_generation(facts)
    if location_data:
        content.update({k: location_data[k] for k in _LOCATION_KEYS if location_data.get(k)})
    return {"content": content}


async def factcheck_content_node(state: PipelineState) -> dict[str, Any]:
    content = state.get("content") or {}
    facts = state.get("facts") or {}
    content = await agent_factcheck_qa(content, facts)
    return {"content": content}


async def quality_gate_node(state: PipelineState) -> dict[str, Any]:
    content = state.get("content") or {}
    facts = state.get("facts") or {}
    score, issues = await agent_quality_check(content, facts)

    quality_round = state.get("quality_round", 0)
    max_retries = state.get("max_retries", 2)
    needs_retry = score < state.get("min_quality_score", MIN_QUALITY_SCORE) and quality_round < max_retries

    if needs_retry:
        print(f"  [Graph] quality retry #{quality_round + 1} queued")
        quality_round += 1

    return {
        "score": score,
        "issues": issues,
        "needs_quality_retry": needs_retry,
        "quality_round": quality_round,
    }


def _score_to_default(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) and value else default


def assemble_post_data_node(state: PipelineState) -> dict[str, Any]:
    """최종 렌더링용 PostData를 조립한다."""
    facts = state.get("facts") or {}
    content = state.get("content") or {}
    doc = state.get("doc")
    post_data = build_post_data(
        facts=facts,
        content=content,
        doc=doc,
        theme=state.get("theme") or BLOG_THEME,
        supply_type=state.get("supply_type") or (doc.supply_type if doc else ""),
        notice_url=state.get("notice_url") or (doc.notice_url if doc else ""),
        api_is_hot_zone=state.get("api_is_hot_zone") or (doc.is_hot_zone if doc else ""),
    )
    return {"post_data": post_data}


def render_and_save_node(state: PipelineState) -> dict[str, Any]:
    post_data = state.get("post_data")
    if not post_data:
        return {"error": "post_data가 없습니다."}

    print("\n  🎨 HTML 렌더링...")
    renderer = BlogHTMLRenderer()
    html = renderer.render(post_data)
    saved_path = save_post(post_data, html, OUTPUT_DIR)
    return {"saved_path": str(saved_path)}


def route_after_validation(state: PipelineState) -> str:
    return "recover_context" if state.get("needs_recovery") else "analyze_location"


def route_after_quality(state: PipelineState) -> str:
    return "generate_content" if state.get("needs_quality_retry") else "assemble_post_data"


def build_graph() -> Any:
    """LangGraph 그래프를 생성하고 컴파일한다."""
    if not _HAS_LANGGRAPH:
        class _FallbackGraph:
            async def ainvoke(self, state: PipelineState) -> dict[str, Any]:
                current: dict[str, Any] = dict(state)
                current.update(await initialize_context(current))
                while True:
                    current.update(await extract_facts_node(current))
                    current.update(validate_facts_node(current))
                    if current.get("needs_recovery"):
                        current.update(await recover_context_node(current))
                        continue
                    current.update(await analyze_location_node(current))
                    while True:
                        current.update(await generate_content_node(current))
                        current.update(await factcheck_content_node(current))
                        current.update(await quality_gate_node(current))
                        if current.get("needs_quality_retry"):
                            continue
                        break
                    current.update(assemble_post_data_node(current))
                    current.update(render_and_save_node(current))
                    return current

        print("  [Graph] langgraph 미설치 → 순차 실행 폴백 사용")
        return _FallbackGraph()

    graph = StateGraph(PipelineState)
    graph.add_node("initialize_context", initialize_context)
    graph.add_node("extract_facts", extract_facts_node)
    graph.add_node("validate_facts", validate_facts_node)
    graph.add_node("recover_context", recover_context_node)
    graph.add_node("analyze_location", analyze_location_node)
    graph.add_node("generate_content", generate_content_node)
    graph.add_node("factcheck_content", factcheck_content_node)
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("assemble_post_data", assemble_post_data_node)
    graph.add_node("render_and_save", render_and_save_node)

    graph.add_edge(START, "initialize_context")
    graph.add_edge("initialize_context", "extract_facts")
    graph.add_edge("extract_facts", "validate_facts")
    graph.add_conditional_edges(
        "validate_facts",
        route_after_validation,
        {
            "recover_context": "recover_context",
            "analyze_location": "analyze_location",
        },
    )
    graph.add_edge("recover_context", "extract_facts")
    graph.add_edge("analyze_location", "generate_content")
    graph.add_edge("generate_content", "factcheck_content")
    graph.add_edge("factcheck_content", "quality_gate")
    graph.add_conditional_edges(
        "quality_gate",
        route_after_quality,
        {
            "generate_content": "generate_content",
            "assemble_post_data": "assemble_post_data",
        },
    )
    graph.add_edge("assemble_post_data", "render_and_save")
    graph.add_edge("render_and_save", END)
    return graph.compile()


GRAPH = build_graph()


async def run_pipeline_from_doc(doc: NoticeDocument, max_retries: int = 2) -> Path | None:
    """NoticeDocument를 LangGraph 파이프라인에 넣어 실행한다."""
    theme = _select_theme(doc.supply_type)
    state: PipelineState = {
        "doc": doc,
        "theme": theme,
        "supply_type": doc.supply_type,
        "notice_url": doc.notice_url,
        "api_is_hot_zone": doc.is_hot_zone,
        "pdf_policy_text": doc.pdf_policy_text,
        "max_retries": max_retries,
        "min_quality_score": MIN_QUALITY_SCORE,
        "recovery_round": 0,
        "quality_round": 0,
    }
    print(
        f"\n  [LangGraph] '{doc.apt_name}' 공고 처리 시작... "
        f"(공급유형: {doc.supply_type or '신규'} → 테마: {theme})"
    )
    result = await GRAPH.ainvoke(state)
    saved = result.get("saved_path")
    return Path(saved) if saved else None


async def run_pipeline(
    notice_text: str,
    max_retries: int = 2,
    theme: str = "",
    supply_type: str = "",
    notice_url: str = "",
    api_is_hot_zone: str = "",
    *,
    doc: NoticeDocument | None = None,
    pdf_policy_text: str = "",
) -> Path | None:
    """notice_text 기반 legacy 진입점."""
    if doc is None:
        return None

    state: PipelineState = {
        "doc": doc,
        "notice_text": notice_text,
        "theme": theme or _select_theme(supply_type or doc.supply_type),
        "supply_type": supply_type or doc.supply_type,
        "notice_url": notice_url or doc.notice_url,
        "api_is_hot_zone": api_is_hot_zone or doc.is_hot_zone,
        "pdf_policy_text": pdf_policy_text or doc.pdf_policy_text,
        "max_retries": max_retries,
        "min_quality_score": MIN_QUALITY_SCORE,
        "recovery_round": 0,
        "quality_round": 0,
    }
    result = await GRAPH.ainvoke(state)
    saved = result.get("saved_path")
    return Path(saved) if saved else None


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="LangGraph 기반 청약 공고 파이프라인")
    parser.add_argument("notice_txt", nargs="?", help="공고문 텍스트 파일 경로")
    args = parser.parse_args()

    if not args.notice_txt:
        raise SystemExit("사용법: python main_langgraph.py <공고문.txt>")

    path = Path(args.notice_txt)
    if not path.exists():
        raise SystemExit(f"파일 없음: {path}")

    async def _main() -> None:
        text = path.read_text(encoding="utf-8")
        # legacy run_pipeline를 직접 실행할 때는 doc가 있어야 하므로 안내만 출력
        print("main_langgraph.py는 run.py 또는 run_pipeline_from_doc 경로를 통해 사용하는 것을 권장합니다.")
        print(f"입력 텍스트 길이: {len(text):,}자")

    asyncio.run(_main())

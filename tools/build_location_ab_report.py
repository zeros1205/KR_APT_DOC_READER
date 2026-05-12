"""build_location_ab_report.py — A/B 결과 JSON 을 비교 MD 문서로 변환.

`tools/run_location_ab.py` 가 만든 `seo_audit/location_ab/<date>/ab_results.json`
을 읽어 운영자가 한눈에 v1 vs v2 차이를 확인 가능한 MD 리포트를 생성한다.

리포트 구성
  1. 요약 표 (단지 × cliche·구체·글자수 v1 vs v2)
  2. 단지별 본문 나란히 (v1 / v2 / metrics·primary_axes)
  3. 5-gram 일치율 (단지 간 유사도) v1 그룹 / v2 그룹

사용
  python tools/build_location_ab_report.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "seo_audit" / "location_ab"

sys.path.insert(0, str(ROOT / "tools"))
from measure_location_diversity import shingles, jaccard  # noqa: E402


def _latest_run() -> Path | None:
    if not AUDIT_DIR.exists():
        return None
    runs = sorted([d for d in AUDIT_DIR.iterdir() if d.is_dir()])
    return runs[-1] if runs else None


def _format_metrics(m: dict) -> str:
    if not m:
        return "—"
    return (
        f"{m.get('chars', 0)}자 · cliche {m.get('cliche', 0)} · "
        f"구체 {m.get('specific', 0)} (밀도 {m.get('specific_density_per_1000', 0)}/1000)"
    )


def _v2_body_markdown(result: dict) -> str:
    if not result or result.get("_error"):
        return f"_v2 결과 없음 ({result.get('_error', 'unknown')})_"
    intro = result.get("location_intro") or ""
    axes = result.get("primary_axes") or []
    subway = re.sub(r"<[^>]+>", "  \n  - ", result.get("subway_detail", "") or "")
    school = re.sub(r"<[^>]+>", "  \n  - ", result.get("school_detail", "") or "")
    feature = re.sub(r"<[^>]+>", "  \n  - ", result.get("feature_detail", "") or "")
    axes_str = ", ".join(axes) if axes else "—"
    return (
        f"**강조 축**: {axes_str}\n\n"
        f"**도입부**: {intro}\n\n"
        f"**교통·입지**: {subway}\n\n"
        f"**교육·주거**: {school}\n\n"
        f"**단지 특징**: {feature}\n"
    )


def build_report(run_dir: Path) -> str:
    data = json.loads((run_dir / "ab_results.json").read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append(f"# 입지 분석 A/B 결과 — {run_dir.name}")
    lines.append("")
    lines.append("**비교 대상**: v1 = production post.html 본문 / v2 = `pipeline.agents.location_v2` 결과")
    lines.append("")
    lines.append("## 1. 요약 (정량 지표)")
    lines.append("")
    lines.append("| 단지 | 글자수 v1→v2 | cliche v1→v2 | 구체 정보 v1→v2 | 강조 축 (v2) |")
    lines.append("|---|---:|---:|---:|---|")

    v1_texts: list[str] = []
    v2_texts: list[str] = []
    for nid, rec in data.items():
        v1m = rec["v1"]["metrics"]
        v2m = rec["v2"]["metrics"]
        v2r = rec["v2"]["result"]
        axes = ", ".join(v2r.get("primary_axes", [])) if isinstance(v2r, dict) else "—"
        v1_chars = v1m.get("chars", 0)
        v2_chars = v2m.get("chars", 0) or "—"
        v1_cliche = v1m.get("cliche", 0)
        v2_cliche = v2m.get("cliche", "—") if v2m else "—"
        v1_spec = v1m.get("specific", 0)
        v2_spec = v2m.get("specific", "—") if v2m else "—"
        lines.append(
            f"| {nid} | {v1_chars} → {v2_chars} | {v1_cliche} → {v2_cliche} | "
            f"{v1_spec} → {v2_spec} | {axes or '—'} |"
        )
        if rec["v1"]["text"]:
            v1_texts.append(rec["v1"]["text"])
        if rec["v2"]["text"]:
            v2_texts.append(rec["v2"]["text"])

    # 5-gram 일치율 — 단지 간 형식화 정도
    lines.append("")
    lines.append("## 2. 단지 간 5-gram Jaccard 평균 (낮을수록 다양함)")
    lines.append("")

    def _avg_pair(texts: list[str]) -> float:
        if len(texts) < 2:
            return 0.0
        sh = [shingles(t) for t in texts]
        pairs = [
            jaccard(sh[i], sh[j])
            for i in range(len(sh)) for j in range(i + 1, len(sh))
        ]
        return sum(pairs) / max(len(pairs), 1)

    v1_avg = _avg_pair(v1_texts) * 100
    v2_avg = _avg_pair(v2_texts) * 100
    lines.append(f"| 버전 | 평균 일치율 |")
    lines.append(f"|---|---:|")
    lines.append(f"| v1 (production) | **{v1_avg:.1f}%** |")
    lines.append(f"| v2 (experiment) | **{v2_avg:.1f}%** |")
    lines.append("")
    lines.append("## 3. 단지별 본문 (v1 / v2)")

    for nid, rec in data.items():
        lines.append("")
        lines.append(f"### {nid}")
        lines.append("")
        lines.append("#### v1 (production)")
        lines.append("")
        v1t = rec["v1"]["text"] or "_본문 추출 실패_"
        lines.append(v1t)
        lines.append("")
        lines.append(f"_metrics: {_format_metrics(rec['v1']['metrics'])}_")
        lines.append("")
        lines.append("#### v2 (experiment)")
        lines.append("")
        lines.append(_v2_body_markdown(rec["v2"]["result"]))
        lines.append("")
        lines.append(f"_metrics: {_format_metrics(rec['v2']['metrics'])}_")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="", help="대상 폴더 (없으면 최신)")
    args = parser.parse_args()

    if args.date:
        run_dir = AUDIT_DIR / args.date
    else:
        run_dir = _latest_run()

    if not run_dir or not run_dir.exists():
        print(f"❌ 결과 폴더 없음: {AUDIT_DIR}", file=sys.stderr)
        return 1

    report = build_report(run_dir)
    out_path = run_dir / "ab_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ 비교 리포트 생성: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

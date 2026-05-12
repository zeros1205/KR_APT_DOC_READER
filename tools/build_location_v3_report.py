"""build_location_v3_report.py — v3 (단지명·주소만, Gemini 추천 프롬프트) 리포트.

`seo_audit/location_v3/<date>/results.json` 을 읽어 단지별 본문 + 정량 지표를
markdown 으로 정리. v1/v2 비교는 없음 (v3 단독 실험).

사용
  python tools/build_location_v3_report.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "seo_audit" / "location_v3"


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


def build_report(run_dir: Path) -> str:
    data = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))

    lines: list[str] = [
        f"# 입지 분석 v3 단독 실험 — {run_dir.name}",
        "",
        "**입력**: 단지명 + 주소 두 줄만. **프롬프트**: Gemini 추천 마스터 프롬프트 (Role / Strategy / Tone / 5섹션 구조)",
        "**LLM 옵션**: gemini-3.1-pro-preview · Grounding(Google Search) · thinking_level=high · temperature 0.4",
        "**안전장치**: cliche·회피·'대장' 어휘 금지",
        "",
        "## 1. 요약",
        "",
        "| 단지 | 입력(apt/주소) | 글자수 | cliche | 구체 정보 | grounding/thinking |",
        "|---|---|---:|---:|---:|---|",
    ]
    for nid, rec in data.items():
        result = rec.get("result") or {}
        meta = (result.get("_meta") or {}) if isinstance(result, dict) else {}
        input_info = meta.get("input") or {}
        m = rec.get("metrics") or {}
        g = meta.get("grounding")
        t = meta.get("thinking")
        lines.append(
            f"| {nid} | {input_info.get('apt_name', '?')} / {input_info.get('address', '?')} | "
            f"{m.get('chars', 0)} | {m.get('cliche', 0)} | {m.get('specific', 0)} | "
            f"{g}/{t} |"
        )

    lines.append("")
    lines.append("## 2. 단지별 본문")
    for nid, rec in data.items():
        result = rec.get("result") or {}
        lines.append("")
        lines.append(f"### {nid}")
        lines.append("")
        if isinstance(result, dict) and result.get("_error"):
            lines.append(f"_v3 오류: {result['_error']}_")
            continue
        headline = result.get("headline") if isinstance(result, dict) else ""
        body_md = result.get("body_md", "") if isinstance(result, dict) else ""
        grounded = result.get("grounded_facts_used") or []
        if headline:
            lines.append(f"**핵심 결론**: {headline}")
            lines.append("")
        lines.append(body_md or "_본문 없음_")
        lines.append("")
        if grounded:
            lines.append("**인용된 외부 사실**:")
            for g in grounded:
                lines.append(f"- {g}")
            lines.append("")
        lines.append(f"_metrics: {_format_metrics(rec.get('metrics') or {})}_")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="")
    args = parser.parse_args()

    run_dir = AUDIT_DIR / args.date if args.date else _latest_run()
    if not run_dir or not run_dir.exists():
        print(f"❌ 결과 폴더 없음: {AUDIT_DIR}", file=sys.stderr)
        return 1

    report = build_report(run_dir)
    out_path = run_dir / "report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ v3 리포트: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

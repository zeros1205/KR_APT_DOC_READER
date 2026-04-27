from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from pipeline.agents.pdf_finance import extract_finance_from_pdf
from pipeline.index_renderer import build_front_index


POSTS_DIR = ROOT / "output" / "posts"
PDF_DIR = ROOT / "output" / "pdfs"
CACHE_DIR = ROOT / "output" / "data_cache" / "notices"
PROCESSED_FILE = ROOT / "output" / "processed_notices.json"
DOWNLOAD_LIST = ROOT / "PDF_DOWNLOAD_LIST.md"
REPORT = ROOT / "PDF_FINANCE_EXTRACTION_REPORT.md"

CONTRACT = "계약금"
MIDTERM = "중도금"
BALANCE = "잔금"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def notice_id_from_meta(meta: dict) -> str:
    for key in ("notice_id", "pblanc_no"):
        if meta.get(key):
            return str(meta[key])
    url = str(meta.get("notice_url") or "")
    for pattern in (r"pblancNo=(\d+)", r"PBLANC_NO=(\d+)", r"houseManageNo=(\d+)"):
        match = re.search(pattern, url, re.I)
        if match:
            return match.group(1)
    return ""


def label_ratio(pattern_label: str, ratio: str) -> tuple[str, str]:
    return re.escape(pattern_label) + r"\s*\d+%", f"{pattern_label} {ratio}%"


def patch_finance_html(html: str, finance: dict[str, object]) -> str:
    contract = str(finance["contract_ratio"])
    midterm = str(finance["midterm_ratio"])
    balance = str(finance["balance_ratio"])
    count = str(finance.get("midterm_count") or "").strip()
    midterm_title = f"{MIDTERM} — {midterm}% ({count}회 분납)" if count else f"{MIDTERM} — {midterm}%"
    qa_ratio = f"{CONTRACT} {contract}%, {MIDTERM} {midterm}%"
    if count:
        qa_ratio += f"({count}회)"
    qa_ratio += f", {BALANCE} {balance}%"

    start = html.find("SECTION 5")
    end = html.find("SECTION 6", start if start >= 0 else 0)
    if start >= 0 and end >= 0:
        prefix, section, suffix = html[:start], html[start:end], html[end:]
    else:
        prefix, section, suffix = "", html, ""

    section = re.sub(
        r"(background:\s*#B83C1E;[\s\S]*?width:\s*)\d+%([\s\S]*?\">\s*)\d+%(</div>)",
        rf"\g<1>{contract}%\g<2>{contract}%\g<3>",
        section,
        count=1,
    )
    section = re.sub(
        r"(background:\s*#D4820A;[\s\S]*?\">\s*)\d+%(</div>)",
        rf"\g<1>{midterm}%\g<2>",
        section,
        count=1,
    )
    section = re.sub(
        r"(background:\s*#CC5F3F;[\s\S]*?width:\s*)\d+%([\s\S]*?\">\s*)\d+%(</div>)",
        rf"\g<1>{balance}%\g<2>{balance}%\g<3>",
        section,
        count=1,
    )

    for label, ratio in ((CONTRACT, contract), (MIDTERM, midterm), (BALANCE, balance)):
        pattern, replacement = label_ratio(label, ratio)
        section = re.sub(pattern, replacement, section)

    section = re.sub(re.escape(CONTRACT) + r"\s*—\s*\d+%", f"{CONTRACT} — {contract}%", section)
    section = re.sub(
        re.escape(MIDTERM) + r"\s*—\s*\d+%\s*(?:\(\d+회 분납\))?",
        midterm_title,
        section,
    )
    section = re.sub(re.escape(BALANCE) + r"\s*—\s*\d+%", f"{BALANCE} — {balance}%", section)
    section = re.sub(
        r"(<strong[^>]*>)\d+%(</strong>)",
        rf"\g<1>{contract}%\g<2>",
        section,
        count=1,
    )

    html = prefix + section + suffix
    html = re.sub(
        re.escape(CONTRACT) + r"\s*\d+%,\s*" + re.escape(MIDTERM) + r"\s*\d+%\(\d+회\),\s*" + re.escape(BALANCE) + r"\s*\d+%",
        qa_ratio,
        html,
    )
    html = re.sub(
        re.escape(CONTRACT) + r"\s*\d+%,\s*" + re.escape(MIDTERM) + r"\s*\d+%,\s*" + re.escape(BALANCE) + r"\s*\d+%",
        qa_ratio,
        html,
    )
    return html


def git_lines(args: list[str]) -> list[str]:
    output = subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace")
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_blob(path: str) -> dict | None:
    try:
        output = subprocess.check_output(
            ["git", "show", f"origin/main:{path}"],
            cwd=ROOT,
            text=True,
            encoding="utf-8-sig",
            errors="replace",
        )
        return json.loads(output)
    except Exception:
        return None


def main() -> None:
    pdf_by_notice = {
        path.name.split(" ", 1)[0]: path
        for path in PDF_DIR.glob("*.pdf")
        if path.name[:10].isdigit()
    }

    finance_by_notice: dict[str, dict[str, object]] = {}
    failed_pdf: list[tuple[str, str, list[str]]] = []
    for notice_id, path in sorted(pdf_by_notice.items()):
        finance = extract_finance_from_pdf(path)
        if finance.has_core_ratios:
            finance_by_notice[notice_id] = finance.to_dict()
        else:
            failed_pdf.append((notice_id, path.name, finance.evidence or []))

    cache_updates = 0
    for notice_id, finance in finance_by_notice.items():
        path = CACHE_DIR / f"{notice_id}.json"
        if not path.exists():
            continue
        data = load_json(path)
        manual = dict(data.get("manual_finance") or {})
        manual.update(
            {
                "contract_ratio": finance["contract_ratio"],
                "midterm_ratio": finance["midterm_ratio"],
                "balance_ratio": finance["balance_ratio"],
                "midterm_count": finance.get("midterm_count") or "",
                "source_pdf": finance.get("source_pdf") or "",
                "source_page": finance.get("source_page"),
            }
        )
        data["manual_finance"] = manual
        data["pdf_extracted_finance"] = finance
        write_json(path, data)
        cache_updates += 1

    deleted_posts: list[tuple[str, str]] = []
    kept_posts: list[tuple[str, str]] = []
    patched_posts: list[tuple[str, str, dict[str, object]]] = []
    for post_dir in sorted(path for path in POSTS_DIR.iterdir() if path.is_dir()):
        meta_path = post_dir / "post_meta.json"
        post_path = post_dir / "post.html"
        if not meta_path.exists():
            deleted_posts.append((post_dir.name, "missing post_meta.json"))
            shutil.rmtree(post_dir)
            continue
        meta = load_json(meta_path)
        notice_id = notice_id_from_meta(meta)
        if not notice_id or notice_id not in pdf_by_notice:
            deleted_posts.append((post_dir.name, notice_id or "unknown_notice_id"))
            shutil.rmtree(post_dir)
            continue

        kept_posts.append((post_dir.name, notice_id))
        finance = finance_by_notice.get(notice_id)
        if not finance or not post_path.exists():
            continue

        meta["contract_ratio"] = str(finance["contract_ratio"])
        meta["midterm_ratio"] = str(finance["midterm_ratio"])
        meta["balance_ratio"] = str(finance["balance_ratio"])
        if finance.get("midterm_count"):
            meta["midterm_count"] = str(finance["midterm_count"])
        meta["pdf_extracted_finance"] = finance
        write_json(meta_path, meta)

        html = post_path.read_text(encoding="utf-8")
        patched = patch_finance_html(html, finance)
        if patched != html:
            post_path.write_text(patched, encoding="utf-8")
            patched_posts.append((post_dir.name, notice_id, finance))

    write_json(PROCESSED_FILE, sorted({notice_id for _, notice_id in kept_posts if notice_id}))
    build_front_index()
    deleted_tracked_files = git_lines(["git", "diff", "--name-status", "--diff-filter=D", "--", "output/posts"])
    cumulative_deleted_posts = len([line for line in deleted_tracked_files if line.startswith("D\t")]) // 2

    notice_paths = [
        path
        for path in git_lines(["git", "ls-tree", "-r", "--name-only", "origin/main", "output/data_cache/notices"])
        if path.endswith(".json")
    ]
    rows = []
    for path in notice_paths:
        data = git_blob(path)
        if not data:
            continue
        doc = data.get("document") or {}
        detail = data.get("detail_raw") or {}
        notice_id = str(data.get("notice_id") or doc.get("notice_id") or detail.get("PBLANC_NO") or Path(path).stem)
        apt_name = str(data.get("apt_name") or doc.get("apt_name") or detail.get("HOUSE_NM") or "").strip()
        notice_url = str(doc.get("notice_url") or detail.get("PBLANC_URL") or "").strip()
        notice_date = str(doc.get("notice_date") or detail.get("RCRIT_PBLANC_DE") or "").strip()
        rows.append((notice_id, notice_date, apt_name, notice_url))
    rows.sort(key=lambda row: (row[1], row[0]), reverse=True)

    download_lines = [
        "# PDF 다운로드 대상 공고 목록",
        "",
        "- 생성 기준: origin/main `output/data_cache/notices`",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 총 공고 수: {len(rows)}건",
        "",
        "| 공고번호 | 모집공고일 | 아파트명 | 청약홈 상세페이지 URL |",
        "|---|---:|---|---|",
    ]
    for notice_id, notice_date, apt_name, notice_url in rows:
        download_lines.append(f"| {notice_id} | {notice_date} | {apt_name.replace('|', '\\|')} | {notice_url} |")
    DOWNLOAD_LIST.write_text("\n".join(download_lines) + "\n", encoding="utf-8")

    report_lines = [
        "# PDF 기반 포스트 정리 및 자금계획 보강 결과",
        "",
        f"- 작업 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 로컬 PDF 수: {len(pdf_by_notice)}건",
        f"- PDF 자금계획 추출 성공: {len(finance_by_notice)}건",
        f"- PDF 자금계획 추출 실패: {len(failed_pdf)}건",
        f"- 로컬 캐시 보강: {cache_updates}건",
        f"- 유지한 포스트: {len(kept_posts)}건",
        f"- 삭제한 포스트: {max(len(deleted_posts), cumulative_deleted_posts)}건",
        f"- 자금계획 HTML/메타 패치: {len(patched_posts)}건",
        "",
        "## 삭제한 포스트",
    ]
    report_lines.extend(f"- {name}: {reason}" for name, reason in deleted_posts)
    report_lines.extend(["", "## 자금계획 추출 실패 PDF"])
    report_lines.extend(
        f"- {notice_id} {name}: {' / '.join(evidence[:2]) if evidence else '추출 실패'}"
        for notice_id, name, evidence in failed_pdf
    )
    report_lines.extend(["", "## 패치한 포스트"])
    report_lines.extend(
        f"- {name} ({notice_id}): 계약금 {finance['contract_ratio']}%, 중도금 {finance['midterm_ratio']}%, 잔금 {finance['balance_ratio']}%"
        for name, notice_id, finance in patched_posts
    )
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "pdf_count": len(pdf_by_notice),
                "finance_success": len(finance_by_notice),
                "finance_failed": len(failed_pdf),
                "cache_updates": cache_updates,
                "kept_posts": len(kept_posts),
                "deleted_posts": len(deleted_posts),
                "patched_posts": len(patched_posts),
                "download_list_rows": len(rows),
                "download_list": str(DOWNLOAD_LIST),
                "report": str(REPORT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

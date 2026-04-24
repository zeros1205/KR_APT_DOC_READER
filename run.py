"""
run.py
────────────────────────────────────────────────────
청약홈 공고 자동 수집 → RAG 저장 → 블로그 포스팅 일괄 생성

사용법:
    python run.py                   # 최근 7일 공고 자동 수집
    python run.py --sample          # 샘플 데이터로 테스트 (API 키 불필요)
    python run.py --days 14         # 최근 14일 공고 수집
    python run.py --limit 3         # 최대 3건만 처리
    python run.py --open            # 완료 후 브라우저 자동 실행
────────────────────────────────────────────────────
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from agents.collector import collect_from_api, get_sample_document
from orchestrator import run_pipeline_from_doc
from index_renderer import build_manifest

PROCESSED_FILE = BASE_DIR / "output" / "processed_notices.json"


def _load_processed() -> set[str]:
    if PROCESSED_FILE.exists():
        raw = PROCESSED_FILE.read_text(encoding="utf-8-sig").strip()
        if not raw:
            return set()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print("[경고] processed_notices.json 파싱 실패 → 빈 히스토리로 진행")
            return set()
        return set(data)
    return set()


def _save_processed(ids: set[str]) -> None:
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _open_html(path: Path) -> None:
    html = path / "post.html"
    if html.exists():
        import webbrowser
        webbrowser.open(html.as_uri())


async def main() -> None:
    parser = argparse.ArgumentParser(description="청약홈 분양공고 블로그 포스팅 자동 생성")
    parser.add_argument("--sample", action="store_true", help="샘플 데이터로 테스트")
    parser.add_argument("--days",   type=int, default=7,  help="최근 N일 공고 수집 (기본 7)")
    parser.add_argument("--limit",  type=int, default=5,  help="최대 처리 건수 (기본 5)")
    parser.add_argument("--open",   action="store_true",  help="완료 후 HTML 브라우저 자동 실행")
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("PROJECT BALI — 분양공고 블로그 포스팅 자동 생성")
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 공고 수집
    if args.sample:
        print("\n[모드] 샘플 데이터 사용 (API 키 불필요)")
        docs = [get_sample_document()]
    else:
        print(f"\n[수집] 최근 {args.days}일 공고 조회 중...")
        print(f"[DEBUG] collect_from_api 호출 시작...")
        docs = await collect_from_api(days_back=args.days)
        print(f"[DEBUG] collect_from_api 호출 완료: {len(docs)}건")

    if not docs:
        print("최근 공고 없음. 잠시 후 다시 시도하세요.")
        return

    # 중복 방지: 이미 처리된 공고 제외 (--sample 모드는 항상 실행)
    processed_ids = _load_processed()
    if not args.sample:
        before = len(docs)
        docs = [d for d in docs if d.notice_id not in processed_ids]
        skipped = before - len(docs)
        if skipped:
            print(f"[중복 제외] {skipped}건 이미 처리됨 → {len(docs)}건 신규 처리")

    docs = docs[:args.limit]
    if not docs:
        print("신규 공고 없음. 모두 이미 처리된 공고입니다.")
        return

    print(f"\n처리 대상: {len(docs)}건")

    # 공고별 파이프라인 실행
    results: list[Path] = []
    failed: list[str] = []

    for i, doc in enumerate(docs, 1):
        print(f"\n[{i}/{len(docs)}] {doc.apt_name} ({doc.region})")
        try:
            path = await run_pipeline_from_doc(doc)
            if path:
                results.append(path)
                processed_ids.add(doc.notice_id)
                print(f"  → 저장: {path}")
                if args.open:
                    _open_html(path)
            else:
                failed.append(doc.apt_name)
        except Exception as e:
            print(f"  오류: {e}")
            failed.append(doc.apt_name)

    # 처리 완료 목록 저장 (중복 방지용)
    if not args.sample and results:
        _save_processed(processed_ids)
        print(f"\n[중복 방지] processed_notices.json 업데이트 ({len(processed_ids)}건 누적)")

    # 결과 요약
    print("\n" + "=" * 55)
    print(f"완료: {len(results)}/{len(docs)}건 성공")
    if failed:
        print(f"실패: {', '.join(failed)}")
    print("=" * 55)

    if results:
        print("\n생성된 포스팅:")
        for p in results:
            print(f"  {p / 'post.html'}")

        # manifest.json 업데이트 (index.html은 수정 안 함)
        print("\n[업데이트] manifest.json 갱신 중...")
        build_manifest()

        if not args.open:
            latest = results[-1] / "post.html"
            print(f"\n브라우저 열기: start {latest}")


if __name__ == "__main__":
    asyncio.run(main())

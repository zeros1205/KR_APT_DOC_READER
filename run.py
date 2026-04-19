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
import asyncio
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from agents.collector import collect_from_api, get_sample_document
from orchestrator import run_pipeline_from_doc


def _open_html(path: Path) -> None:
    html = path / "post.html"
    if html.exists():
        subprocess.Popen(["cmd", "/c", "start", "", str(html)])


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
        docs = await collect_from_api(days_back=args.days)

    if not docs:
        print("최근 공고 없음. 잠시 후 다시 시도하세요.")
        return

    docs = docs[:args.limit]
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
                print(f"  → 저장: {path}")
                if args.open:
                    _open_html(path)
            else:
                failed.append(doc.apt_name)
        except Exception as e:
            print(f"  오류: {e}")
            failed.append(doc.apt_name)

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

        if not args.open:
            latest = results[-1] / "post.html"
            print(f"\n브라우저 열기: start {latest}")


if __name__ == "__main__":
    asyncio.run(main())

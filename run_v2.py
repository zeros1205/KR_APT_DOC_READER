#!/usr/bin/env python3
"""
run_v2.py
─────────────────────────────────────────────────
orchestrator_v2 기반 개선된 진입점

사용법:
    python run_v2.py --sample              # 샘플 데이터로 테스트 (API 키 불필요)
    python run_v2.py 2024-sample-001       # 단일 공고 처리
    python run_v2.py --batch ID1 ID2 ID3  # 배치 처리 (여러 공고)
    python run_v2.py --api --days 7        # 공공API에서 최근 7일 공고 수집 후 처리
─────────────────────────────────────────────────
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "pipeline"))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from orchestrator_v2 import run_pipeline_v2, run_batch_pipeline


def print_header(text: str):
    """헤더 출력"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)


async def main():
    parser = argparse.ArgumentParser(description="orchestrator_v2 메인 진입점")
    parser.add_argument("notice_ids", nargs="*", help="처리할 공고 ID 리스트")
    parser.add_argument("--sample", action="store_true", help="샘플 데이터로 테스트")
    parser.add_argument("--batch", action="store_true", help="배치 모드 (여러 공고 처리)")
    parser.add_argument("--api", action="store_true", help="공공API에서 공고 수집")
    parser.add_argument("--days", type=int, default=7, help="수집 기간 (일)")
    parser.add_argument("--limit", type=int, default=3, help="최대 처리 건수")

    args = parser.parse_args()

    print_header("orchestrator_v2 v1.0")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 모드 결정
    if args.sample:
        notice_ids = ["2024-sample-001"]
        print(f"모드: 샘플 테스트")
    elif args.api:
        print_header("공공API에서 공고 수집")
        print(f"수집 기간: 최근 {args.days}일")
        print(f"최대 처리 건수: {args.limit}")
        # TODO: 공공API에서 공고 ID 수집 (현재는 구현 예정)
        notice_ids = ["2024-sample-001"]
        print(f"⚠️  API 연동 미완성 - 샘플 데이터로 실행")
    elif args.batch and args.notice_ids:
        notice_ids = args.notice_ids
        print(f"모드: 배치 처리")
        print(f"공고 수: {len(notice_ids)}")
    elif args.notice_ids:
        notice_ids = args.notice_ids
        print(f"모드: 단일/복수 처리")
        print(f"공고 수: {len(notice_ids)}")
    else:
        notice_ids = ["2024-sample-001"]
        print(f"모드: 기본값 (샘플)")

    print_header("처리 시작")

    try:
        if len(notice_ids) == 1:
            # 단일 처리
            print(f"공고 ID: {notice_ids[0]}")
            success = await run_pipeline_v2(notice_ids[0])

            if success:
                print_header("✅ 처리 완료")
                return 0
            else:
                print_header("❌ 처리 실패")
                return 1
        else:
            # 배치 처리
            print(f"공고 ID: {', '.join(notice_ids)}")
            results = await run_batch_pipeline(notice_ids)

            success_count = results["success"]
            total_count = results["total"]

            if success_count == total_count:
                print_header(f"✅ 배치 처리 완료 ({success_count}/{total_count})")
                return 0
            elif success_count > 0:
                print_header(f"⚠️  배치 처리 부분 성공 ({success_count}/{total_count})")
                return 1
            else:
                print_header(f"❌ 배치 처리 실패 (0/{total_count})")
                return 1

    except KeyboardInterrupt:
        print_header("처리 중단됨 (사용자)")
        return 130
    except Exception as e:
        print_header(f"❌ 오류 발생")
        print(f"에러: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

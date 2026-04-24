"""
posting_monitor.py
────────────────────────────────────────────────
생성된 포스팅 모니터링 및 통계
────────────────────────────────────────────────
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

try:
    from pipeline.logger import logger
except ImportError:
    logger = None


class PostingMonitor:
    """포스팅 모니터링 및 통계"""

    def __init__(self, output_root: Path = None):
        if output_root is None:
            output_root = Path(__file__).parent.parent / "output"

        # 보안: 경로 조작 방지 (절대경로로 정규화)
        self.output_root = Path(output_root).resolve()
        self.posts_dir = self.output_root / "posts"

        # 보안: 경로가 프로젝트 내에 있는지 확인
        try:
            self.posts_dir.relative_to(Path(__file__).parent.parent.resolve())
        except ValueError:
            raise ValueError(f"Invalid output path: {output_root}")

    def get_all_posts(self) -> List[Dict[str, Any]]:
        """모든 생성된 포스팅 수집"""
        posts = []

        if not self.posts_dir.exists():
            return posts

        for post_dir in sorted(self.posts_dir.iterdir()):
            if not post_dir.is_dir():
                continue

            meta_file = post_dir / "post_meta.json"
            html_file = post_dir / "post.html"

            if meta_file.exists():
                try:
                    # 보안: 파일 크기 제한 (100KB 이상이면 스킵)
                    if meta_file.stat().st_size > 100 * 1024:
                        if logger:
                            logger.warning(f"파일 크기 초과: {post_dir.name}")
                        continue

                    with open(meta_file, encoding="utf-8") as f:
                        meta = json.load(f)

                    # 보안: 필수 필드 검증
                    if not isinstance(meta, dict):
                        raise ValueError("Invalid JSON structure")

                    # 포스트 정보 구성
                    post = {
                        "id": post_dir.name,
                        "title": meta.get("title", ""),
                        "apt_name": meta.get("apt_name", ""),
                        "location": meta.get("location", ""),
                        "region": meta.get("region_category", "기타"),
                        "price_range": meta.get("price_range", ""),
                        "theme": meta.get("theme", "claude"),
                        "html_size": html_file.stat().st_size if html_file.exists() else 0,
                        "created_at": meta.get("created_at", ""),
                    }
                    posts.append(post)
                except Exception as e:
                    if logger:
                        logger.warning(f"포스팅 로드 실패: {post_dir.name}: {e}")

        return posts

    def get_statistics(self) -> Dict[str, Any]:
        """생성된 포스팅 통계"""
        posts = self.get_all_posts()

        if not posts:
            return {
                "total_posts": 0,
                "total_size_mb": 0,
                "by_region": {},
                "by_theme": {},
                "avg_size_kb": 0
            }

        # 지역별 통계
        by_region = defaultdict(int)
        for post in posts:
            by_region[post["region"]] += 1

        # 테마별 통계
        by_theme = defaultdict(int)
        for post in posts:
            by_theme[post["theme"]] += 1

        # 크기 통계
        total_size = sum(p["html_size"] for p in posts)
        avg_size = total_size / len(posts) if posts else 0

        return {
            "total_posts": len(posts),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "avg_size_kb": round(avg_size / 1024, 2),
            "by_region": dict(sorted(by_region.items())),
            "by_theme": dict(sorted(by_theme.items())),
        }

    def print_summary(self):
        """콘솔 요약 출력"""
        stats = self.get_statistics()
        posts = self.get_all_posts()

        print("\n" + "=" * 60)
        print("  📊 포스팅 모니터링 통계")
        print("=" * 60)

        if stats["total_posts"] == 0:
            print("생성된 포스팅이 없습니다.")
            print("=" * 60)
            return

        # 기본 통계
        print(f"\n📈 기본 통계")
        print(f"  • 총 포스팅: {stats['total_posts']}개")
        print(f"  • 전체 크기: {stats['total_size_mb']} MB")
        print(f"  • 평균 크기: {stats['avg_size_kb']} KB")

        # 지역별
        print(f"\n🗺️  지역별 분포")
        for region, count in stats["by_region"].items():
            pct = (count / stats["total_posts"] * 100)
            bar = "█" * int(pct / 5)
            print(f"  • {region:12s} {count:2d}개 {bar} {pct:.0f}%")

        # 테마별
        print(f"\n🎨 테마별 분포")
        for theme, count in stats["by_theme"].items():
            print(f"  • {theme:12s} {count}개")

        # 최근 포스팅 5개
        if posts:
            print(f"\n⏰ 최근 포스팅 (상위 5개)")
            for post in posts[-5:]:
                size_kb = post["html_size"] / 1024
                print(f"  • {post['id']:20s} | {post['apt_name'][:15]:15s} | {size_kb:6.1f}KB")

        print("\n" + "=" * 60)

    def export_json(self, output_file: Path = None) -> bool:
        """통계를 JSON으로 내보내기"""
        if output_file is None:
            output_file = self.output_root / "posting_stats.json"

        try:
            stats = self.get_statistics()
            posts = self.get_all_posts()

            data = {
                "generated_at": datetime.now().isoformat(),
                "statistics": stats,
                "posts": posts
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if logger:
                logger.info(f"통계 내보내기: {output_file}")
            print(f"✅ 통계 저장: {output_file}")
            return True

        except Exception as e:
            if logger:
                logger.error(f"통계 내보내기 실패: {e}")
            print(f"❌ 통계 저장 실패: {e}")
            return False

    def get_post_quality_report(self) -> Dict[str, Any]:
        """포스팅 품질 리포트"""
        posts = self.get_all_posts()

        if not posts:
            return {"status": "No posts generated"}

        quality_issues = []

        for post in posts:
            # 크기 기준 (너무 작으면 문제)
            if post["html_size"] < 10000:  # 10KB 미만
                quality_issues.append({
                    "post_id": post["id"],
                    "issue": "HTML 크기가 너무 작음",
                    "size_kb": post["html_size"] / 1024
                })

            # 제목 길이
            if len(post["title"]) < 10:
                quality_issues.append({
                    "post_id": post["id"],
                    "issue": "제목이 너무 짧음",
                    "title_len": len(post["title"])
                })

        return {
            "total_posts": len(posts),
            "quality_issues": quality_issues,
            "issue_count": len(quality_issues),
            "quality_score": round((len(posts) - len(quality_issues)) / len(posts) * 100, 1) if posts else 0
        }


# 테스트 코드
if __name__ == "__main__":
    import sys

    monitor = PostingMonitor()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--json":
            monitor.export_json()
        elif sys.argv[1] == "--quality":
            report = monitor.get_post_quality_report()
            print("\n📋 품질 리포트")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        monitor.print_summary()
        quality = monitor.get_post_quality_report()
        if quality["quality_issues"]:
            print(f"\n⚠️  품질 문제: {quality['issue_count']}건")
            for issue in quality["quality_issues"][:3]:
                print(f"  • {issue['post_id']}: {issue['issue']}")

"""
migrate_to_db.py
────────────────────────────────────────────────────
Migrate existing JSON data to PostgreSQL/SQLite DB
────────────────────────────────────────────────────
"""

import json
import re
import sys
from pathlib import Path
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent))

from database import engine, SessionLocal, init_db
from models import Apartment, Posting, PostingContent, PostingMeta

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def migrate_existing_data():
    """기존 JSON 파일들을 DB로 마이그레이션"""
    init_db()
    db: Session = SessionLocal()

    posts_dir = OUTPUT_DIR / "posts"
    if not posts_dir.exists():
        print("⚠️  posts 디렉토리가 없습니다")
        return

    migrated_count = 0
    error_count = 0

    for post_dir in posts_dir.iterdir():
        if not post_dir.is_dir():
            continue

        meta_file = post_dir / "post_meta.json"
        if not meta_file.exists():
            continue

        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                post_meta = json.load(f)

            apt_data = post_meta.get("facts", {})
            apt_notice_id = apt_data.get("notice_id", "")

            apartment = db.query(Apartment).filter(
                Apartment.api_notice_id == apt_notice_id
            ).first()

            if not apartment:
                apartment = Apartment(
                    api_notice_id=apt_notice_id,
                    apt_name=apt_data.get("apt_name", ""),
                    supply_address=apt_data.get("supply_address", ""),
                    location=apt_data.get("location", ""),
                    supply_scale=apt_data.get("supply_scale", ""),
                    total_units=apt_data.get("total_households"),
                    is_hot_zone=apt_data.get("is_hot_zone", "N"),
                    regulated_zone=apt_data.get("regulated_zone"),
                    readmission_limit=apt_data.get("readmission_limit"),
                    live_requirement=apt_data.get("live_requirement"),
                    price_cap=apt_data.get("price_cap"),
                    land_type=apt_data.get("land_type"),
                    constructor=apt_data.get("constructor"),
                    notice_url=apt_data.get("notice_url"),
                )
                db.add(apartment)
                db.flush()

            content_data = post_meta.get("content", {})
            post_title = content_data.get("post_title", apartment.apt_name)
            post_slug = _slugify(post_title)

            posting = Posting(
                apartment_id=apartment.id,
                post_title=post_title,
                post_subtitle=content_data.get("post_subtitle", ""),
                post_slug=post_slug,
                theme=post_meta.get("theme", "intercom"),
                quality_score=post_meta.get("quality_score", 0),
                is_published=1,
            )
            db.add(posting)
            db.flush()

            posting_content = PostingContent(
                posting_id=posting.id,
                apt_intro=content_data.get("apt_intro", ""),
                location_intro=content_data.get("location_intro", ""),
                financial_intro=content_data.get("financial_intro", ""),
                qa_intro=content_data.get("qa_intro", ""),
                schedule_desc=content_data.get("schedule_desc", ""),
                tax_desc=content_data.get("tax_desc", ""),
                unit_type_desc=content_data.get("unit_type_desc", ""),
                subway_score=content_data.get("subway_score", "★★★☆☆"),
                subway_detail=content_data.get("subway_detail", ""),
                school_score=content_data.get("school_score", "★★★☆☆"),
                school_detail=content_data.get("school_detail", ""),
                life_score=content_data.get("life_score", "★★★☆☆"),
                life_detail=content_data.get("life_detail", ""),
                medical_score=content_data.get("medical_score", "★★★☆☆"),
                medical_detail=content_data.get("medical_detail", ""),
                eligibility_special=content_data.get("eligibility_special", []),
                eligibility_rank1=content_data.get("eligibility_rank1", []),
                eligibility_rank2=content_data.get("eligibility_rank2", []),
                qa_blocks=content_data.get("qa_blocks", []),
                seo_tags=content_data.get("seo_tags", []),
            )
            db.add(posting_content)
            db.flush()

            posting_metadata = PostingMeta(
                posting_id=posting.id,
                special_supply_date=apt_data.get("special_supply_date", "-"),
                rank1_date=apt_data.get("rank1_date", "-"),
                rank2_date=apt_data.get("rank2_date", "-"),
                winner_date=apt_data.get("winner_date", "-"),
                move_in_date=apt_data.get("move_in_date", "-"),
                contract_ratio=str(apt_data.get("contract_ratio", "10")),
                contract_amount=apt_data.get("contract_amount", ""),
                midterm_ratio=str(apt_data.get("midterm_ratio", "60")),
                midterm_count=str(apt_data.get("midterm_count", "6")),
                balance_ratio=str(apt_data.get("balance_ratio", "30")),
                loan_info=apt_data.get("loan_info", ""),
                resale_restriction=apt_data.get("resale_restriction", "-"),
                acquisition_tax_rate=apt_data.get("acquisition_tax_rate", ""),
            )
            db.add(posting_metadata)

            migrated_count += 1
            print(f"✅ {apartment.apt_name} → DB 저장됨")

        except Exception as e:
            error_count += 1
            print(f"❌ {post_dir.name} 마이그레이션 실패: {e}")

    db.commit()
    db.close()

    print(f"\n🎉 마이그레이션 완료")
    print(f"   성공: {migrated_count}개")
    print(f"   실패: {error_count}개")


if __name__ == "__main__":
    print("🔄 기존 JSON 데이터를 DB로 마이그레이션 중...")
    migrate_existing_data()

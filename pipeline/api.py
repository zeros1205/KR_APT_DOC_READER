"""
api.py
────────────────────────────────────────────────────
FastAPI 백엔드 서버
DB 기반 CRUD API + 검색 엔드포인트

실행: python pipeline/api.py
접근: http://localhost:8000
문서: http://localhost:8000/docs
────────────────────────────────────────────────────
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import datetime

from database import SessionLocal, init_db, engine
from models import Base, Apartment, Posting, PostingContent, PostingMetadata

# DB 초기화
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="KR APT DOC READER API",
    description="아파트 분양공고 분석 API",
    version="2.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────
# 아파트 API
# ──────────────────────────────────────────────────

@app.get("/api/apartments")
def list_apartments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """아파트 목록 조회 (검색/필터 가능)"""
    query = db.query(Apartment)

    if search:
        query = query.filter(Apartment.apt_name.ilike(f"%{search}%"))

    if region:
        query = query.filter(Apartment.location.ilike(f"%{region}%"))

    total = query.count()
    apartments = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "id": apt.id,
                "apt_name": apt.apt_name,
                "supply_address": apt.supply_address,
                "location": apt.location,
                "constructor": apt.constructor,
                "notice_url": apt.notice_url,
                "created_at": apt.created_at.isoformat()
            }
            for apt in apartments
        ]
    }


@app.get("/api/apartments/{apt_id}")
def get_apartment(apt_id: int, db: Session = Depends(get_db)):
    """특정 아파트 정보 조회"""
    apt = db.query(Apartment).filter(Apartment.id == apt_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Apartment not found")

    return {
        "id": apt.id,
        "api_notice_id": apt.api_notice_id,
        "apt_name": apt.apt_name,
        "supply_address": apt.supply_address,
        "location": apt.location,
        "supply_scale": apt.supply_scale,
        "total_units": apt.total_units,
        "is_hot_zone": apt.is_hot_zone,
        "regulated_zone": apt.regulated_zone,
        "readmission_limit": apt.readmission_limit,
        "live_requirement": apt.live_requirement,
        "price_cap": apt.price_cap,
        "land_type": apt.land_type,
        "constructor": apt.constructor,
        "notice_url": apt.notice_url,
        "created_at": apt.created_at.isoformat()
    }


# ──────────────────────────────────────────────────
# 포스팅 API
# ──────────────────────────────────────────────────

@app.get("/api/postings")
def list_postings(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    apt_id: Optional[int] = None,
    theme: Optional[str] = None,
    min_score: Optional[int] = None,
    published_only: bool = True,
    db: Session = Depends(get_db)
):
    """포스팅 목록 조회"""
    query = db.query(Posting)

    if published_only:
        query = query.filter(Posting.is_published == True)

    if apt_id:
        query = query.filter(Posting.apartment_id == apt_id)

    if theme:
        query = query.filter(Posting.theme == theme)

    if min_score is not None:
        query = query.filter(Posting.quality_score >= min_score)

    total = query.count()
    postings = query.order_by(Posting.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "id": post.id,
                "apt_name": post.apartment.apt_name if post.apartment else "",
                "post_title": post.post_title,
                "post_subtitle": post.post_subtitle,
                "quality_score": post.quality_score,
                "theme": post.theme,
                "is_published": post.is_published,
                "created_at": post.created_at.isoformat()
            }
            for post in postings
        ]
    }


@app.get("/api/postings/{post_id}")
def get_posting(post_id: int, db: Session = Depends(get_db)):
    """특정 포스팅 조회 (콘텐츠 + 메타 포함)"""
    posting = db.query(Posting).filter(Posting.id == post_id).first()
    if not posting:
        raise HTTPException(status_code=404, detail="Posting not found")

    content = posting.content
    metadata = posting.metadata

    return {
        "id": posting.id,
        "apartment": {
            "id": posting.apartment.id,
            "apt_name": posting.apartment.apt_name,
            "supply_address": posting.apartment.supply_address,
            "location": posting.apartment.location,
        } if posting.apartment else None,
        "post_title": posting.post_title,
        "post_subtitle": posting.post_subtitle,
        "post_slug": posting.post_slug,
        "quality_score": posting.quality_score,
        "theme": posting.theme,
        "is_published": posting.is_published,
        "content": {
            "apt_intro": content.apt_intro if content else "",
            "location_intro": content.location_intro if content else "",
            "financial_intro": content.financial_intro if content else "",
            "qa_intro": content.qa_intro if content else "",
            "subway_detail": content.subway_detail if content else "",
            "school_detail": content.school_detail if content else "",
            "life_detail": content.life_detail if content else "",
            "medical_detail": content.medical_detail if content else "",
            "qa_blocks": content.qa_blocks if content else [],
            "seo_tags": content.seo_tags if content else [],
        } if content else None,
        "metadata": {
            "special_supply_date": metadata.special_supply_date if metadata else "",
            "rank1_date": metadata.rank1_date if metadata else "",
            "rank2_date": metadata.rank2_date if metadata else "",
            "move_in_date": metadata.move_in_date if metadata else "",
            "contract_ratio": metadata.contract_ratio if metadata else "",
            "midterm_ratio": metadata.midterm_ratio if metadata else "",
            "balance_ratio": metadata.balance_ratio if metadata else "",
        } if metadata else None,
        "created_at": posting.created_at.isoformat(),
        "updated_at": posting.updated_at.isoformat()
    }


# ──────────────────────────────────────────────────
# 검색 API
# ──────────────────────────────────────────────────

@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, max_length=100),
    type: str = Query("all", regex="^(all|apartments|postings)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """통합 검색 (아파트 + 포스팅)"""
    results = {"apartments": [], "postings": []}

    if type in ["all", "apartments"]:
        apts = db.query(Apartment).filter(
            Apartment.apt_name.ilike(f"%{q}%")
        ).limit(limit).all()
        results["apartments"] = [
            {
                "id": apt.id,
                "apt_name": apt.apt_name,
                "location": apt.location,
                "supply_address": apt.supply_address,
            }
            for apt in apts
        ]

    if type in ["all", "postings"]:
        posts = db.query(Posting).filter(
            Posting.post_title.ilike(f"%{q}%")
        ).limit(limit).all()
        results["postings"] = [
            {
                "id": post.id,
                "post_title": post.post_title,
                "apt_name": post.apartment.apt_name if post.apartment else "",
                "quality_score": post.quality_score,
            }
            for post in posts
        ]

    return results


# ──────────────────────────────────────────────────
# 상태 체크
# ──────────────────────────────────────────────────

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """헬스 체크 + DB 연결 확인"""
    try:
        # DB 연결 테스트
        db.execute("SELECT 1")
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """전체 통계"""
    total_apts = db.query(Apartment).count()
    total_postings = db.query(Posting).count()
    published_postings = db.query(Posting).filter(Posting.is_published == True).count()

    return {
        "total_apartments": total_apts,
        "total_postings": total_postings,
        "published_postings": published_postings,
        "unpublished_postings": total_postings - published_postings,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

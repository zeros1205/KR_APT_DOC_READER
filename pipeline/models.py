"""
models.py
────────────────────────────────────────────────────
SQLAlchemy ORM 모델 정의
아파트, 포스팅, 콘텐츠, 메타데이터
────────────────────────────────────────────────────
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, create_engine
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Apartment(Base):
    """아파트/단지 정보"""
    __tablename__ = "apartments"

    id = Column(Integer, primary_key=True, index=True)
    api_notice_id = Column(String(50), unique=True, index=True)
    apt_name = Column(String(255), nullable=False, index=True)
    supply_address = Column(String(500), nullable=False)
    location = Column(String(255))
    supply_scale = Column(String(255))
    total_units = Column(Integer, nullable=True)
    is_hot_zone = Column(String(10), default="N")
    regulated_zone = Column(Text, nullable=True)
    readmission_limit = Column(String(100), nullable=True)
    live_requirement = Column(String(100), nullable=True)
    price_cap = Column(String(50), nullable=True)
    land_type = Column(String(100), nullable=True)
    constructor = Column(String(255), nullable=True)
    notice_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    postings = relationship("Posting", back_populates="apartment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Apartment(id={self.id}, apt_name={self.apt_name})>"


class Posting(Base):
    """포스팅 메타정보"""
    __tablename__ = "postings"

    id = Column(Integer, primary_key=True, index=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=False, index=True)
    post_title = Column(String(255), nullable=False)
    post_subtitle = Column(String(255), nullable=True)
    post_slug = Column(String(255), unique=True, index=True)
    theme = Column(String(50), default="intercom")
    quality_score = Column(Integer, default=0)
    is_published = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    apartment = relationship("Apartment", back_populates="postings")
    content = relationship("PostingContent", back_populates="posting", uselist=False, cascade="all, delete-orphan")
    meta = relationship("PostingMeta", back_populates="posting", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Posting(id={self.id}, post_title={self.post_title})>"


class PostingContent(Base):
    """포스팅 콘텐츠 (LLM 생성)"""
    __tablename__ = "postings_content"

    id = Column(Integer, primary_key=True, index=True)
    posting_id = Column(Integer, ForeignKey("postings.id"), nullable=False, unique=True)

    apt_intro = Column(Text, default="")
    location_intro = Column(Text, default="")
    financial_intro = Column(Text, default="")
    qa_intro = Column(Text, default="")
    schedule_desc = Column(Text, default="")
    tax_desc = Column(Text, default="")
    unit_type_desc = Column(Text, default="")

    subway_score = Column(String(20), default="★★★☆☆")
    subway_detail = Column(Text, default="")
    school_score = Column(String(20), default="★★★☆☆")
    school_detail = Column(Text, default="")
    life_score = Column(String(20), default="★★★☆☆")
    life_detail = Column(Text, default="")
    medical_score = Column(String(20), default="★★★☆☆")
    medical_detail = Column(Text, default="")

    eligibility_special = Column(JSON, default=list)
    eligibility_rank1 = Column(JSON, default=list)
    eligibility_rank2 = Column(JSON, default=list)
    qa_blocks = Column(JSON, default=list)
    seo_tags = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    posting = relationship("Posting", back_populates="content")

    def __repr__(self):
        return f"<PostingContent(posting_id={self.posting_id})>"


class PostingMeta(Base):
    """포스팅 메타데이터 (일정, 금융) - 'Meta'로 이름 변경"""
    __tablename__ = "postings_meta"

    id = Column(Integer, primary_key=True, index=True)
    posting_id = Column(Integer, ForeignKey("postings.id"), nullable=False, unique=True)

    special_supply_date = Column(String(50), default="-")
    rank1_date = Column(String(50), default="-")
    rank2_date = Column(String(50), default="-")
    winner_date = Column(String(50), default="-")
    move_in_date = Column(String(50), default="-")

    contract_ratio = Column(String(10), default="10")
    contract_amount = Column(String(100), default="")
    midterm_ratio = Column(String(10), default="60")
    midterm_count = Column(String(10), default="6")
    balance_ratio = Column(String(10), default="30")
    loan_info = Column(Text, default="")
    resale_restriction = Column(String(200), default="-")

    acquisition_tax_rate = Column(String(50), default="")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    posting = relationship("Posting", back_populates="meta")

    def __repr__(self):
        return f"<PostingMeta(posting_id={self.posting_id})>"

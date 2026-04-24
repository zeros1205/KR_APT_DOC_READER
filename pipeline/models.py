"""
models.py
────────────────────────────────────────────────────
SQLAlchemy ORM models for apartment data and postings
────────────────────────────────────────────────────
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Apartment(Base):
    __tablename__ = "apartments"

    id = Column(Integer, primary_key=True, index=True)
    api_notice_id = Column(String(255), unique=True, nullable=False, index=True)
    apt_name = Column(String(255), nullable=False)
    supply_address = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False, index=True)
    supply_scale = Column(String(100))
    total_units = Column(Integer)
    is_hot_zone = Column(String(10))
    regulated_zone = Column(String(100))
    readmission_limit = Column(String(100))
    live_requirement = Column(String(100))
    price_cap = Column(String(100))
    land_type = Column(String(100))
    constructor = Column(String(255))
    notice_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    postings = relationship("Posting", back_populates="apartment", cascade="all, delete-orphan")


class Posting(Base):
    __tablename__ = "postings"

    id = Column(Integer, primary_key=True, index=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    post_title = Column(String(255), nullable=False)
    post_subtitle = Column(String(255))
    post_slug = Column(String(255), unique=True, nullable=False, index=True)
    theme = Column(String(50), default="intercom")
    quality_score = Column(Integer, default=0)
    is_published = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    apartment = relationship("Apartment", back_populates="postings")
    content = relationship("PostingContent", back_populates="posting", uselist=False, cascade="all, delete-orphan")
    meta = relationship("PostingMeta", back_populates="posting", uselist=False, cascade="all, delete-orphan")


class PostingContent(Base):
    __tablename__ = "postings_content"

    id = Column(Integer, primary_key=True, index=True)
    posting_id = Column(Integer, ForeignKey("postings.id"), nullable=False, unique=True)
    apt_intro = Column(String(500))
    location_intro = Column(String(500))
    financial_intro = Column(String(500))
    qa_intro = Column(String(500))
    schedule_desc = Column(String(1000))
    tax_desc = Column(String(1000))
    unit_type_desc = Column(String(1000))
    subway_score = Column(String(20), default="★★★☆☆")
    subway_detail = Column(String(1000))
    school_score = Column(String(20), default="★★★☆☆")
    school_detail = Column(String(1000))
    life_score = Column(String(20), default="★★★☆☆")
    life_detail = Column(String(1000))
    medical_score = Column(String(20), default="★★★☆☆")
    medical_detail = Column(String(1000))
    eligibility_special = Column(JSON, default=[])
    eligibility_rank1 = Column(JSON, default=[])
    eligibility_rank2 = Column(JSON, default=[])
    qa_blocks = Column(JSON, default=[])
    seo_tags = Column(JSON, default=[])

    posting = relationship("Posting", back_populates="content")


class PostingMeta(Base):
    __tablename__ = "postings_meta"

    id = Column(Integer, primary_key=True, index=True)
    posting_id = Column(Integer, ForeignKey("postings.id"), nullable=False, unique=True)
    special_supply_date = Column(String(100))
    rank1_date = Column(String(100))
    rank2_date = Column(String(100))
    winner_date = Column(String(100))
    move_in_date = Column(String(100))
    contract_ratio = Column(String(50))
    contract_amount = Column(String(100))
    midterm_ratio = Column(String(50))
    midterm_count = Column(String(50))
    balance_ratio = Column(String(50))
    loan_info = Column(String(1000))
    resale_restriction = Column(String(100))
    acquisition_tax_rate = Column(String(100))

    posting = relationship("Posting", back_populates="metadata")

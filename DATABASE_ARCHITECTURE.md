# Database Architecture Documentation

## Overview
Multi-layer data persistence system for the apartment sales announcement pipeline, eliminating Cloudflare cache invalidation issues through immutable HTML + dynamic manifest approach.

## Architecture Diagram

```
orchestrator.py (LLM Pipeline)
    │
    ├── Generate Post (HTML)
    ├── Save HTML to output/posts/{id}/post.html
    │
    └── _save_to_database(post_data, facts, content)
         │
         ├── Create/Match Apartment record
         ├── Create Posting record
         ├── Create PostingContent record
         ├── Create PostingMeta record
         └── Commit transaction (with rollback on error)
              │
              └── SQLAlchemy ORM
                   │
                   └── PostgreSQL/SQLite
                       
build_manifest()
    │
    ├── Scan output/posts/* for post_meta.json
    ├── Extract apartment, location, quality metadata
    │
    └── Generate output/manifest.json
         │
         └── Serves to JavaScript runtime in index.html

index.html (Static, created once)
    │
    └── Runtime JavaScript
         │
         ├── fetch('./manifest.json')
         ├── Parse regions and posts
         ├── Render region tabs with counts
         ├── Render post cards with filtering
         └── Support pagination (12 posts/page)
```

## Database Schema

### 1. Apartment (주택 정보)
```sql
CREATE TABLE apartment (
    id SERIAL PRIMARY KEY,
    api_notice_id VARCHAR(100) UNIQUE,  -- 청약홈 공고 ID
    apt_name VARCHAR(200),
    supply_address VARCHAR(300),
    location VARCHAR(200),             -- "지역 / 구간" format
    supply_scale VARCHAR(100),
    total_units INTEGER,
    is_hot_zone VARCHAR(1),            -- Y/N
    regulated_zone VARCHAR(200),
    readmission_limit VARCHAR(100),
    live_requirement VARCHAR(100),
    price_cap VARCHAR(100),
    land_type VARCHAR(100),
    constructor VARCHAR(200),
    notice_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Posting (포스팅)
```sql
CREATE TABLE posting (
    id SERIAL PRIMARY KEY,
    apartment_id INTEGER FOREIGN KEY,
    post_title VARCHAR(300),
    post_subtitle VARCHAR(500),
    post_slug VARCHAR(300),            -- URL-friendly slug
    theme VARCHAR(50),                 -- claude|notion|intercom|airbnb|stripe|apple|mintlify
    quality_score INTEGER,             -- 0-100
    is_published BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3. PostingContent (포스팅 본문)
```sql
CREATE TABLE posting_content (
    id SERIAL PRIMARY KEY,
    posting_id INTEGER FOREIGN KEY,
    apt_intro TEXT,                    -- 150-200자 소개
    location_intro TEXT,               -- 100-150자 입지소개
    financial_intro TEXT,              -- 80-100자 자금계획 도입
    qa_intro TEXT,                     -- 60-80자 Q&A 도입
    schedule_desc TEXT,                -- 청약 일정 설명
    tax_desc TEXT,                     -- 세금 정리
    unit_type_desc TEXT,               -- 타입별 분양가 설명
    subway_score VARCHAR(10),          -- ★★★☆☆
    subway_detail TEXT,
    school_score VARCHAR(10),
    school_detail TEXT,
    life_score VARCHAR(10),
    life_detail TEXT,
    medical_score VARCHAR(10),
    medical_detail TEXT,
    eligibility_special JSON,          -- 특별공급 조건
    eligibility_rank1 JSON,            -- 1순위 조건
    eligibility_rank2 JSON,            -- 2순위 조건
    qa_blocks JSON,                    -- [{q: string, a: string}]
    seo_tags JSON,                     -- [string...]
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4. PostingMeta (포스팅 메타데이터)
```sql
CREATE TABLE posting_meta (
    id SERIAL PRIMARY KEY,
    posting_id INTEGER FOREIGN KEY,
    special_supply_date VARCHAR(20),
    rank1_date VARCHAR(20),
    rank2_date VARCHAR(20),
    winner_date VARCHAR(20),
    move_in_date VARCHAR(20),
    contract_ratio VARCHAR(10),        -- "10"
    contract_amount VARCHAR(100),
    midterm_ratio VARCHAR(10),         -- "60"
    midterm_count VARCHAR(10),         -- "6"
    balance_ratio VARCHAR(10),         -- "30"
    loan_info TEXT,
    resale_restriction VARCHAR(200),
    acquisition_tax_rate VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Implementation Files

### Core Database Layer
- **database.py**: SQLAlchemy engine, session management, init_db()
- **models.py**: SQLAlchemy ORM models with relationships
- **migrate_to_db.py**: Migration script for existing JSON data

### API Layer
- **api.py**: FastAPI REST backend with 7 endpoints
  - GET /api/apartments
  - GET /api/apartments/{id}
  - GET /api/postings
  - GET /api/postings/{id}
  - GET /api/search
  - GET /health
  - GET /api/stats

### Frontend Layer
- **index_renderer.py**: 
  - build_front_index_once() - creates index.html once (immutable)
  - build_manifest() - generates manifest.json dynamically
  - _render_runtime_script() - JavaScript for dynamic rendering

- **index.html**: Static template with embedded JavaScript runtime
- **manifest.json**: Dynamic post metadata for client-side rendering

### Pipeline Integration
- **orchestrator.py**: 
  - _save_to_database() - persists post data to 4 tables
  - run_pipeline() - calls _save_to_database() after HTML generation
  - Post-generation: calls build_manifest()

## Data Flow

### 1. POST Generation (Orchestrator)
```python
async def run_pipeline(...) -> Path | None:
    # ... Generate post HTML
    _save_to_database(post_data, facts, content)  # ← DB save
    # ... Move HTML to output/posts/{id}/post.html
    build_manifest()  # ← Update manifest
```

### 2. Database Storage
```python
def _save_to_database(post_data: PostData, facts: dict, content: dict):
    # 1. Get or create Apartment (by api_notice_id)
    apartment = db.query(Apartment).filter(...).first()
    if not apartment:
        apartment = Apartment(...)
        db.add(apartment)
        db.flush()
    
    # 2. Create Posting record
    posting = Posting(apartment_id=apartment.id, ...)
    db.add(posting)
    db.flush()
    
    # 3. Create PostingContent record
    posting_content = PostingContent(posting_id=posting.id, ...)
    db.add(posting_content)
    db.flush()
    
    # 4. Create PostingMeta record
    posting_meta = PostingMeta(posting_id=posting.id, ...)
    db.add(posting_meta)
    
    # 5. Commit transaction
    db.commit()
```

### 3. Manifest Generation
```python
def build_manifest():
    # Load all posts from output/posts/*/post_meta.json
    posts = load_posts()
    
    # Extract unique regions from location field
    regions_map = {}
    for post in posts:
        region = extract_region(post.get("facts", {}).get("location"))
        regions_map[region] = regions_map.get(region, 0) + 1
    
    # Build manifest structure
    manifest = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_posts": len(posts),
            "version": "2.0"
        },
        "regions": [
            {"code": "all", "name": "전체", "count": len(posts)},
            # ... region entries
        ],
        "posts": [
            {
                "id": post_dir_name,
                "_dir": post_dir_name,
                "apt_name": facts.apt_name,
                "location": facts.location,
                "region": extracted_region,
                "post_title": content.post_title,
                "quality_score": quality_score,
                "theme": theme,
                "created_at": date_string
            },
            # ... more posts
        ]
    }
    
    # Write to output/manifest.json
```

### 4. Frontend Rendering
```javascript
// index.html runtime script
async function initPage() {
    await loadManifest();           // fetch('./manifest.json')
    renderRegionTabs();              // display regions with counts
    renderCards();                   // display filtered posts
}

function filterByRegion(btn, regionCode) {
    // Update active filter
    // Re-render cards based on region
}

// Pagination support
var POSTS_PER_PAGE = 12;
var _currentPage = 1;
```

## API Response Examples

### GET /api/apartments
```json
{
    "total": 5,
    "skip": 0,
    "limit": 10,
    "data": [
        {
            "id": 1,
            "apt_name": "분당 신도시 래미안",
            "supply_address": "경기도 성남시 분당구",
            "location": "경기도 / 성남시",
            "constructor": "럭스건설",
            "notice_url": "https://www.applyhome.co.kr/",
            "created_at": "2026-04-24T11:38:36.010672"
        }
    ]
}
```

### GET /api/postings/{id}
```json
{
    "id": 1,
    "apartment": {
        "id": 1,
        "apt_name": "분당 신도시 래미안",
        "supply_address": "경기도 성남시 분당구",
        "location": "경기도 / 성남시"
    },
    "post_title": "분당 신도시 래미안 프리미엄 분양",
    "post_slug": "bundang-ramian-premium",
    "quality_score": 85,
    "theme": "claude",
    "is_published": 1,
    "content": {
        "apt_intro": "분당 신도시의 프리미엘...",
        "location_intro": "강남역 근처 접근성...",
        "qa_blocks": [
            {"q": "청약 자격은?", "a": "무주택 세대주..."}
        ]
    },
    "metadata": {
        "special_supply_date": "2026-05-10",
        "rank1_date": "2026-05-12",
        "move_in_date": "2027-01-15"
    }
}
```

### GET /api/search?q=강남
```json
{
    "apartments": [
        {
            "id": 4,
            "apt_name": "강남역 프리미엄 아파트",
            "location": "서울 / 강남구",
            "supply_address": "서울 / 강남구 123번지"
        }
    ],
    "postings": [
        {
            "id": 4,
            "post_title": "강남역 프리미엄 아파트 분양공고 분석",
            "apt_name": "강남역 프리미엄 아파트",
            "quality_score": 85
        }
    ]
}
```

## Deployment

### Environment Variables
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/apt_reader  # or sqlite:///./apt_reader.db
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
```

### Database Setup
```bash
# SQLite (default)
python -c "from pipeline.database import init_db; init_db()"

# PostgreSQL
psql -U user -d apt_reader -f schema.sql
```

### Migration
```bash
# Migrate existing JSON posts to database
python -m pipeline.migrate_to_db
```

### API Server
```bash
# Development
python -m pipeline.api

# Production with Gunicorn
gunicorn pipeline.api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Cloudflare Pages Deployment
The `output/` directory contains:
- `index.html` - Static, created once, never modified
- `manifest.json` - Updated after each post generation
- `posts/{id}/post.html` - Individual post HTML files
- `_redirects`, `_headers` - Cloudflare configuration

Cache strategy:
- `index.html` - Cached (immutable after creation)
- `manifest.json` - Not cached or short TTL (updated frequently)
- `/posts/*` - Cached (immutable after creation)

## Error Handling

### Database Errors
```python
def _save_to_database(...):
    db = SessionLocal()
    try:
        # ... create records
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ DB 저장 실패: {e}")
    finally:
        db.close()
```

### Manifest Load Failures
```javascript
async function loadManifest() {
    try {
        var response = await fetch('./manifest.json');
        _manifestData = await response.json();
    } catch (e) {
        console.error('manifest.json 로드 실패:', e);
        _manifestData = { posts: [], regions: [] };
    }
}
```

## Performance Considerations

### Query Optimization
- Apartment matching by unique api_notice_id (indexed)
- Posting filtering by apt_id, theme, quality_score
- Search uses ILIKE for Korean text support

### Frontend Optimization
- manifest.json size: ~1.5KB per 10 posts
- JavaScript runtime: ~3KB (minified)
- Region filtering via client-side JavaScript (no API calls)

### Database Indexes
Recommended indexes:
```sql
CREATE INDEX idx_apartment_api_notice_id ON apartment(api_notice_id);
CREATE INDEX idx_posting_apartment_id ON posting(apartment_id);
CREATE INDEX idx_posting_is_published ON posting(is_published);
CREATE INDEX idx_posting_quality_score ON posting(quality_score);
```

## Testing

### Unit Tests (Required)
- Database initialization
- Model relationships
- CRUD operations
- Migration script

### Integration Tests (Recommended)
- Full orchestrator pipeline with sample data
- API endpoint responses with various filters
- Manifest generation accuracy
- JavaScript rendering in browser

### Performance Tests (Optional)
- Database query performance with 1000+ records
- API response time under load
- Manifest file size growth
- JavaScript runtime memory usage

## Future Enhancements

1. **Caching Layer** - Redis for API responses
2. **Search Improvement** - Full-text search with PostgreSQL
3. **Analytics** - Track post views, engagement
4. **Admin Dashboard** - CRUD UI for manual adjustments
5. **Version Control** - Archive old manifest versions

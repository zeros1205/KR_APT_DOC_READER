# PROJECT BALI — Claude 작업 지침

## 프로젝트 개요
청약홈 분양공고 데이터를 수집·분석하여 네이버 블로그 HTML 포스팅을 자동생성하는 파이프라인.
발행 방식: 스마트에디터 ONE → [HTML] → 전체 붙여넣기 → 발행 (스크립트/외부CSS 불가, 인라인 스타일만 허용).

## 블로그 글 구조 (스토리텔링 흐름)
딱딱한 공공기관 요약표 형식이 아닌, 마케팅 담당자가 고객을 처음 만나 대화하듯 자연스럽게 흘러야 한다.

```
1. 헤더 배너 (브랜드 + 제목)
2. 단지 소개 인사 (apt_intro: 마케터 어투, 150~200자) → 핵심 요약 테이블 → 조감도 이미지
3. 타입별 분양가 테이블 + 평면도 플레이스홀더
4. 입지 소개 (location_intro: 지역 특색 산문, 100~150자) → 별점 카드 4개
5. 자금 계획 도입 (financial_intro, 80~100자) → 납부 타임라인
6. 세금 정리 테이블
7. 청약 일정 캘린더
8. Q&A 도입 (qa_intro, 60~80자) → Q&A 블록 6개
9. 면책 고지 + SEO 태그
```

## 테마 시스템
`config.py`의 `BLOG_THEME` 값으로 디자인을 전환한다.
지원 테마: `notion` | `stripe` | `airbnb` | `linear`
각 테마의 CSS 토큰은 `html_renderer.py`의 `THEMES` 딕셔너리에 정의.

## 디자인 가이드라인

### 타이포그래피 계층 구조
- 본문 폰트: `Pretendard` 우선, 폴백: `Inter, -apple-system, system-ui, sans-serif`
- 헤드라인과 본문의 폰트 크기 대비는 3배 이상 유지 (시각적 위계 확보)

### 컬러 시스템 (사용자 지정 기본값, 테마 미적용 시)
- 주색상 Primary: `#3B82F6` (신뢰도 상징)
- 보조색상 Secondary: `#F59E0B` (행동 유도 및 강조)
- 명도 대비: 모든 텍스트와 배경의 대비 최소 4.5:1 이상 (WCAG AA)

### 상호작용 규칙
- 버튼 hover: 배경색 명도 10% 감소, transition 200ms
- 모든 클릭 가능 요소: `cursor: pointer` 필수

### 웹 접근성 (WCAG 2.1 AA)
- 이미지: 명확한 `alt` 텍스트 필수
- 모든 폼 입력 필드: 연결된 `<label>` 필수
- 키보드 포커스 링(focus ring) 제거 금지

### 성능 제약
- 애니메이션: `transform`과 `opacity` 속성만 사용 (브라우저 부하 최소화)
- 단일 책임 원칙: 컴포넌트 코드 크기 최소화

### 모바일 퍼스트
- 터치 대상(버튼, 링크): 최소 44×44px 이상 확보
- 본문 텍스트 크기: 최소 16px (모바일 가독성)

### 콘텐츠 톤앤매너
- 친절하고 명확한 어조, 명령조 대신 제안형 문장
- 마케팅 담당자가 고객과 대화하는 산문체 (공문서 스타일 금지)

## 이미지 처리 원칙
- 단지 조감도 / 평면도 / 위치지도: 건설사 저작물 → PLACEHOLDER (직접 삽입 안내)
- 자동 수집 이미지(Unsplash/Pexels): CC0 라이선스 + 출처 자동 표기
- 입지 분석 섹션과 자금 계획 섹션: 이미지 없음 (섹션 자체 디자인으로 충분)

## API 키 관리
`.env` 파일에 보관. 코드에 직접 입력 금지.
필요 키: `OPENAI_API_KEY`, `UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY`, `PUBLIC_DATA_API_KEY`

## 실행 명령어 요약
```powershell
cd "D:\Downloads\재혁\★PROJECT_BALI\아파트분양공고 읽어주기"
.venv\Scripts\Activate.ps1

python run.py --sample            # 샘플 테스트
python run.py --days 7 --limit 3  # 실제 공고 수집
python test_pipeline.py --step 3  # HTML 렌더링 테스트 (API 불필요)
python test_pipeline.py --step 6  # RAG 연동 전체 테스트
```

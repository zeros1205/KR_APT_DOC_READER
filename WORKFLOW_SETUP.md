# 🚀 Daily.yml 워크플로우 실행 준비 가이드

**작성일:** 2026-04-24  
**상태:** 🟢 실행 준비 완료

---

## ✅ 최종 체크리스트

### 코드 준비
- [x] OpenAI → Gemini 3.1 Pro Preview 전환
- [x] 모델 코드: `gemini-3.1-pro-preview` 검증
- [x] 샘플 데이터: 오티에르 반포 (실데이터)
- [x] daily.yml 워크플로우 구성 (14단계)
- [x] Cloudflare Workers 배포 통합
- [x] 모든 커밋 적용 완료

### Cloudflare 배포
- [x] Cloudflare Workers 설정됨
- [x] apt-note.com 연결됨
- [x] 빌드 로그: ✅ 성공
- [x] 배포 URL: https://kraptdocreader.jax1205.workers.dev

### 문서 완성
- [x] WORKFLOW_READY.md (실행 가이드)
- [x] MODELS.md (모델 관리)
- [x] CLAUDE.md (프로젝트 가이드)

---

## 📋 필수 GitHub Secrets 설정 (3개)

### Step 1: GitHub Settings 접속
```
Repository → Settings → Secrets and variables → Actions
```

### Step 2: 3개 Secret 추가

| Secret 이름 | 값 | 용도 |
|-----------|-----|------|
| **GEMINI_API_KEY** | AIzaSy... | LLM 팩트 추출/생성 |
| **PUBLIC_DATA_API_KEY** | ... | 청약홈 데이터 |
| **CLOUDFLARE_API_TOKEN** | ... | Workers 배포 |

**Secret 생성 방법:**
```
"New repository secret" 클릭
→ Name: GEMINI_API_KEY
→ Value: (API 키 붙여넣기)
→ "Add secret"
```

---

## 🎯 워크플로우 실행 방법

### 수동 실행 (즉시 테스트)
```
1. GitHub Actions 탭 이동
2. "청약 공고 자동 수집 및 포스팅 생성" 선택
3. "Run workflow" 클릭
4. 옵션 입력 (선택사항):
   - days: 7 (최근 N일)
   - limit: 3 (최대 처리 건수)
5. "Run" 클릭
```

### 자동 실행 (매일)
```
매일 UTC 00:00 (한국 09:00 KST) 자동 실행
```

---

## 📊 워크플로우 상세 구성

### 14단계 처리 흐름

| 단계 | 작업 | 목적 |
|------|------|------|
| 1 | 코드 체크아웃 | 최신 코드 가져오기 |
| 2 | Python 3.11 설정 | 런타임 환경 준비 |
| 3 | 의존성 설치 | 필수 라이브러리 설치 |
| 4 | 환경 확인 | API 키 검증 |
| 5 | Grounding 테스트 | Google 검색 테스트 |
| 6 | 모델 검증 | gemini-3.1-pro-preview 확인 |
| 7 | 파이프라인 실행 | 포스팅 자동 생성 |
| 8 | 프론트페이지 재생성 | index.html 업데이트 |
| 9 | 결과 커밋 | main 브랜치에 푸시 |
| 10 | Node.js 설정 | Wrangler 실행환경 |
| 11 | Wrangler 설치 | Cloudflare 배포 도구 |
| 12 | Workers 배포 | apt-note.com 업데이트 |
| 13 | 완료 요약 | 상태 리포팅 |
| 14 | 포스팅 백업 | 아티팩트 저장 |

---

## 🔄 배포 흐름도

```
GitHub Actions 실행
     ↓
포스팅 자동 생성/수집
     ↓
main 브랜치에 커밋
     ↓
Cloudflare Workers 배포 (wrangler)
     ↓
apt-note.com 즉시 업데이트
     ↓
완료 알림 + 로그 저장
```

---

## 📱 실행 후 확인 사항

### 성공 시나리오 ✅
```
1. GitHub Actions 로그에서 모든 단계 초록색 확인
2. apt-note.com에 새로운 포스팅 표시
3. "Success! Build completed" 메시지 확인
```

### 실패 시나리오 ❌
```
1. Actions 로그에서 실패 단계 확인
2. 에러 메시지 읽기
3. 해당 Secret 또는 설정 수정
4. 다시 실행
```

---

## 🔑 API 토큰 확인 방법

### Cloudflare API Token
```
Cloudflare 대시보드
→ My Profile
→ API Tokens
→ 기존 토큰 또는 "Create Token"
→ "Edit Cloudflare Workers" Template
→ 토큰 복사
```

### Gemini API Key
```
Google AI Studio
→ https://aistudio.google.com/app/apikey
→ "Create API key"
→ 키 복사
```

### Public Data API Key
```
데이터포털
→ https://www.data.go.kr/
→ "청약홈 분양정보 조회"
→ 활용신청 → 개발계정 발급
```

---

## 📝 환경 변수 검증

워크플로우 Step 4에서 자동으로 다음을 확인합니다:
```
✅ GEMINI_API_KEY 설정 여부
✅ PUBLIC_DATA_API_KEY 설정 여부
✅ CLOUDFLARE_API_TOKEN 설정 여부
❌ 누락된 키는 에러 메시지 표시
```

---

## 🚨 트러블슈팅

| 문제 | 원인 | 해결책 |
|------|------|--------|
| GEMINI_API_KEY 없음 | Secret 미설정 | GitHub Secrets에 추가 |
| 모델 오류 (404) | 잘못된 모델명 | MODELS.md 확인 |
| Workers 배포 실패 | 토큰 만료 | 새 토큰 생성 후 업데이트 |
| 포스팅 생성 안 됨 | 공고 없음 | limit 값 증가 또는 days 값 변경 |
| apt-note.com 404 | 배포 미완료 | 워크플로우 로그 확인 |

---

## 📚 관련 문서

| 파일 | 용도 |
|------|------|
| WORKFLOW_READY.md | 실행 가이드 |
| MODELS.md | LLM 모델 관리 |
| CLAUDE.md | 프로젝트 전체 가이드 |
| LAYOUT_SPEC.md | 포스팅 레이아웃 명세 |

---

## ✨ 최근 커밋

```
b80c634 - Restore Cloudflare Workers deployment
f04c4fd - Add workflow execution readiness checklist
fd15cb2 - Remove Cloudflare Workers deployment
b787230 - Add Cloudflare API token to job-level env
```

---

## 🎯 실행 준비 완료!

**모든 것이 준비되었습니다. 다음 3단계만 진행하면 됩니다:**

### 1️⃣ GitHub Secrets 설정 (5분)
```
Settings → Secrets and variables → Actions
→ 3개 Secret 추가
```

### 2️⃣ 워크플로우 실행 (즉시)
```
Actions → "청약 공고..." → "Run workflow" → "Run"
```

### 3️⃣ 결과 확인 (1-2분)
```
Actions 로그에서 실행 상황 모니터링
```

---

**상태: 🟢 즉시 실행 가능**  
**마지막 업데이트: 2026-04-24 02:00 KST**

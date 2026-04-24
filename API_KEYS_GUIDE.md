# API 키 발급 가이드

로컬 개발 환경에서 테스트하기 위해 각 API 키를 발급받는 방법을 안내합니다.

## 📋 필수 API 키 목록

| 순번 | API | 용도 | 난이도 | 예상 시간 |
|------|-----|------|--------|---------|
| 1 | Anthropic Claude | 팩트 추출 보조 | ⭐ 쉬움 | 5분 |
| 2 | OpenAI | 콘텐츠 생성 | ⭐ 쉬움 | 5분 |
| 3 | Google Gemini | 메인 LLM (필수) | ⭐ 쉬움 | 2분 |
| 4 | 청약홈 공공데이터 | 분양공고 수집 | ⭐⭐ 보통 | 10분 |
| 5 | Unsplash | 이미지 수집 (선택) | ⭐ 쉬움 | 5분 |
| 6 | Pexels | 이미지 수집 (선택) | ⭐ 쉬움 | 5분 |

---

## 1️⃣ Anthropic Claude API

**용도**: Claude Haiku (팩트 추출 보조)  
**난이도**: ⭐ 쉬움  
**예상 시간**: 5분

### 단계별 가이드

1. https://console.anthropic.com/ 방문
2. **Sign Up** 클릭 (또는 로그인)
3. 이메일 인증 완료
4. 좌측 메뉴 **API Keys** 선택
5. **Create Key** 버튼 클릭
6. 생성된 키 복사

### 사용 방법

```bash
# .env 파일에 추가
ANTHROPIC_API_KEY=sk-ant-v0-xxxxx...
```

**참고**: 무료 크레딧 $5 제공

---

## 2️⃣ OpenAI API

**용도**: GPT-4 (콘텐츠 생성)  
**난이도**: ⭐ 쉬움  
**예상 시간**: 5분

### 단계별 가이드

1. https://platform.openai.com/signup 방문
2. Sign Up (이메일 또는 Google/Microsoft 계정)
3. 이메일 인증 + 전화번호 인증
4. 좌측 메뉴 **API keys** 선택
5. **+ Create new secret key** 클릭
6. 생성된 키 복사 (한 번만 표시됨)

### 사용 방법

```bash
# .env 파일에 추가
OPENAI_API_KEY=sk-proj-xxxxx...
```

**참고**: 
- 결제 수단 등록 필요 (Pay-as-you-go)
- 첫 $5 크레딧 제공 (3개월 유효)
- 사용량 체크: https://platform.openai.com/account/usage/overview

---

## 3️⃣ Google Gemini API (⭐ 필수)

**용도**: Gemini 3.1 Flash, Flash Lite (메인 LLM)  
**난이도**: ⭐ 쉬움  
**예상 시간**: 2분

### 단계별 가이드

1. https://ai.google.dev/ 방문
2. **Get API Key** 클릭
3. "Create API Key in Google Cloud"
4. 프로젝트 선택 (신규면 생성)
5. "Create API key in new project" 클릭
6. **API Key** 페이지에서 키 복사

### 사용 방법

```bash
# .env 파일에 추가
GEMINI_API_KEY=AIzaSyxxxxxx...
```

**참고**: 
- 무료 Tier (매달 1500 RPM 제한)
- 가장 빠르고 저렴함
- **이 프로젝트에서 가장 중요한 키**

---

## 4️⃣ 청약홈 공공데이터 OpenAPI (⭐ 필수)

**용도**: 분양공고 데이터 수집  
**난이도**: ⭐⭐ 보통  
**예상 시간**: 10분

### 단계별 가이드

1. https://www.data.go.kr/ 방문
2. 회원가입 (이메일, 이름, 휴대폰 인증)
3. 로그인
4. 상단 검색창에 "한국부동산원_청약홈 분양정보" 검색
5. 해당 데이터셋 선택
6. **활용신청** 클릭
7. 개발계정 신청 (즉시 발급)
8. 마이페이지 → 개발계정 관리 → API Key 확인

### 사용 방법

```bash
# .env 파일에 추가
PUBLIC_DATA_API_KEY=xxxx-xxxx-xxxx-xxxx
```

**참고**:
- 무료 사용 (가입 필수)
- 40,000회/일 호출 제한
- 이 프로젝트의 데이터 소스

---

## 5️⃣ Unsplash API (선택사항)

**용도**: 무료 고화질 이미지 자동 수집  
**난이도**: ⭐ 쉬움  
**예상 시간**: 5분

### 단계별 가이드

1. https://unsplash.com/developers 방문
2. **Register as a developer** 클릭
3. 회원가입 (Google/GitHub 계정 추천)
4. 앱 생성: **Create an app**
5. 앱 정보 입력 (이름, 설명, 이미지)
6. **Access Key** 복사

### 사용 방법

```bash
# .env 파일에 추가
UNSPLASH_ACCESS_KEY=xxxxx...
```

**참고**:
- 무료 Tier (시간당 50회 요청)
- CC0 라이선스 (상업 이용 가능)
- 크레딧 표기 권장

---

## 6️⃣ Pexels API (선택사항)

**용도**: 무료 고화질 이미지 자동 수집  
**난이도**: ⭐ 쉬움  
**예상 시간**: 5분

### 단계별 가이드

1. https://www.pexels.com/api/ 방문
2. **Your API Key** 클릭
3. 회원가입 (이메일)
4. API Key 확인 (메일로 발송)
5. 키 복사

### 사용 방법

```bash
# .env 파일에 추가
PEXELS_API_KEY=xxxxx...
```

**참고**:
- 무료 Tier (무제한)
- CC0 라이선스
- 매우 관대한 정책

---

## 🚀 빠른 시작

### 최소 필수 구성 (3개)

이 3개만 있으면 기본 파이프라인 실행 가능:

```bash
# .env 파일 생성
cp .env.example .env

# 아래 3개 키만 입력
GEMINI_API_KEY=AIzaSyxxxxxx...          # Google Gemini (필수)
PUBLIC_DATA_API_KEY=xxxx-xxxx...        # 청약홈 공공데이터 (필수)
ANTHROPIC_API_KEY=sk-ant-v0-xxxxx...    # Claude (선택, 있으면 좋음)
```

그 다음 테스트:

```bash
python pipeline/orchestrator_v2.py --sample
```

### 전체 구성 (6개)

모든 기능을 활용하려면:

```bash
# .env 파일에 6개 API 키 모두 입력
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
PUBLIC_DATA_API_KEY=...
UNSPLASH_ACCESS_KEY=...
PEXELS_API_KEY=...
```

---

## ✅ 설정 완료 확인

`.env` 파일 준비 후 테스트:

```bash
# Python 환경에서 키 로드 확인
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('GEMINI_API_KEY:', '✅' if os.getenv('GEMINI_API_KEY') else '❌')
print('PUBLIC_DATA_API_KEY:', '✅' if os.getenv('PUBLIC_DATA_API_KEY') else '❌')
print('ANTHROPIC_API_KEY:', '✅' if os.getenv('ANTHROPIC_API_KEY') else '❌')
"
```

모두 ✅ 표시되면 준비 완료!

---

## 🔒 보안 주의사항

### ❌ 절대 하지 말 것

1. **API 키를 git에 커밋하지 마세요**
   - `.env` 파일은 이미 `.gitignore`에 등록됨
   
2. **API 키를 공개 저장소에 올리지 마세요**
   - GitHub, GitLab 등 공개 저장소

3. **API 키를 메시지로 공유하지 마세요**
   - 슬랙, 이메일, 메신저 등

### ✅ 올바른 방법

1. **로컬 개발**: `.env` 파일 사용
2. **GitHub CI/CD**: GitHub Secrets 사용
3. **프로덕션 배포**: 환경 변수로 관리

### GitHub Secrets 설정

1. Repository Settings → Secrets and variables → Actions
2. **New repository secret** 클릭
3. 각 API 키 입력:
   - Name: `GEMINI_API_KEY`
   - Value: `AIzaSyxxxxxx...`

---

## 🐛 문제 해결

### Q: "API key not found" 오류

```python
# 확인 체크리스트
1. .env 파일이 프로젝트 루트에 있는가?
2. GEMINI_API_KEY=... 형식이 맞는가?
3. 파일 저장 후 Python 재시작했는가?
4. 키가 유효한가? (공백, 따옴표 확인)
```

### Q: 403 Unauthorized 오류

```python
# 각 API별 해결책
1. Gemini: API Key 활성화 확인
   → console.cloud.google.com → Gemini API 활성화

2. 청약홈: 개발계정 승인 확인
   → www.data.go.kr → 개발계정 관리 → 상태 확인

3. OpenAI: 결제 수단 등록 확인
   → platform.openai.com → Billing → Payment methods
```

### Q: Rate limit 초과

```python
# 해결책
- 요청 간격 조정
- 유료 Tier 업그레이드
- 다른 API로 대체 (Unsplash → Pexels)
```

---

## 📚 참고 문서

| API | 공식 문서 | 가격 정책 |
|-----|---------|---------|
| Anthropic | https://docs.anthropic.com | https://www.anthropic.com/pricing |
| OpenAI | https://platform.openai.com/docs | https://openai.com/pricing |
| Google Gemini | https://ai.google.dev/docs | https://ai.google.dev/pricing |
| 청약홈 | https://www.data.go.kr/api | 무료 (공공데이터) |
| Unsplash | https://unsplash.com/developers | https://unsplash.com/pricing |
| Pexels | https://www.pexels.com/api | https://www.pexels.com/api |

---

**이제 준비가 완료되었습니다! 🎉**

```bash
# .env 파일 생성
cp .env.example .env

# API 키 입력 후
python pipeline/orchestrator_v2.py --sample
```

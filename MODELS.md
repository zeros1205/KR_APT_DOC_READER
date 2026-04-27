# 테스트된 LLM 모델 코드 관리

프로젝트에서 테스트된 모델들과 그들의 상태를 기록합니다.

## ✅ 검증된 모델 (현재 사용 중)

### Gemini 3.1 Pro Preview
```
모델 코드: gemini-3.1-pro-preview
API 버전: v1beta
제공사: Google
```

**특성:**
- ✅ Google Search Grounding 지원
- ✅ JSON 응답 가능
- ✅ 한국어 처리 우수
- ✅ 팩트 추출, 콘텐츠 생성, 팩트 체크 모두 지원

**용도:**
- Agent 1: 팩트 추출
- Agent 2: 콘텐츠 생성
- Agent 3: 콘텐츠 검증
- Agent 5: 팩트 체크
- 입지 분석: Google Search Grounding 사용

**필수 환경변수:**
```bash
GEMINI_API_KEY=AIzaSy...
```

---

## ❌ 실패한 모델 (사용 금지)

### OpenAI GPT-5.4
```
모델 코드: gpt-5.4
API: Responses API (v1)
제공사: OpenAI
```

**실패 원인:**
- PermissionDeniedError: "Host not in allowlist"
- API 키 권한 부족 또는 IP 제한
- GitHub Actions 환경에서 차단됨

**상태:** ❌ 사용 불가

---

### Gemini 3.1 Pro (구 버전)
```
모델 코드: gemini-3.1-pro
API 버전: v1beta
제공사: Google
```

**실패 원인:**
```
404 NOT_FOUND: 'models/gemini-3.1-pro is not found for API version v1beta'
```

**해결책:** `gemini-3.1-pro-preview` 사용

**상태:** ❌ 지원 중단

---

## 📋 대체 옵션 (미테스트)

### Gemini 2.0 Flash
```
모델 코드: gemini-2.0-flash
API 버전: v1
제공사: Google
```
**주의:** v1 API 사용 (grounding 지원 확인 필요)

### Claude 3.5 Sonnet
```
모델 코드: claude-3-5-sonnet-20241022
API: Anthropic API
제공사: Anthropic
```
**주의:** Google Grounding 미지원

---

## 🔧 모델 변경 방법

1. `pipeline/config.py` 수정:
```python
LLM_EXTRACT_MODEL = "새_모델_코드"
LLM_CONTENT_MODEL = "새_모델_코드"
LLM_FACTCHECK_MODEL = "새_모델_코드"
LLM_LOCATION_MODEL = "새_모델_코드"
```

2. 로컬 테스트:
```bash
export GEMINI_API_KEY=...  # 또는 OPENAI_API_KEY=...
python run.py --sample
```

3. 오류가 없으면 커밋:
```bash
git commit -m "Switch LLM to [모델명]"
```

---

## 📝 새 모델 테스트 체크리스트

새 모델을 테스트할 때:

- [ ] 모델 코드 정확성 확인
- [ ] API 버전 호환성 확인 (v1 vs v1beta)
- [ ] JSON 응답 형식 지원 확인
- [ ] 로컬 `python run.py --sample` 테스트
- [ ] Google Grounding 지원 여부 확인 (필요시)
- [ ] 한국어 처리 테스트
- [ ] 워크플로우 테스트
- [ ] 이 문서 업데이트

---

**마지막 업데이트:** 2026-04-24  
**현재 사용 모델:** gemini-3.1-pro-preview

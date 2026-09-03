# 정과장의 청약노트 — 운영 종료 체크리스트

운영 종료일: **2026-09-03**

이 문서는 서비스를 완전히 정지시키기 위해 필요한 작업을 정리한다.
레포에서 처리한 것과, **사람이 콘솔에서 직접 해야만 멈추는 것**을 구분한다.

---

## 1. 이 PR 이 실제로 정지시킨 것

### 1-1. GitHub Actions 워크플로 17개 전부 삭제

트리거만 제거하는 방식은 **불충분하다.** Cloudflare Worker 가 GitHub API 로
`workflow_dispatch` 를 직접 호출하기 때문에, `schedule:` 만 지우면 Worker 가
계속 워크플로를 깨운다. 그래서 파일 자체를 삭제해 dispatch 대상이 사라지게 했다.

삭제된 워크플로와 원래 하던 일:

| 워크플로 | 자동 실행 | 하던 일 |
|---|---|---|
| `push-notifications` | 매일 10:00 / 17:00 KST | **실사용자 폰으로 FCM 푸시 발송** |
| `codex-collect-notices` | 매일 08:00 / 11:00 / 15:00 KST | 청약홈 공고 수집 + 커밋 + 텔레그램 알림 |
| `codex-export-notice-urls` | 수집 완료 시 연쇄 | 입력 시트(MD) 생성 + 텔레그램 알림 |
| `codex-cleanup-old-pdfs` | 매일 15:00 KST | 발행된 공고의 PDF 삭제 + 텔레그램 알림 |
| `cloudflare-pages-auto-deploy` | push + 매일 09:20 KST | 사이트 재배포 + 텔레그램 알림 |
| `cloudflare-worker-deploy` | main push | Worker 재배포 |
| `codex-generate-pages` | Worker dispatch | 페이지 생성 (OpenAI + Gemini 과금) |
| `codex-ingest-telegram-pdf` | Worker dispatch | 텔레그램 PDF 첨부 수신 처리 |
| `mobile-app-play-release` | push + PR | Android 서명 빌드 |
| `setup-ios-platform` | PR | macOS 러너 iOS 셋업 |
| 나머지 7개 | 수동 전용 | location v3 테스트/패치, 모바일 릴리스, 버전 발행 |

되살리려면 이 커밋을 revert 하면 전부 복구된다.

### 1-2. Cloudflare Worker cron 제거 (`cloudflare-worker/wrangler.toml`)

```toml
[triggers]
crons = ["0 23 * * *", "0 2 * * *", "0 6 * * *"]
```

이 3개 cron 이 Worker 의 `scheduled()` 를 깨워
`codex-collect-notices.yml` 을 GitHub API 로 dispatch 하고 있었다.
소스에서 제거했으나 — **아래 2-1 을 반드시 읽을 것.**

---

## 2. 레포 변경만으로는 절대 멈추지 않는 것

### 2-1. ★ Cloudflare Worker `apt-note-tg-bot` — 최우선

**이미 배포된 Worker 는 이 레포와 무관하게 계속 살아 있다.**
소스 수정은 재배포해야만 반영되는데, 재배포용 워크플로도 방금 삭제했다.

이 Worker 가 하는 일:

- **자체 cron 하루 3회** → GitHub 워크플로 dispatch (워크플로를 지웠으므로 이제
  실패하지만, 실패할 때마다 `🔔 [자동 스케줄] 워크플로우 실행 실패` 텔레그램이 계속 온다)
- **텔레그램 봇 webhook** — PDF 첨부 수신, `/generate` 명령, 인라인 버튼 콜백 처리
- **`POST /push/dispatch`** — `DEVICES_KV` 에 저장된 기기 토큰으로 FCM 푸시 발송
- `DEVICES_KV` 네임스페이스에 사용자 푸시 토큰·관심지역·발송이력 보관

**조치**: Cloudflare 대시보드 → Workers & Pages → `apt-note-tg-bot` → **삭제**
(또는 최소한 Settings → Trigger Events 에서 cron 3개 제거).
KV 네임스페이스 `DEVICES_KV` (`0c75f73e…`) 도 함께 삭제 — 사용자 기기 토큰이
들어 있으므로 개인정보 정리 관점에서도 지우는 편이 낫다.

### 2-2. 텔레그램 봇 webhook 해제

Worker 를 지우면 webhook 이 죽지만, 봇 자체는 남는다.
완전히 정리하려면:

```
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/deleteWebhook"
```

그 후 @BotFather 에서 `/deletebot` 으로 봇 삭제.

### 2-3. Cloudflare Pages (사이트 `apt-note.com`)

Workers & Pages → Pages 프로젝트 삭제. 삭제 전 콘텐츠를 보관하려면
`output/` 디렉터리가 이미 이 레포에 전부 들어 있으므로 별도 백업 불필요.

---

## 3. 과금 정리 (우선순위 순)

레포가 **public** 이라 GitHub Actions 러너 비용은 $0 이었다. 실제 정기 결제는 아래뿐이다.

| 순위 | 항목 | 금액 | 조치 |
|---|---|---|---|
| 1 | **Apple Developer Program** | **연 $99 자동갱신** | developer.apple.com → Membership → 자동갱신 해제 |
| 2 | **도메인 `apt-note.com`** | 연 1~2만원대 | 등록기관 콘솔에서 자동갱신 해제 |
| 3 | Cloudflare Workers Paid | 월 $5 (유료 플랜인 경우) | 대시보드 → Billing 에서 플랜 확인 |
| 4 | Firebase | Blaze 면 종량, Spark 면 $0 | 프로젝트 설정 → 사용량 및 결제 |

**종량 API 는 수동 실행 때만 과금됐다** (`codex-generate-pages` 경로).
워크플로를 삭제했으므로 이제 호출 자체가 불가능하다.

- OpenAI (GPT-5.4 / 5.4-mini / text-embedding-3-small) — 본문 생성·검증·RAG
- Google Gemini (3.1-pro-preview / flash-lite) — 입지분석 v3, Agent 1B/1C/2/3
- Kakao Local / Unsplash / Pexels / 공공데이터포털 — 전부 무료 쿼터

Google Play Developer $25 는 1회성이라 추가 청구 없음.
AdMob 은 지출이 아니라 수입이며, 앱을 내리면 잔여 정산만 남는다.

---

## 4. 스토어 게시 중단

| 스토어 | 조치 |
|---|---|
| Google Play | Play Console → 고급 설정 → **앱 게시 중단**. 이러면 Android 16(API 36) 대상 API 경고도 함께 무의미해진다 |
| App Store | App Store Connect → 가격 및 판매 여부 → **판매 중단** |

---

## 5. 자격증명 폐기

Worker·워크플로를 정지시킨 뒤 마지막으로 정리한다.

**GitHub → Settings → Secrets and variables → Actions** 에서 삭제:

```
GEMINI_API_KEY, OPENAI_API_KEY, PUBLIC_DATA_API_KEY,
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DISPATCH_TOKEN, WORKER_ORIGIN,
CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID,
FCM_SERVICE_ACCOUNT_JSON, FIREBASE_* , GOOGLE_SERVICES_JSON*,
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON,
KEYSTORE_* / ANDROID_KEYSTORE_*,
APP_STORE_CONNECT_* , IOS_*
```

**서명 키는 삭제 전에 로컬 백업을 권장한다.** Android 업로드 키(`KEYSTORE_BASE64`)를
잃으면 나중에 같은 패키지명으로 앱을 되살릴 수 없다.

발급처에서도 폐기:
- OpenAI platform → API keys
- Google AI Studio / Cloud Console → API 키 및 서비스 계정
- Cloudflare → API Tokens
- Firebase → 서비스 계정 키

---

## 6. 미해결로 남기는 알려진 이슈

2026-08-22 생성분 6건의 입지분석이 구버전(v1 결정론적 폴백)으로 남아 있다.

`2026000342` `2026000354` `2026000368` `2026000372` `2026000383` `2026000388`

원인: 해당 실행(Actions run #64)에서 **Gemini 호출이 전부 실패**했다.
본생성 Agent 2(`gemini-3.1-flash-lite`)는 결정론적 템플릿으로 폴백했고,
v3 패치 스텝(`gemini-3.1-pro-preview`)은 산출물 0건으로 끝났다.
같은 실행에서 OpenAI 계열은 정상 작동했으므로 Gemini 한정 장애다.
Actions 로그가 만료되어 키 무효화인지 결제·할당량 소진인지는 확정하지 못했다.

실패가 3중으로 은폐된 구조도 함께 기록해 둔다 —
`codex-generate-pages.yml` 의 `set +e` 가 exit 1 을 삼켰고,
텔레그램 알림은 본생성 건수만 파싱했으며,
`generate_v3` 의 3단계 폴백이 셋 다 같은 모델을 써서 모델·키 레벨 장애에는
무력했다. 서비스를 되살릴 경우 가장 먼저 고쳐야 할 지점이다.

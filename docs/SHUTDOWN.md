# 정과장의 청약노트 — 운영 종료 체크리스트

운영 종료 결정: **2026-09-01**

이 문서는 서비스 완전 종료(사이트·앱·자동화·과금 전부 정리)를 위한 작업 목록이다.
레포 안에서 처리 가능한 항목은 이미 반영했고, 외부 콘솔에서 사람이 해야 하는
항목은 아래 순서대로 진행하면 된다.

---

## 1. 레포 자동화 정지 — 완료

모든 GitHub Actions 워크플로에서 **자동 트리거를 제거**했다.
`workflow_dispatch`(수동 실행)만 남아 있으므로, 사람이 Actions 탭에서
직접 누르지 않는 한 아무것도 실행되지 않는다.

| 워크플로 | 제거한 트리거 | 원래 하던 일 |
|---|---|---|
| `push-notifications.yml` | `schedule` (매일 10:00 / 17:00 KST) | 실사용자에게 FCM 푸시 발송 |
| `codex-collect-notices.yml` | `schedule` (매일 08:00 / 11:00 / 15:00 KST) | 청약홈 공고 수집 후 커밋 |
| `codex-export-notice-urls.yml` | `workflow_run` (수집 완료 시 연쇄) | 입력 시트(MD) 생성 |
| `codex-cleanup-old-pdfs.yml` | `schedule` (매일 15:00 KST) | 발행 완료 PDF 자동 삭제 |
| `cloudflare-pages-auto-deploy.yml` | `push` + `schedule` (매일 09:20 KST) | 사이트 자동 재배포 |
| `cloudflare-worker-deploy.yml` | `push` | Worker 자동 배포 |
| `mobile-app-play-release.yml` | `push` + `pull_request` | Android 서명 빌드 |
| `setup-ios-platform.yml` | `pull_request` | macOS 러너에서 iOS 플랫폼 셋업 |

검증: 레포 전체에 `cron:` 트리거 **0건**.

> 되돌리려면 이 변경 커밋을 revert 하면 원래 트리거가 그대로 복구된다.
> 워크플로 파일 자체는 하나도 지우지 않았다.

---

## 2. 과금 정리 — 우선순위 순

가장 확실하게 반복 청구되는 것부터. **API 종량과금보다 구독 갱신이 크다.**

- [ ] **Apple Developer Program 자동갱신 해제** — 연 **$99**
  developer.apple.com → Account → Membership → 자동갱신 끄기.
  종료 항목 중 유일하게 금액이 크고 확정적으로 반복된다. 가장 먼저 처리할 것.

- [ ] **도메인 `apt-note.com` 자동갱신 해제** — 연 1~2만원대
  등록기관 콘솔. 기존 페이지 URL을 살려둘 계획이 없다면 해제.

- [ ] **Cloudflare 플랜 확인** — Workers Paid 사용 중이면 월 $5
  대시보드 → Billing. 무료 플랜이면 추가 조치 불필요.

- [ ] **Firebase 플랜 확인** — Blaze면 종량과금, Spark면 $0
  프로젝트 설정 → 사용량 및 결제.

- [ ] **OpenAI API 키 폐기** — platform.openai.com → API keys
  자동 실행이 멈춘 지금은 $0이지만, 키가 살아 있으면 유출 시 과금된다.
  선불 크레딧 잔액이 있으면 소멸 조건도 함께 확인.

- [ ] **Google Gemini API 키 폐기** — aistudio.google.com/apikey
  Google Cloud Console → 결제에서 프로젝트 결제 계정도 함께 정리.

- [ ] **공공데이터포털 활용신청 해지** (선택) — 무료라 급하지 않음

> Google Play Developer 등록비 $25는 **1회성**이라 추가 청구가 없다.
> AdMob은 지출이 아니라 수입이므로, 앱을 내린 뒤 잔여 수익 정산만 확인하면 된다.

---

## 3. 앱 스토어 게시 중단

- [ ] **Google Play** — Play Console → 테스트 및 출시 → 고급 설정 →
  앱 사용 가능 여부 → **게시 중단(Unpublish)**
  트랙별 활성 릴리스(프로덕션 1.0.9 / 공개·내부 테스트 1.0.9 / 비공개 Alpha 1.0.8)를
  모두 중단해야 완전히 내려간다.

  > 게시 중단하면 "Android 16(API 36) 타겟" 정책 경고와 2026-08-31 기한은
  > 자동으로 무의미해진다. 별도 대응 불필요.

- [ ] **App Store** — App Store Connect → 앱 → 가격 및 사용 가능 여부 →
  판매 중단(Remove from Sale)

- [ ] **AdMob** — 광고 단위 비활성화 후 잔여 수익 지급 확인

---

## 4. 인프라 정리

- [ ] **Cloudflare Pages 프로젝트 삭제** (`output/` 정적 사이트)
- [ ] **Cloudflare Worker 삭제** — `kr-apt-doc-reader` (`wrangler.jsonc`)
- [ ] **DNS 레코드 정리** — 도메인을 당장 해지하지 않는다면 레코드만 제거
- [ ] **Firebase 프로젝트 삭제 또는 FCM 비활성화**

---

## 5. GitHub Secrets 폐기

자동화가 멈춰도 Secret은 레포에 남아 있다. 레포를 공개로 전환하거나
협업자를 추가할 계획이면 반드시 먼저 삭제할 것.

Settings → Secrets and variables → Actions

**LLM · 외부 API**
`GEMINI_API_KEY` · `OPENAI_API_KEY` · `PUBLIC_DATA_API_KEY`

**앱 서명 (유출 시 위험도 최상)**
`KEYSTORE_BASE64` · `KEYSTORE_STORE_PASSWORD` · `KEYSTORE_KEY_ALIAS` · `KEYSTORE_KEY_PASSWORD`
(+ `ANDROID_KEYSTORE_*` 별칭 4종)
`IOS_CERTIFICATE_CER_BASE64` · `IOS_CERTIFICATE_PASSWORD` · `IOS_PRIVATE_KEY_BASE64`
`IOS_PROVISIONING_PROFILE_BASE64` · `IOS_PROVISIONING_PROFILE_NAME` · `IOS_TEAM_ID`

> **주의**: Android 키스토어 원본(`aptnote-release.jks`)은 Secret을 지워도
> 별도로 백업해 두는 편이 좋다. 나중에 앱을 되살릴 경우 같은 키스토어가
> 없으면 기존 앱을 업데이트할 수 없다.

**스토어 · Firebase**
`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` · `APP_STORE_CONNECT_KEY_BASE64` ·
`APP_STORE_CONNECT_KEY_ID` · `APP_STORE_CONNECT_ISSUER_ID`
`FCM_SERVICE_ACCOUNT_JSON` · `FIREBASE_SERVICE_ACCOUNT_JSON` · `FIREBASE_TOKEN` ·
`FIREBASE_APP_ID` · `FIREBASE_ANDROID_APP_ID` · `GOOGLE_SERVICES_JSON*` 계열

**인프라 · 알림**
`CLOUDFLARE_API_TOKEN` · `CLOUDFLARE_ACCOUNT_ID` · `WORKER_ORIGIN` ·
`TELEGRAM_TOKEN` · `TELEGRAM_CHAT_ID` · `DISPATCH_TOKEN`

---

## 6. 레포 마무리 (선택)

- [ ] README 상단에 종료 안내 추가
- [ ] 레포 아카이브(읽기 전용 전환) — Settings → Archive this repository
- [ ] `output/posts/` 콘텐츠 백업이 필요하면 아카이브 전에 확보

---

## 알려진 미해결 사항 (복구하지 않고 종료함)

**입지분석 v3 회귀 6건** — 2026-08-22 생성분(`2026000342`, `2026000354`,
`2026000368`, `2026000372`, `2026000383`, `2026000388`)은 입지 분석이 구버전
템플릿 상태다.

원인: 해당 실행에서 Gemini 호출이 전부 실패했다. 본생성 Agent 2
(`gemini-3.1-flash-lite`)는 결정론적 폴백 템플릿으로 떨어졌고, v3 패치 스텝
(`gemini-3.1-pro-preview`)은 산출물을 하나도 만들지 못했다(6건 모두
`location_v3.json` 부재). 같은 실행에서 OpenAI 계열은 정상 동작했으므로
Gemini 한정 장애다. 키 무효화 또는 결제/할당량 소진이 유력하나, Actions 로그가
만료되어 확정하지 못했다.

이 실패가 조용히 넘어간 구조적 원인:
`codex-generate-pages.yml`의 v3 패치 스텝이 `set +e`로 감싸여 있어
`patch_posts_location_v3.py`가 exit 1로 끝나도 스텝은 success로 처리되고,
텔레그램 알림은 본생성 건수만 파싱한다. 서비스를 되살릴 경우 이 부분을
먼저 고쳐야 한다.

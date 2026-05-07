# apt-note Telegram Bot (Cloudflare Worker)

텔레그램에서 ✅/❌ 버튼이나 `/gen all` 명령으로 GitHub Actions 워크플로우를 트리거하는 웹훅.

## 흐름

```
Telegram (버튼 클릭 / 명령) → Cloudflare Worker → GitHub Actions API
```

| 입력 | 트리거되는 워크플로우 |
|------|----------------------|
| 수집 알림에서 ✅ 진행 버튼 (`callback_data=export_notice_urls`) | `codex-export-notice-urls.yml` |
| `/gen all` 메시지 | `codex-generate-pages.yml` |

## 사전 준비

### 1. Telegram 봇 생성
1. Telegram에서 [@BotFather](https://t.me/BotFather) 에게 `/newbot` 전송
2. 안내에 따라 이름 설정 → **봇 토큰** 발급
3. 만든 봇과 1:1 대화 시작 → 아무 메시지 한 번 전송
4. 다음 URL로 chat_id 확인:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   `result[].message.chat.id` 값이 chat_id (개인 채팅은 양수, 그룹은 음수)

### 2. GitHub PAT 발급
1. https://github.com/settings/tokens?type=beta → "Generate new token (Fine-grained)"
2. **Repository access**: `zeros1205/KR_APT_DOC_READER`
3. **Permissions** → Repository permissions → **Actions: Read and write**
4. 생성 후 `ghp_...` 토큰 보관 (한 번만 표시됨)

### 3. Cloudflare 계정
무료 Workers 플랜으로 충분. https://dash.cloudflare.com 가입.

## 배포

```bash
cd cloudflare-worker
npm install
npx wrangler login          # 브라우저 인증
npx wrangler secret put TELEGRAM_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler secret put GITHUB_PAT
npm run deploy
```

배포 후 출력되는 URL (예: `https://apt-note-telegram-bot.<account>.workers.dev`)을 복사.

## Telegram 웹훅 등록

```bash
curl -F "url=https://apt-note-telegram-bot.<account>.workers.dev" \
  https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook
```

응답이 `{"ok":true,"result":true,"description":"Webhook was set"}` 이면 성공.

확인:
```bash
curl https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo
```

## 동작 검증

1. 텔레그램에서 봇과 대화 시작 → `/help` 입력 → 사용 가이드 응답 수신
2. `/gen all` 입력 → "🚀 페이지 생성 워크플로우 시작" 응답 + GitHub Actions 실행 확인
3. `codex-collect-notices.yml` 수동 실행 → 신규 공고 ≥1건이면 ✅/❌ 버튼 메시지 수신 → ✅ 클릭 → export 워크플로우 자동 시작 확인

## 디버깅

```bash
npx wrangler tail
```
실시간 Worker 로그 확인. `dispatchWorkflow ... failed: 401` 등이 보이면 PAT 권한 문제.

## 보안

- `chat_id` 인증으로 등록된 사용자만 명령 실행 가능 (다른 사용자는 403)
- 모든 secrets는 Cloudflare Worker 환경변수로만 보관, 코드 미포함
- GitHub PAT는 Fine-grained 토큰으로 단일 저장소 + Actions 권한만 부여

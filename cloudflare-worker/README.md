# apt-note Telegram Bot (Cloudflare Worker)

텔레그램에서 ✅/❌ 버튼, `/gen all` 명령, 또는 PDF 첨부로 GitHub Actions 워크플로우를 트리거하는 웹훅.

## 흐름

```
Telegram (버튼 클릭 / 명령 / PDF 첨부) → Cloudflare Worker → GitHub Actions API
```

| 입력 | 트리거되는 워크플로우 |
|------|----------------------|
| 수집 알림에서 ✅ 진행 버튼 (`callback_data=export_notice_urls`) | `codex-export-notice-urls.yml` |
| `/gen all` 메시지 | `codex-generate-pages.yml` |
| PDF 파일 첨부 (공고와 자동/수동 매칭 후) | `codex-ingest-telegram-pdf.yml` → 내부에서 `codex-generate-pages.yml` 연쇄 실행 |

### PDF 첨부 자동 업로드

1. 사용자가 봇과의 채팅에 공고문 PDF 를 첨부.
2. Worker 는 파일 실물을 다루지 않고 `file_id`만 받는다 — Cloudflare Workers
   무료 플랜은 요청당 CPU 시간이 10ms 라 수 MB PDF 를 base64 인코딩해
   GitHub Contents API 로 커밋하는 작업을 감당하지 못하기 때문. 대신
   `output/notice_pending.json`(PDF 없는 대기 공고 목록, `export_notice_urls.py`
   가 매 실행마다 커밋)을 raw.githubusercontent.com 으로 읽어 파일명·캡션의
   공고번호(9~10자리) 또는 단지명으로 공고를 매칭한다.
3. 정확히 한 건으로 좁혀지면 바로 `codex-ingest-telegram-pdf.yml` 을
   dispatch. 매칭이 안 되거나 여러 건이면 인라인 버튼으로 후보를 보여주고
   사용자가 직접 고른다 (선택 대기 중인 `file_id` 는 KV 에 1시간 TTL 로 임시 보관).
4. `codex-ingest-telegram-pdf.yml` (Actions 러너, CPU/메모리 제약 없음) 이
   텔레그램에서 PDF 를 실제로 내려받아 `input/pdfs/` 에 커밋하고, 이어서
   `codex-generate-pages.yml` 을 `notice_id` 지정 + `limit=0` 으로 dispatch한다.
5. 20MB 를 넘는 파일은 텔레그램 봇 다운로드 상한(`getFile`)에 걸려 처리할
   수 없다 — Worker 가 이 경우 GitHub 웹 업로드 링크로 안내한다.

**사전 준비**: 저장소 Settings → Actions → General → Workflow permissions
을 **"Read and write permissions"** 로 설정해야 `codex-ingest-telegram-pdf.yml`
이 자체 `GITHUB_TOKEN` 으로 `codex-generate-pages.yml` 을 연쇄 dispatch 할 수 있다.
(PDF 커밋 자체는 이 설정과 무관하게 항상 동작하고, 이 권한이 없으면
페이지 생성만 텔레그램 알림을 보고 수동으로 실행하면 된다.)

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
4. 대기 중인 공고의 PDF 를 봇과의 채팅에 첨부 → "🔄 처리 중" 또는 후보 선택
   버튼 메시지 수신 확인 → `codex-ingest-telegram-pdf.yml` 실행 및
   `input/pdfs/` 커밋 확인 → 이어서 `codex-generate-pages.yml` 자동 실행 확인

## 디버깅

```bash
npx wrangler tail
```
실시간 Worker 로그 확인. `dispatchWorkflow ... failed: 401` 등이 보이면 PAT 권한 문제.

## 보안

- `chat_id` 인증으로 등록된 사용자만 명령 실행 가능 (다른 사용자는 403)
- 모든 secrets는 Cloudflare Worker 환경변수로만 보관, 코드 미포함
- GitHub PAT는 Fine-grained 토큰으로 단일 저장소 + Actions 권한만 부여

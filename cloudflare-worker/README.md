# apt-note Telegram Bot (Cloudflare Worker)

텔레그램에서 ✅/❌ 버튼, `/generate` 명령, 또는 PDF 첨부로 GitHub Actions 워크플로우를 트리거하는 웹훅.

## 흐름

```
Telegram (버튼 클릭 / 명령 / PDF 첨부) → Cloudflare Worker → GitHub Actions API
```

| 입력 | 트리거되는 워크플로우 |
|------|----------------------|
| 수집 알림에서 ✅ 진행 버튼 (`callback_data=export_notice_urls`) | `codex-export-notice-urls.yml` |
| `/generate` (또는 `/gen all`) 메시지 | `codex-generate-pages.yml` — 대기 전체 |
| `/generate <공고번호>` | `codex-generate-pages.yml` — 해당 공고만 (`notice_id` 지정) |
| `/generate <공고번호> force` | 위와 동일 + `include_processed=true` (이미 발행된 공고도 재생성) |
| PDF 파일 첨부 (공고와 자동/수동 매칭 후) | `codex-ingest-telegram-pdf.yml` → 내부에서 `codex-generate-pages.yml` 연쇄 실행 |

**운영 방식**: PDF 는 GitHub 웹 업로드(`input/pdfs/`)로 직접 올리고, 페이지
생성은 `/generate` 명령으로 실행하는 조합을 기본 흐름으로 가정한다. PDF
첨부 자동 매칭(아래)은 그대로 켜져 있지만 필수 경로는 아니다 — 안 써도 된다.

**주의**: `/generate`(공고번호 없이)는 `input/pdfs/` 에 실제로 커밋된 PDF가
있는 미발행 공고만 생성한다. 웹 업로드가 "Commit changes" 까지 완료되지
않았거나 경로가 다르면(`input/pdfs/` 가 아니거나 브랜치가 `main` 이
아니면) 아무것도 처리되지 않고 "성공 0건 / 실패 0건" 으로 끝난다 — 오류가
아니라 "처리할 PDF 없음"을 정확히 보고한 것이다. 업로드 자체가 됐는지
`github.com/<repo>/tree/main/input/pdfs` 에서 먼저 확인할 것.

### PDF 첨부 자동 업로드

1. 사용자가 봇과의 채팅에 공고문 PDF 를 첨부.
2. Worker 는 파일 실물을 다루지 않고 `file_id`만 받는다 — Cloudflare Workers
   무료 플랜은 요청당 CPU 시간이 10ms 라 수 MB PDF 를 base64 인코딩해
   GitHub Contents API 로 커밋하는 작업을 감당하지 못하기 때문. 대신
   `output/notice_pending.json`(PDF 없는 대기 공고 목록, `export_notice_urls.py`
   가 매 실행마다 커밋)을 raw.githubusercontent.com 으로 읽어 파일명·캡션의
   공고번호(9~10자리) 또는 단지명으로 공고를 매칭한다.
3. 공고번호(9~10자리)가 파일명/캡션에 그대로 있고 **대기 목록에도 있으면**
   확인 없이 바로 `codex-ingest-telegram-pdf.yml` 을 dispatch. 단지명 부분
   일치로만 좁혀진 경우(후보 정확히 1건이어도)는 이름 매칭의 오배정 위험
   때문에 **"맞나요?" 확인 버튼**을 한 번 거친다. 후보가 여러 건이거나
   전혀 못 찾으면 대기 공고 목록을 인라인 버튼으로 보여주고 직접 고르게 한다
   (선택 대기 중인 `file_id` 는 KV 에 1시간 TTL 로 임시 보관).
4. 공고번호는 있는데 대기 목록엔 없는 경우, `output/notice_status_index.json`
   (전체 공고 상태 인덱스, `export_notice_urls.py` 가 함께 커밋)으로 이유를
   구분해서 안내한다 — 이미 발행됨 / 이미 PDF 있음(교체 확인) / 청약홈에서
   삭제됨. 이 구분이 없으면 이미 처리된 공고의 PDF 를 실수로 재전송했을 때
   대기 목록에서 빠져 있으니 엉뚱한 다른 공고 후보가 뜨고, 잘못 고르면 그
   PDF 가 다른 공고에 잘못 배정될 수 있다.
5. `codex-ingest-telegram-pdf.yml` (Actions 러너, CPU/메모리 제약 없음) 이
   텔레그램에서 PDF 를 실제로 내려받아 `input/pdfs/` 에 커밋하고, 이어서
   `codex-generate-pages.yml` 을 `notice_id` 지정 + `limit=0` 으로 dispatch한다.
6. 20MB 를 넘는 파일은 텔레그램 봇 다운로드 상한(`getFile`)에 걸려 처리할
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
2. `/generate` 입력 → "🚀 페이지 생성 워크플로우 시작" 응답 + GitHub Actions 실행 확인
3. GitHub 웹으로 `input/pdfs/` 에 PDF 하나를 올린 뒤 `/generate <그 공고번호>`
   입력 → 해당 공고만 생성됐는지 Actions 로그로 확인
4. `codex-collect-notices.yml` 수동 실행 → 신규 공고 ≥1건이면 ✅/❌ 버튼 메시지 수신 → ✅ 클릭 → export 워크플로우 자동 시작 확인
5. (선택) 대기 중인 공고의 PDF 를 봇과의 채팅에 첨부 → "🔄 처리 중" 또는 후보 선택
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

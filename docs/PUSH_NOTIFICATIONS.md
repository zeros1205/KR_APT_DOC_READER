# FCM 푸시 알림 운영 가이드

본 문서는 청약노트(Apt Note) 모바일앱 FCM 푸시 알림 시스템의 구성 요소와 운영 절차를 기록한다.

## 아키텍처

```
codex-collect-notices.yml  (KST 08·11·15시 cron)
        ↓ 신규 공고 캐시 커밋
codex-generate-pages.yml   (별도 트리거 / Telegram /gen all)
        ↓ output/posts/{notice_id}/post_meta.json 생성
push-notifications.yml     (KST 10·17시 cron)
        ↓ scripts/build_push_payload.py 로 윈도우 안 신규 포스트 추출
        ↓ POST /push/dispatch (Cloudflare Worker)
Cloudflare Worker (cloudflare-worker/)
   ├─ /devices   : POST 등록 / DELETE 해지
   ├─ /push/dispatch : 디바이스별 타입 분기 + FCM v1 호출
   └─ KV DEVICES_KV : device:* / region:*:* / sent:*:*:*
```

## 발송 윈도우

- 오전 10시 (KST 10:00): `00:00:00 ≤ generated_at < 10:00:00` 신규 포스트
- 오후 17시 (KST 17:00): `10:00:00 ≤ generated_at < 17:00:00` 신규 포스트
- 동일 `notice_id`가 오전·오후 두 번 발송되지 않도록 `sent:{YYYYMMDD}:{notice_id}:{token}` 키 (TTL 48h) 사용

## 알림 타입 분기

| 타입 | 관심지역 설정 | 매칭 신규 공고 수 | 본문 | 클릭 라우팅 |
|-----|-------------|----------------|-----|-----------|
| 1 | 설정 | 1건 | `{지역} 신규 아파트 청약 공고를 확인해보세요.\n{단지명}` | 단지 포스트 |
| 2 | 설정 | 2건 이상 | `... {단지명} 외 N건` (N = 추가 건수) | 관심지역 탭 |
| 3 | 미설정 | 1건 | `오늘 등록된 신규 ... 확인해보세요.\n{단지명}` | 단지 포스트 |
| 4 | 미설정 | 2건 이상 | `... {단지명} 외 N건` | 메인 |

대표 단지: `total_households desc`, 동률은 `generated_at desc`.
관심지역 매칭 0건인 디바이스는 발송 제외.

## 필요한 시크릿

### Cloudflare Worker (`wrangler secret put`)
- `DISPATCH_TOKEN` : GitHub Actions 인증용 임의 토큰
- `FCM_PROJECT_ID` : Firebase 프로젝트 ID
- `FCM_SERVICE_ACCOUNT_JSON` : Service Account 키 JSON 전문

### KV 네임스페이스
```bash
wrangler kv namespace create DEVICES_KV
wrangler kv namespace create DEVICES_KV --preview
# wrangler.toml 의 REPLACE_WITH_* 자리에 id 채우기
```

### GitHub Actions Secret (push-notifications.yml)
- `WORKER_ORIGIN` : `https://apt-note-tg-bot.<account>.workers.dev`
- `DISPATCH_TOKEN` : Worker 와 동일한 값

### 모바일앱 빌드 시
- (선택) `VITE_WORKER_ORIGIN` 환경변수 — 기본값은 api.ts 의 상수

### Firebase 콘솔
- Android : `google-services.json` → CI `GOOGLE_SERVICES_JSON_BASE64`
- iOS : `GoogleService-Info.plist` + APNs 인증키(.p8) 업로드 → Apple 개발자 계정 승인 후 진행
- Cloud Messaging API 활성화 (HTTP v1)

## 검증

```bash
# 1. payload 생성 단위 테스트
python3 -m pytest tests/test_build_push_payload.py -v

# 2. 특정 날짜로 dry-run 페이로드 확인
python3 scripts/build_push_payload.py --window=morning --date=2026-04-29 --dry-run

# 3. Worker 로컬 실행
cd cloudflare-worker
npx wrangler dev

# 4. GitHub Actions 수동 dry-run
#    Actions → "FCM 푸시 알림 발송" → Run workflow → dry_run=true
```

`dry_run=true` 인 경우 Worker 응답에 `plans` 배열이 포함되어 디바이스별 어떤 알림이 발송될 예정인지 확인할 수 있다(토큰은 마스킹).

## iOS 진행 메모

현재 Apple 개발자 계정 심사 중이라 1차 출시는 Android 단독.
iOS 코드/설정 파일(AppDelegate.swift, Podfile)은 같은 PR에 미리 포함했고,
계정 승인 후:
1. Firebase Console 에 iOS 앱(`app.aptnote.mobile`) 등록
2. APNs 인증키(.p8) 업로드, Team ID/Key ID 입력
3. `GoogleService-Info.plist` 를 `mobile-app/ios/App/App/` 에 배치 (CI 시크릿 디코드)
4. `cd mobile-app/ios/App && pod install`
5. 실기기에서 4가지 타입 클릭 라우팅 검증

# iOS 배포용 GitHub Secrets 설정 가이드

`mobile-app-ios-release.yml` 워크플로우 실행 전 GitHub Repository Settings → Secrets and variables → Actions 에서 아래 secrets를 추가하세요.

---

## 필수 Secrets

### 1. 코드 서명 인증서 (Distribution Certificate)

#### `IOS_CERTIFICATE_P12_BASE64`
Apple Developer에서 iOS Distribution Certificate를 내보낸 `.p12` 파일 base64 인코딩 값.

```bash
# Keychain Access → 인증서 오른쪽 클릭 → 내보내기 → .p12 저장
# 이후 터미널에서:
base64 -i Certificates.p12 | pbcopy
# 클립보드에 복사됨 → GitHub Secret에 붙여넣기
```

#### `IOS_CERTIFICATE_PASSWORD`
`.p12` 파일 내보낼 때 설정한 비밀번호.

---

### 2. 프로비저닝 프로파일 (App Store Distribution)

#### `IOS_PROVISIONING_PROFILE_BASE64`
App Store 배포용 프로비저닝 프로파일(`.mobileprovision`) base64 인코딩 값.

**생성 방법**:
1. [Apple Developer](https://developer.apple.com) → Certificates, Identifiers & Profiles
2. Profiles → + 버튼
3. Distribution → App Store 선택
4. App ID: `app.aptnote.mobile` 선택
5. Distribution Certificate 선택
6. 프로파일 이름: `AptNote AppStore` 입력
7. Generate → Download → `.mobileprovision` 파일 저장

```bash
base64 -i AptNote_AppStore.mobileprovision | pbcopy
```

#### `IOS_PROVISIONING_PROFILE_NAME`
프로비저닝 프로파일 이름 (Xcode에서 표시되는 이름).
```
AptNote AppStore
```

---

### 3. Apple Developer Team

#### `IOS_TEAM_ID`
Apple Developer 계정의 Team ID.

**확인 방법**: [Apple Developer](https://developer.apple.com) → Account → Membership → Team ID
```
예시: ABCDE12345
```

---

### 4. App Store Connect API (TestFlight 업로드용)

#### `APP_STORE_CONNECT_KEY_ID`
App Store Connect API 키 ID.

**생성 방법**:
1. [App Store Connect](https://appstoreconnect.apple.com) → Users and Access → Integrations → App Store Connect API
2. + 버튼 → Name: `GitHub Actions`, Role: `Developer`
3. Key ID 복사

#### `APP_STORE_CONNECT_ISSUER_ID`
App Store Connect 발급자 ID (API 키 목록 상단에 표시).

#### `APP_STORE_CONNECT_KEY_BASE64`
다운로드한 `.p8` 파일 base64 인코딩 값. (한 번만 다운로드 가능!)

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy
```

---

### 5. Firebase (선택 사항)

#### `IOS_GOOGLE_SERVICES_PLIST_BASE64`
Firebase iOS 설정 파일 `GoogleService-Info.plist` base64 인코딩 값.

**생성 방법**:
1. [Firebase Console](https://console.firebase.google.com) → 프로젝트 → Project Settings
2. iOS 앱 추가 (`app.aptnote.mobile`)
3. `GoogleService-Info.plist` 다운로드

```bash
base64 -i GoogleService-Info.plist | pbcopy
```

> 이미 Android용 Firebase 설정이 있다면 iOS 앱을 같은 프로젝트에 추가하면 됩니다.

---

## Secrets 요약 체크리스트

| Secret 이름 | 필수 여부 | 설명 |
|------------|---------|------|
| `IOS_CERTIFICATE_P12_BASE64` | ✅ 필수 | Distribution Certificate (.p12) |
| `IOS_CERTIFICATE_PASSWORD` | ✅ 필수 | .p12 비밀번호 |
| `IOS_PROVISIONING_PROFILE_BASE64` | ✅ 필수 | App Store 프로비저닝 프로파일 |
| `IOS_PROVISIONING_PROFILE_NAME` | ✅ 필수 | 프로파일 이름 |
| `IOS_TEAM_ID` | ✅ 필수 | Apple Developer Team ID |
| `APP_STORE_CONNECT_KEY_ID` | ✅ 필수 | API 키 ID (TestFlight) |
| `APP_STORE_CONNECT_ISSUER_ID` | ✅ 필수 | 발급자 ID (TestFlight) |
| `APP_STORE_CONNECT_KEY_BASE64` | ✅ 필수 | .p8 키 파일 (TestFlight) |
| `IOS_GOOGLE_SERVICES_PLIST_BASE64` | ⚪ 선택 | Firebase iOS 설정 |

---

## 워크플로우 실행 방법

1. GitHub → **Actions** 탭
2. **"Build Signed Mobile App for TestFlight"** 선택
3. **Run workflow** 버튼
4. 입력값 확인:
   - `source_ref`: `main` (또는 빌드할 브랜치)
   - `version_name`: `1.0.0`
   - `build_number`: `1` (이전 TestFlight 빌드보다 높아야 함)
   - `upload_to_testflight`: ✅ 체크
5. **Run** 클릭

**소요 시간**: 약 20~30분 (CocoaPods 설치 + Xcode 빌드 + TestFlight 업로드 포함)

---

## 처음 배포 전 로컬에서 할 일 (Mac 필수)

```bash
# 1. iOS 플랫폼 추가 (최초 1회)
cd mobile-app
npm run build
npx cap add ios      # ios/ 폴더 생성
npx cap sync ios

# 2. CocoaPods 설치
cd ios/App
pod install

# 3. Xcode에서 한 번 열어서 서명 설정 확인
cd ../..
npx cap open ios
# Xcode → Signing & Capabilities → Team 선택

# 4. 시뮬레이터에서 테스트
# Xcode → 시뮬레이터 선택 → ⌘+R

# 5. 실기기 테스트 후 GitHub Actions로 TestFlight 빌드
```

---

## 주의사항

- `IOS_CERTIFICATE_P12_BASE64` — Distribution Certificate 사용 (Development 아님)
- `APP_STORE_CONNECT_KEY_BASE64` (.p8) — 생성 직후 단 한 번만 다운로드 가능. 분실 시 재생성 필요
- `build_number` — TestFlight에 올릴 때마다 반드시 증가해야 함 (같은 번호 재업로드 불가)
- `IOS_PROVISIONING_PROFILE_BASE64` — 인증서 갱신 시 프로파일도 함께 재생성 필요 (1년 유효)

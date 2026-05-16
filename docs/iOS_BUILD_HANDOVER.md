# iOS 앱 빌드 워크플로우 인수인계 문서

## 개요

이 문서는 **정과장의 청약노트** iOS 앱의 클라우드 기반 자동 빌드 시스템 구축에 대한 인수인계 문서입니다.

- **앱 ID**: `app.aptnote.mobile`
- **프레임워크**: React 19 + Capacitor 7
- **빌드 환경**: GitHub Actions (macOS-latest runner)
- **배포 방식**: TestFlight 자동 업로드
- **Mac 필요 여부**: ❌ (모든 빌드가 클라우드에서 진행)

---

## 시스템 아키텍처

```
[Windows/Mac PC] → [GitHub Push]
                       ↓
              [GitHub Actions macOS Runner]
                       ↓
                  ┌────────────┐
                  │ 1. 웹 빌드  │ (npm run build)
                  │ 2. 동기화   │ (npx cap sync ios)
                  │ 3. CocoaPods│ (pod install)
                  │ 4. 서명     │ (인증서/프로파일 적용)
                  │ 5. Archive  │ (xcodebuild)
                  │ 6. Export   │ (IPA 생성)
                  │ 7. 업로드   │ (xcrun altool)
                  └────────────┘
                       ↓
                  [TestFlight]
                       ↓
                  [App Store]
```

---

## GitHub Actions 워크플로우

### 1. Setup iOS Platform (`.github/workflows/setup-ios-platform.yml`)

**목적**: iOS 플랫폼 최초 1회 자동 생성

**실행 방법**: Actions 탭 → "Setup iOS Platform" → Run workflow

**기능**:
- `npx cap add ios` 실행
- CocoaPods 의존성 설치
- `mobile-app/ios/` 폴더를 main 브랜치에 자동 커밋

**조건**: `mobile-app/ios/` 폴더가 없을 때만 실행됨 (멱등성)

---

### 2. Build Signed Mobile App for TestFlight (`.github/workflows/mobile-app-ios-release.yml`)

**목적**: TestFlight 빌드 + 업로드

**실행 방법**: Actions 탭 → "Build Signed Mobile App for TestFlight" → Run workflow

**입력값**:
| 항목 | 기본값 | 설명 |
|------|--------|------|
| `source_ref` | `main` | 빌드할 git 브랜치/태그 |
| `version_name` | `1.0.0` | 앱 버전 (x.y.z 형식) |
| `build_number` | `1` | 빌드 번호 (TestFlight에서 매번 증가 필요) |
| `upload_to_testflight` | `true` | TestFlight 업로드 여부 |

**소요 시간**: 약 20~30분

---

## GitHub Secrets 설정 (10개)

| Secret 이름 | 설명 | 발급처 |
|------------|------|--------|
| `IOS_CERTIFICATE_CER_BASE64` | Distribution Certificate (.cer base64) | Apple Developer → Certificates |
| `IOS_PRIVATE_KEY_BASE64` | OpenSSL로 생성한 private.key (base64) | 로컬 OpenSSL 생성 |
| `IOS_CERTIFICATE_PASSWORD` | `.p12` 파일 export 비밀번호 | 직접 설정 |
| `IOS_PROVISIONING_PROFILE_BASE64` | App Store 프로비저닝 프로파일 (base64) | Apple Developer → Profiles |
| `IOS_PROVISIONING_PROFILE_NAME` | 프로파일 이름 (예: `AptNote AppStore`) | Apple Developer → Profiles |
| `IOS_TEAM_ID` | Apple Developer Team ID | Apple Developer → Membership |
| `APP_STORE_CONNECT_KEY_ID` | App Store Connect API Key ID | App Store Connect → Users → API |
| `APP_STORE_CONNECT_ISSUER_ID` | App Store Connect Issuer ID | App Store Connect → Users → API |
| `APP_STORE_CONNECT_KEY_BASE64` | App Store Connect API `.p8` 파일 (base64) | App Store Connect → Users → API |
| `IOS_GOOGLE_SERVICES_PLIST_BASE64` | Firebase iOS 설정 (선택사항) | Firebase Console |

⚠️ **기존 `IOS_CERTIFICATE_P12_BASE64`는 사용하지 않음** (Windows에서 만든 .p12 호환성 문제로 .cer + .key 방식으로 변경)

---

## 사전 준비 사항 (필수)

### 0단계: App Store Connect에 앱 등록
TestFlight 업로드 전에 반드시 앱이 App Store Connect에 등록되어 있어야 함.

1. [App Store Connect](https://appstoreconnect.apple.com) → **My Apps** → **+** → **New App**
2. 입력:
   - Platforms: `iOS`
   - Name: `정과장의 청약노트`
   - Primary Language: `Korean`
   - Bundle ID: `app.aptnote.mobile` (Apple Developer에서 생성한 App ID)
   - SKU: `aptnote-ios-001` (임의 식별자)
   - User Access: `Full Access`

⚠️ 이 단계를 건너뛰면 TestFlight 업로드 시 401 인증 실패 발생

---

## 인증서 발급 절차 (Mac 없이)

### 1단계: CSR 생성 (Git Bash on Windows)
```bash
openssl req -new -newkey rsa:2048 -nodes \
  -out CertificateSigningRequest.certSigningRequest \
  -keyout private.key
# Common Name: app.aptnote.mobile
```

### 2단계: Apple Developer에서 인증서 발급
1. Certificates, Identifiers & Profiles → Certificates → +
2. **Apple Distribution** 선택
3. CSR 파일 업로드 → 다운로드 (`distribution.cer`)

### 3단계: App ID 생성
1. Identifiers → +
2. **App IDs** → **App** 선택
3. Description: `AptNote Mobile`, Bundle ID: `app.aptnote.mobile`

### 4단계: 프로비저닝 프로파일 생성
1. Profiles → + → **App Store** 선택
2. App ID: `app.aptnote.mobile`
3. Certificate 선택
4. Profile Name: `AptNote AppStore`
5. 다운로드 (`AptNote_AppStore.mobileprovision`)

### 5단계: App Store Connect API 키
1. Users and Access → Integrations → App Store Connect API → +
2. Name: `GitHub Actions`, **Access: `App Manager`** ⚠️
3. Key ID, Issuer ID 복사
4. `.p8` 파일 다운로드 (1회만 가능, 분실 시 새 키 생성 필요)

⚠️ **Access 권한 주의**: `Developer`로 설정하면 TestFlight 업로드 권한 부족으로 401 에러 발생. 반드시 **App Manager** 또는 더 높은 권한 부여.

### 6단계: Base64 인코딩 (Git Bash)
```bash
base64 -w 0 -i distribution.cer | clip          # IOS_CERTIFICATE_CER_BASE64
base64 -w 0 -i private.key | clip               # IOS_PRIVATE_KEY_BASE64
base64 -w 0 -i AptNote_AppStore.mobileprovision | clip  # IOS_PROVISIONING_PROFILE_BASE64
base64 -w 0 -i AuthKey_*.p8 | clip              # APP_STORE_CONNECT_KEY_BASE64
```

---

## 핵심 기술 결정

### 1. Windows에서 .p12 생성 불가 → .cer + .key 별도 저장
**문제**: Windows OpenSSL로 만든 `.p12` 파일은 macOS Keychain에서 import 실패 ("MAC verification failed")

**해결**: `.cer`와 `.key` 파일을 별도로 GitHub Secret에 저장 → macOS runner에서 직접 `.p12` 생성

```bash
# 워크플로우 내부
openssl x509 -in cert.cer -inform DER -out cert.pem -outform PEM
openssl pkcs12 -export -in cert.pem -inkey private.key -out cert.p12 ...
```

### 2. Pods 타겟 서명 비활성화
**문제**: `xcodebuild`의 `PROVISIONING_PROFILE` 옵션이 Pods 타겟 (Capacitor 라이브러리)에 전파되어 archive 실패

```
error: Capacitor does not support provisioning profiles
error: CapacitorPreferences does not support provisioning profiles
...
```

**해결 (이중 방어)**:

**(A) Podfile post_install hook** (`mobile-app/ios/App/Podfile`):
```ruby
post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings.delete('PROVISIONING_PROFILE_SPECIFIER')
      config.build_settings.delete('PROVISIONING_PROFILE')
      config.build_settings['CODE_SIGNING_REQUIRED'] = 'NO'
      config.build_settings['CODE_SIGNING_ALLOWED'] = 'NO'
    end
  end
end
```

**(B) App 타겟의 project.pbxproj 직접 수정** (워크플로우 step):
```ruby
# ruby + xcodeproj gem 사용
project.targets.each do |target|
  next unless target.name == 'App'
  target.build_configurations.each do |config|
    config.build_settings['CODE_SIGN_STYLE'] = 'Manual'
    config.build_settings['DEVELOPMENT_TEAM'] = ENV['TEAM_ID']
    config.build_settings['PROVISIONING_PROFILE_SPECIFIER'] = ENV['PROFILE_NAME']
    config.build_settings['CODE_SIGN_IDENTITY'] = 'iPhone Distribution'
  end
end
```

**(C) xcodebuild 명령에서 서명 옵션 제거**:
```bash
# 기존 (실패): PROVISIONING_PROFILE이 모든 타겟에 전파됨
xcodebuild archive ... PROVISIONING_PROFILE="$PROFILE_UUID"

# 수정 후 (성공): 깨끗한 archive, 서명 정보는 project.pbxproj에서 가져옴
xcodebuild archive \
  -workspace App.xcworkspace \
  -scheme App \
  -configuration Release \
  -archivePath "$RUNNER_TEMP/App.xcarchive" \
  -destination "generic/platform=iOS"
```

---

## 빌드 단계 상세

`mobile-app-ios-release.yml`의 주요 단계:

1. **Checkout source** - 코드 체크아웃
2. **Validate iOS secrets** - 필수 secret 확인
3. **Set up Node.js** - Node 22 설치
4. **Build web shell** - `npm run build` (Vite)
5. **Add Capacitor iOS platform** - iOS 폴더 없으면 추가
6. **Sync Capacitor iOS project** - `npx cap sync ios`
7. **Install CocoaPods** - `pod install --repo-update`
8. **Import signing certificate** - macOS에서 `.cer` + `.key` → `.p12` → keychain
9. **Install provisioning profile** - `.mobileprovision` 설치, UUID 추출
10. **Set version in Xcode project** - `agvtool`로 버전 설정
11. **Configure App target signing** - ruby + xcodeproj gem으로 project.pbxproj 수정
12. **Build and archive** - `xcodebuild archive`
13. **Export IPA** - `xcodebuild -exportArchive` (ExportOptions.plist)
14. **Verify IPA** - SHA256 체크섬
15. **Upload to TestFlight** - `xcrun altool --upload-app`
16. **Upload IPA artifact** - GitHub Actions에 IPA 보관 (30일)

---

## 트러블슈팅

### "MAC verification failed during PKCS12 import"
- **원인**: Windows에서 만든 `.p12`가 macOS에서 인식 안 됨
- **해결**: `.cer` + `.key` 방식으로 변경 (이미 적용됨)

### "App requires a provisioning profile"
- **원인**: 프로비저닝 프로파일이 keychain에 설치 안 됨 또는 매칭 실패
- **확인**: `Install provisioning profile` 단계 로그에서 UUID 출력 확인
- **체크**: GitHub Secret `IOS_PROVISIONING_PROFILE_BASE64`, `IOS_PROVISIONING_PROFILE_NAME` 값

### "Capacitor does not support provisioning profiles"
- **원인**: xcodebuild의 서명 옵션이 Pods에 전파
- **해결**: Podfile post_install hook + xcodebuild 옵션 제거 (이미 적용됨)

### "Missing IOS_xxx secret"
- **원인**: GitHub Secret 누락
- **해결**: Repository Settings → Secrets → 누락된 Secret 추가

### Archive Failed (xcpretty가 에러 감춤)
- **확인**: `xcpretty` 제거 후 전체 로그 확인 (이미 적용됨)

### "exportArchive App.app requires a provisioning profile"
- **원인**: ExportOptions.plist에 서명 정보(signingStyle, certificate, provisioningProfiles) 누락
- **해결**: ExportOptions.plist에 manual signing 정보 추가 (이미 적용됨)

### TestFlight Upload "401 Unauthorized" / "Failed to load AuthKey file"
- **원인 1**: `.p8` 파일이 `~/private_keys/AuthKey_${KEY_ID}.p8` 표준 경로에 없음
  - **해결**: 워크플로우에서 자동 저장됨 (이미 적용)
- **원인 2**: App Store Connect API 키 권한 부족 (`Developer`로는 부족)
  - **해결**: API 키 권한을 **`App Manager`** 이상으로 변경
- **원인 3**: App Store Connect에 앱이 등록되지 않음
  - **해결**: My Apps에서 새 앱 생성 (Bundle ID: `app.aptnote.mobile`)
- **원인 4**: `APP_STORE_CONNECT_KEY_ID` / `APP_STORE_CONNECT_ISSUER_ID` 값 오타
  - **해결**: GitHub Secret 재등록 (값을 다시 볼 수 없으니 의심되면 그냥 재등록)

### "SDK version issue. This app was built with the iOS X SDK. All iOS apps must be built with the iOS 26 SDK or later"
- **원인**: GitHub Actions의 `macos-latest` runner는 Xcode 16.x (iOS 18.5 SDK) 사용
- **해결**: `runs-on: macos-26` 사용 (Xcode 26 / iOS 26 SDK 포함) - 이미 적용됨

---

## 운영 체크리스트

### 매 빌드마다
- [ ] `build_number`를 이전 빌드보다 +1 증가
- [ ] `version_name` 확인 (변경 시 App Store Connect에 동기화됨)

### 인증서 갱신 (1년마다)
- [ ] Apple Developer에서 새 Distribution Certificate 발급
- [ ] `IOS_CERTIFICATE_CER_BASE64` Secret 업데이트
- [ ] 프로비저닝 프로파일도 함께 재생성
- [ ] `IOS_PROVISIONING_PROFILE_BASE64` 업데이트

### App Store Connect API 키 분실 시
- [ ] 새 API 키 생성 (Access: **App Manager** ⚠️)
- [ ] `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_KEY_BASE64` 모두 업데이트

### GitHub Secret 값 재확인 불가
- GitHub Secret은 보안상 저장 후 **값을 볼 수 없음** (정상 동작)
- "Update secret" 클릭 시 빈칸으로 표시되는 것은 정상
- 값 확인 필요 시 **새로 등록**하는 것이 유일한 방법


---

## 파일 위치

| 파일 | 역할 |
|------|------|
| `.github/workflows/setup-ios-platform.yml` | iOS 플랫폼 최초 생성 |
| `.github/workflows/mobile-app-ios-release.yml` | TestFlight 빌드 + 업로드 |
| `mobile-app/ios/App/Podfile` | CocoaPods 의존성 + post_install hook |
| `mobile-app/ios/App/App.xcodeproj/` | Xcode 프로젝트 (워크플로우에서 동적 수정) |
| `mobile-app/capacitor.config.ts` | Capacitor 설정 (iOS-specific 옵션 포함) |
| `mobile-app/src/App.tsx` | 플랫폼별 앱스토어 URL 라우팅 |
| `docs/iOS_GITHUB_SECRETS_GUIDE.md` | Secrets 설정 가이드 |
| `docs/iOS_APP_DEVELOPMENT_PLAN_v2.md` | 개발 계획서 |

---

## 비용 및 자원

- **Apple Developer Program**: $99/년 (필수)
- **GitHub Actions**: macOS runner 분당 과금 (Public repo는 무료)
- **개발 기간**: 약 2.5~3주 (1인 개발 기준)
- **재사용률**: 99% (기존 Android Capacitor 앱 코드 그대로 사용)

---

## 참고 자료

- [Capacitor iOS 가이드](https://capacitorjs.com/docs/ios)
- [Apple Developer Documentation](https://developer.apple.com/documentation/)
- [App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi)
- [GitHub Actions macOS Runner](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)

---

## 작업 이력 (Pull Requests)

| PR # | 내용 |
|------|------|
| #58 | iOS 개발 계획 v2 수립 |
| #62 | setup-ios-platform.yml YAML 문법 수정 (3건) |
| #63 | `cancel_in_progress` → `cancel-in-progress` 수정 |
| #64 | `pull-requests: write` 권한 추가 |
| #88 | `.cer` + `.key` 방식으로 변경 (Windows .p12 호환성 문제 해결) |
| #89 | DER → PEM 변환 추가 |
| #90 | 프로비저닝 프로파일 UUID 사용 |
| #91 | xcpretty 제거 (에러 로그 가시화) |
| #92 | Pods 서명 비활성화 + App 타겟 project.pbxproj 동적 수정 |
| #93 | ExportOptions.plist에 manual signing 정보 추가 |
| #94 | `.p8` 파일을 `~/private_keys/AuthKey_${KEY_ID}.p8` 표준 경로에 저장 |
| #95 | `macos-26` runner 사용 (Xcode 26 / iOS 26 SDK) + 트러블슈팅 문서 보강 |

---

## 빌드 단계별 통과 확인 체크리스트

각 빌드 시도 후 어디까지 통과했는지 확인하는 방법:

| 단계 | 성공 시 로그 메시지 |
|------|-------------------|
| 1. 인증서 import | `1 certificate imported.` |
| 2. 프로비저닝 프로파일 설치 | `Installed provisioning profile UUID: xxx-xxx-xxx` |
| 3. App 타겟 서명 설정 | `App target signing configured.` |
| 4. Archive | `** ARCHIVE SUCCEEDED **` |
| 5. Export IPA | `IPA_PATH=...` 환경변수 설정됨 |
| 6. IPA 검증 | sha256 체크섬 출력 |
| 7. TestFlight 업로드 | `p8 private key loaded from '~/private_keys/...'`, 이후 인증 성공 |

각 단계에서 실패 시 트러블슈팅 섹션의 해당 항목 참조.

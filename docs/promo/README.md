# 청약노트 스토어 등록 프로모 이미지

NotebookLM의 Play Store 프로모 카드 스타일을 차용한, 정과장의 청약노트 앱 홍보용 이미지 세트.

## 출력 경로

| 스토어 | 사이즈 | 디렉터리 |
|-------|--------|---------|
| Google Play Store | 1080 × 1920 (9:16) | `out/play/` |
| Apple App Store — iPhone 6.7" (필수) | 1290 × 2796 | `out/ios/` |
| Apple App Store — iPad 12.9"/13" Pro | 2048 × 2732 (3:4) | `out/ipad/` |

각 세트는 동일한 5장으로 구성됩니다.

| 파일 | 내용 |
|------|------|
| `01_intro.png` | 텍스트 인트로 ("복잡한 분양 공고를 정과장이 깔끔히 정리해드려요") |
| `02_regions.png` | 관심 지역 선택 화면 |
| `03_home.png` | 홈/분양 정보 리스트 |
| `04_notify.png` | 알림 권한 안내 |
| `05_favorites.png` | 즐겨찾기 |

## 디자인 토큰

- 배경: `#FAF6F0` (앱 브랜드 크림 톤)
- 본문 폰트: **Pretendard** (Black / ExtraBold / Bold) — `docs/promo/assets/fonts/` 에 동봉
- 키워드 그라데이션: 오렌지 `#F58A46` → 딥레드 `#D85032`
- 이모지: Noto Color Emoji (시스템 폰트)

## 재생성

```bash
python3 scripts/build_promo_images.py
```

원본 스크린샷은 `docs/promo/screenshots/` 에 있으며, 새 스크린샷으로 교체한 뒤 위 명령을 다시 실행하면 두 세트가 동시에 갱신됩니다.

## 카피 톤

- 마케팅 담당자가 대화하듯 자연스럽게 (CLAUDE.md 콘텐츠 톤앤매너 준수)
- 각 헤드라인에 핵심 키워드 하나를 브랜드 그라데이션으로 강조 (NotebookLM 패턴)
- 이모지는 헤드라인 끝에 배치하여 시각적 액센트로 활용

문구를 손보고 싶을 때는 `scripts/build_promo_images.py` 의 `build_set()` 안 `HeadlineLine([...])` 리스트만 수정하면 됩니다.

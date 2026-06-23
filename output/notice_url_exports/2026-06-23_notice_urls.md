# 청약홈 상세페이지 URL · 수동 입력 시트

- 생성일: 2026-06-23
- 대상 공고: 9건  (입력 완료 0건 / 대기 9건)
- PDF 업로드 폴더: `input/pdfs/`

## 입력 안내

1. 청약홈 상세 페이지에서 PDF 모집공고문을 받아 `input/pdfs/` 에 업로드.
2. 아래 표의 8개 메타 필드를 채우고 커밋. 자동 추출된 값이 prefilled 되어 있으니 검토만 하면 됩니다.
3. 8필드가 모두 채워진 행은 다음 빌드에서 `상태` 컬럼이 `✅` 로 갱신됩니다.
4. `codex-페이지 생성` 워크플로우 실행 시 모든 행이 `✅` 인지 검증 후 진행합니다.

### 필드 형식

- **규제지역**: `투기과열지구` / `청약과열지역` / `조정대상지역` / `비규제지역`
- **재당첨 / 전매 / 거주의무**: 예 `10년`, `없음`
- **분양가상한제**: `적용` / `미적용`
- **계약금 / 중도금 / 잔금**: 비율(예 `10%` `60%` `30%`). 숫자만 입력해도 자동으로 % 가 붙음. 세 값 합계 100% 권장

| 공고번호 | 단지명 | 모집공고일 | 당첨자 발표일 | 청약홈 링크 | 권장 PDF 파일명 | 규제지역 | 재당첨 | 전매 | 거주의무 | 분양가상한제 | 계약금 | 중도금 | 잔금 | 상태 |
|---|---|---:|---:|---|---|---|---|---|---|---|---:|---:|---:|:-:|
| 2026000234 | 에코델타시티 중흥S-클래스 리버시티 | 2026-06-19 | 2026-07-07 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000234&pblancNo=2026000234 | `2026000234 에코델타시티 중흥S-클래스 리버시티 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000241 | 드파인 아르티아 | 2026-06-19 | 2026-07-08 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000241&pblancNo=2026000241 | `2026000241 드파인 아르티아 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000263 | 신문 대상 웰라움 라시엘 | 2026-06-19 | 2026-07-07 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000263&pblancNo=2026000263 | `2026000263 신문 대상 웰라움 라시엘 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000270 | 김해 신문 센트럴 아이파크 | 2026-06-19 | 2026-07-07 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000270&pblancNo=2026000270 | `2026000270 김해 신문 센트럴 아이파크 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000272 | 함안가야 휴니온아르떼 | 2026-06-22 | 2026-07-10 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000272&pblancNo=2026000272 | `2026000272 함안가야 휴니온아르떼 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000273 | 펜타힐즈 더블유 1단지 | 2026-06-19 | 2026-07-07 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000273&pblancNo=2026000273 | `2026000273 펜타힐즈 더블유 1단지 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000275 | 장위 푸르지오 마크원 | 2026-06-19 | 2026-07-08 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000275&pblancNo=2026000275 | `2026000275 장위 푸르지오 마크원 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000278 | 양주 회천지구 A-8BL 로제비앙 엘가 | 2026-06-22 | 2026-07-10 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000278&pblancNo=2026000278 | `2026000278 양주 회천지구 A-8BL 로제비앙 엘가 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |
| 2026000281 | 이천 서희스타힐스 SKY(조합원 취소분) | 2026-06-22 | 2026-07-09 | https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo=2026000281&pblancNo=2026000281 | `2026000281 이천 서희스타힐스 SKY(조합원 취소분) 입주자모집공고문.pdf` | _ | _ | _ | _ | _ | _ | _ | _ | ☐ |

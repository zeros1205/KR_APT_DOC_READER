"""
patch_posts4_eligibility.py — 청약 신청자격 섹션 삽입
기존 11개 포스트 (구 템플릿 v3.0) 에 신규 섹션 추가
  - SECTION 4 → 04 · 청약 신청자격 (新)
  - 기존 04 → 05 · 자금 계획
  - 기존 05 → 06 · 자주 묻는 질문

실행: python patch_posts4_eligibility.py
"""
import re, json
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

# ── 색상 상수 (구 템플릿 intercom 테마 기준) ──────────────────
C_ACCENT   = "#CC5F3F"
C_TEXT     = "#2C2825"
C_TEXT2    = "#6A635C"
C_SURFACE  = "#F5F2ED"
C_BORDER   = "#DED9D1"
C_ACCENT_L = "#FDEEE8"
RADIUS_MD  = "10px"
RADIUS_SM  = "6px"
RADIUS_PILL= "24px"


def _eligibility_html(data: dict) -> str:
    """신청자격 섹션 HTML 빌드"""

    # ── 특별공급 카드 ──
    sp_cards = ""
    for sp in data.get("eligibility_special", []):
        type_name = sp.get("type_name", "")
        quota     = sp.get("quota", "")
        reqs      = sp.get("requirements", [])
        quota_html = (
            f'<span style="font-size:11px;font-weight:600;background:{C_ACCENT_L};'
            f'color:{C_ACCENT};padding:2px 8px;border-radius:{RADIUS_PILL};margin-left:6px;">'
            f'{quota}</span>'
        ) if quota else ""
        req_items = "".join(
            f'<li style="font-size:14px;color:{C_TEXT2};line-height:1.7;padding:2px 0;">{r}</li>'
            for r in reqs
        )
        sp_cards += (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{C_SURFACE};border:1px solid {C_BORDER};'
            f'border-radius:{RADIUS_MD};padding:16px 18px;">'
            f'<div style="font-size:14px;font-weight:800;color:{C_TEXT};margin-bottom:10px;">'
            f'{type_name}{quota_html}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{req_items}</ul>'
            f'</div>'
        )

    if sp_cards:
        special_block = (
            f'<div style="font-size:13px;font-weight:700;color:{C_ACCENT};'
            f'letter-spacing:0.5px;margin-bottom:12px;">특별공급</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:28px;">'
            f'{sp_cards}</div>'
        )
    else:
        special_block = (
            f'<div style="background:{C_SURFACE};border:1px solid {C_BORDER};'
            f'border-radius:{RADIUS_MD};padding:16px 18px;margin-bottom:28px;'
            f'font-size:14px;color:{C_TEXT2};">특별공급 자격 정보가 없습니다.</div>'
        )

    # ── 1순위 / 2순위 ──
    def _rank_block(label, items, color):
        if not items:
            items = ["-"]
        li_html = "".join(
            f'<li style="font-size:14px;color:{C_TEXT2};line-height:1.8;'
            f'padding:3px 0;border-bottom:1px solid {C_BORDER};">'
            f'<span style="color:{color};font-weight:700;margin-right:6px;">·</span>{r}</li>'
            for r in items
        )
        return (
            f'<div style="flex:1 1 calc(50% - 8px);min-width:200px;'
            f'background:{C_SURFACE};border:1px solid {C_BORDER};'
            f'border-top:3px solid {color};border-radius:{RADIUS_MD};padding:16px 18px;">'
            f'<div style="font-size:14px;font-weight:800;color:{color};margin-bottom:12px;">{label}</div>'
            f'<ul style="list-style:none;padding:0;margin:0;">{li_html}</ul>'
            f'</div>'
        )

    rank_blocks = (
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;">'
        f'{_rank_block("1순위 자격", data.get("eligibility_rank1", []), C_ACCENT)}'
        f'{_rank_block("2순위 자격", data.get("eligibility_rank2", []), C_TEXT2)}'
        f'</div>'
    )

    notice = (
        f'<p style="font-size:13px;color:{C_TEXT2};margin-top:16px;line-height:1.6;">'
        f'※ 자격 요건은 공고문 기준이며, 개인 상황에 따라 다를 수 있습니다. '
        f'반드시 청약홈 및 분양사 공식 자료를 통해 최종 확인하세요.</p>'
    )

    section_html = f"""

<!-- ══════════════════════════════════════════
     SECTION 4 — 청약 신청자격
═══════════════════════════════════════════ -->
<div style="padding: 0 20px; margin-bottom: 44px;">

  <div style="font-size: 12px; font-weight: 700; color: {C_ACCENT}; letter-spacing: 1.5px; margin-bottom: 10px;">
    04 · 청약 신청자격
  </div>
  <h2 style="font-size: 22px; font-weight: 800; color: {C_TEXT}; margin: 0 0 20px 0; line-height: 1.4;">
    나는 청약할 수 있을까요?
  </h2>

  {special_block}
  {rank_blocks}
  {notice}

</div>

<!-- 구분선 -->
<div style="height: 1px; background: {C_BORDER}; margin: 0 20px 44px;"></div>

"""
    return section_html


def renumber_sections(html: str) -> str:
    """구 04 · → 05 ·, 05 · → 06 · 로 변경 (줄바꿈·공백 허용)"""
    html = re.sub(r'(?<=\s)04 · 자금 계획(?=\s)', '05 · 자금 계획', html)
    html = re.sub(r'(?<=\s)04 · 자금계획(?=\s)',  '05 · 자금계획',  html)
    html = re.sub(r'(?<=\s)05 · 자주 묻는 질문(?=\s)', '06 · 자주 묻는 질문', html)
    return html


def patch(html: str, eligibility_data: dict) -> str:
    # 이미 삽입된 경우 스킵
    if "04 · 청약 신청자격" in html:
        return html

    elig_html = _eligibility_html(eligibility_data)

    # SECTION 4 자금 계획 앞에 삽입
    # 패턴: "SECTION 4 — 자금 계획" 주석 앞
    insert_before = re.search(
        r'<!-- ═+\s*SECTION 4 — 자금 계획',
        html,
    )
    if insert_before:
        pos = insert_before.start()
        html = html[:pos] + elig_html + html[pos:]
        html = renumber_sections(html)
    else:
        # 자금 계획 h2 기준으로 찾기
        insert_before = re.search(
            r'<div[^>]*>\s*04 · 자금 계획\s*</div>',
            html,
        )
        if insert_before:
            pos = insert_before.start()
            html = html[:pos] + elig_html + html[pos:]
            html = renumber_sections(html)

    return html


# ── 단지별 신청자격 데이터 ───────────────────────────────────────
ELIGIBILITY_DATA: dict[str, dict] = {
    "강릉 우미 린 더 프리미어": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "", "requirements": [
                "무주택 세대구성원",
                "혼인 기간 7년 이내 (신생아특공: 공고일 2년 내 출생아 有)",
                "소득: 도시근로자 월평균 140% 이하 (맞벌이 160%)",
            ]},
            {"type_name": "생애최초특별공급", "quota": "", "requirements": [
                "세대원 전원 생애 주택 미소유",
                "5년 이상 소득세 납부 이력",
                "소득: 도시근로자 월평균 160% 이하",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 3명 이상 (태아 포함)",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택 세대구성원",
                "청약통장 1순위 해당자",
            ]},
            {"type_name": "기관추천특별공급", "quota": "", "requirements": [
                "국가보훈·장애인·중소기업근로자 등 해당 기관 추천자",
                "무주택 세대구성원",
            ]},
        ],
        "eligibility_rank1": [
            "강릉시 6개월 이상 거주자 우선 (비규제지역)",
            "청약통장 가입 6개월 이상 + 면적별 예치금 충족",
            "유주택자도 1순위 신청 가능 (비규제지역)",
            "85㎡ 이하: 가점 40% / 추첨 60% · 85㎡ 초과: 추첨 100%",
        ],
        "eligibility_rank2": [
            "강릉시 외 강원도 거주자 (1순위 미달 시)",
            "청약통장 가입 6개월 미만자",
        ],
    },
    "경기광주역 롯데캐슬 시그니처 1단지": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "", "requirements": [
                "무주택 세대구성원",
                "혼인 기간 7년 이내",
                "소득: 도시근로자 월평균 140% 이하 (맞벌이 160%)",
            ]},
            {"type_name": "생애최초특별공급", "quota": "", "requirements": [
                "세대원 전원 생애 주택 미소유",
                "5년 이상 소득세 납부 이력",
                "소득: 도시근로자 월평균 160% 이하",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 3명 이상",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택 세대구성원",
                "청약통장 1순위 해당자",
            ]},
            {"type_name": "장애인기관추천특별공급", "quota": "7세대", "requirements": [
                "장애인등록증 소지자",
                "해당 지자체(서울·인천 등) 추천 명단 등재",
                "무주택 세대구성원",
            ]},
        ],
        "eligibility_rank1": [
            "수도권(서울·인천·경기) 거주자, 경쟁 시 광주시 1년 이상 거주자 우선",
            "청약통장 가입 12개월 이상 + 면적별 예치금 충족",
            "유주택자(다주택자)도 1순위 가능 (비규제지역)",
            "85㎡ 이하: 가점 40% / 추첨 60% · 85㎡ 초과: 추첨 100%",
        ],
        "eligibility_rank2": [
            "1순위 미달 시 수도권 거주자",
            "청약통장 12개월 미만 또는 예치금 미달자",
        ],
    },
    "고덕신도시 아테라 A-63블록 공공분양주택": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "", "requirements": [
                "무주택 세대구성원, 혼인 7년 이내",
                "소득: 도시근로자 월평균 100% 이하 (우선) / 130% 이하 (일반)",
                "자산: 부동산 2억 1,550만원 이하, 자동차 3,683만원 이하",
            ]},
            {"type_name": "생애최초특별공급", "quota": "", "requirements": [
                "세대원 전원 생애 무주택 (5년 이상 소득세 납부)",
                "소득: 도시근로자 월평균 100% 이하 (우선) / 130% 이하 (일반)",
                "자산: 부동산 2억 1,550만원 이하, 자동차 3,683만원 이하",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 2명 이상 (공공분양 기준)",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하",
            ]},
            {"type_name": "장애인기관추천특별공급", "quota": "10세대", "requirements": [
                "장애인등록증 소지자",
                "해당 지자체 추천 명단 등재",
                "무주택 세대구성원",
            ]},
        ],
        "eligibility_rank1": [
            "무주택 세대구성원 필수 (유주택자 청약 불가)",
            "평택시 또는 경기도 거주자 우선",
            "청약통장 가입 24개월 이상 + 납입 24회 이상",
            "저축총액 많은 순 당첨 (순차제 80% / 추첨제 20%)",
        ],
        "eligibility_rank2": [
            "청약통장 24개월·24회 미만 무주택 세대구성원",
            "기타 수도권 거주 무주택자",
        ],
    },
    "공덕역자이르네": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "약 40세대", "requirements": [
                "혼인기간 7년 이내 또는 6세 이하 자녀 보유",
                "부부 모두 무주택세대구성원",
                "소득: 도시근로자 월평균 140% 이하 (맞벌이 160%)",
                "신생아(2세 미만) 보유 시 우선공급 적용",
            ]},
            {"type_name": "생애최초특별공급", "quota": "약 15세대", "requirements": [
                "생애 최초 주택 구입자",
                "근로자·자영업자로 소득세 납부 이력 필요",
                "소득: 도시근로자 월평균 130% 이하 (맞벌이 140%)",
                "세대 구성원 전원 무주택",
            ]},
            {"type_name": "기관추천특별공급(장애인)", "quota": "5세대", "requirements": [
                "만 19세 이상 성년 장애인 본인",
                "서울시 3개월 이상 계속 거주",
                "세대구성원 전원 무주택",
                "서울시 장애인복지관 등 기관 추천 필요",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 3명 이상",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "세대주로서 무주택",
                "청약통장 24개월 이상 가입",
            ]},
        ],
        "eligibility_rank1": [
            "공고일 기준 서울 2년 이상 계속 거주 (해당지역 우선)",
            "세대주 필수 (투기과열지구)",
            "청약통장 24개월 이상 + 예치금 300만원 이상 (85㎡ 이하)",
            "전용 60㎡ 이하: 가점제 40% + 추첨제 60%",
            "추첨제 물량 중 75% 무주택세대구성원 우선",
        ],
        "eligibility_rank2": [
            "서울 외 수도권 거주자 (1순위 미달 시 접수)",
            "청약통장 12개월 이상 + 예치금 기준 충족",
            "세대주 또는 세대원 가능",
        ],
    },
    "도안자이 센텀리체 2단지": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "151세대", "requirements": [
                "혼인기간 7년 이내 또는 6세 이하 자녀 보유",
                "부부 모두 무주택",
                "소득: 도시근로자 월평균 140% 이하 (맞벌이 160%)",
                "신생아 보유 시 우선공급 적용",
            ]},
            {"type_name": "생애최초특별공급", "quota": "75세대", "requirements": [
                "생애 최초 주택 구입",
                "근로자·자영업자로 소득세 납부 이력",
                "소득: 도시근로자 월평균 130% 이하 (맞벌이 140%)",
                "세대 구성원 전원 무주택",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "94세대", "requirements": [
                "미성년 자녀 3명 이상",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "28세대", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택 세대주",
                "청약통장 24개월 이상 가입",
            ]},
            {"type_name": "기관추천특별공급", "quota": "84세대", "requirements": [
                "국가유공자·장애인·철거민 등 기관 추천 대상자",
                "세대구성원 전원 무주택",
                "해당 기관별 별도 자격 기준 적용",
            ]},
        ],
        "eligibility_rank1": [
            "공고일 기준 대전시 거주자 우선 (비규제지역)",
            "청약통장 12개월 이상 가입 + 예치금 충족",
            "만 19세 이상 세대주 또는 세대원 가능",
            "유주택자도 청약 가능 (비규제지역)",
            "84㎡: 가점제 40% + 추첨제 60% / 115㎡: 100% 추첨제",
        ],
        "eligibility_rank2": [
            "대전 외 충청권 거주자 (1순위 미달 시)",
            "청약통장 6개월 이상 가입",
            "예치금 기준 충족",
        ],
    },
    "동탄 그웬 160 (동탄2 B11BL)": {
        "eligibility_special": [
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 3명 이상",
                "무주택 세대구성원",
                "소득: 도시근로자 월평균 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택 세대주",
                "청약통장 24개월 이상 가입",
            ]},
        ],
        "eligibility_rank1": [
            "화성시 거주자 우선, 그 외 수도권 포함 (비규제지역)",
            "만 19세 이상 세대주·세대원 무관",
            "청약통장 12개월 이상 + 예치금 충족",
            "유주택자 포함 누구나 가능 (비규제지역)",
            "전용 85㎡ 초과 전 타입 100% 추첨제",
        ],
        "eligibility_rank2": [
            "수도권(화성 외) 거주자",
            "청약통장 6개월 이상 가입",
            "예치금 기준 충족",
        ],
    },
    "두산위브더제니스 구미(조합원취소분)": {
        "eligibility_special": [
            {"type_name": "다자녀가구 특별공급", "quota": "", "requirements": [
                "무주택세대구성원 세대주",
                "미성년 자녀 2명 이상",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "신혼부부 특별공급", "quota": "", "requirements": [
                "혼인 7년 이내 무주택 신혼부부·예비신혼·한부모가족",
                "청약통장 가입 6개월 이상",
                "소득기준: 도시근로자 월평균소득 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "생애최초 특별공급", "quota": "", "requirements": [
                "세대원 전원 과거 주택 소유 이력 없음",
                "근로자·사업자로서 5년 이상 소득세 납부",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "기관추천 특별공급", "quota": "", "requirements": [
                "국가유공자·장애인 등 관련 기관 추천 대상",
                "무주택세대구성원",
                "해당 기관 추천서 필수",
            ]},
        ],
        "eligibility_rank1": [
            "청약통장 가입 6개월 이상 + 면적별 예치금 충족",
            "구미시 또는 대구광역시·경상북도 거주 만 19세 이상",
            "세대주·세대원·유주택자 모두 가능 (비규제지역)",
        ],
        "eligibility_rank2": [
            "청약통장 가입 6개월 미만 또는 예치금 미충족자",
            "1순위 미당첨자 대상",
        ],
    },
    "문수로 라티에르 673": {
        "eligibility_special": [
            {"type_name": "신혼부부 특별공급", "quota": "", "requirements": [
                "혼인 7년 이내 무주택 신혼부부·예비신혼·한부모가족",
                "청약통장 가입 6개월 이상",
                "소득: 도시근로자 월평균소득 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "생애최초 특별공급", "quota": "", "requirements": [
                "세대원 전원 과거 주택 소유 이력 없음",
                "근로자·사업자로서 5년 이상 소득세 납부",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "다자녀가구 특별공급", "quota": "", "requirements": [
                "미성년 자녀 2명 이상",
                "무주택세대구성원 세대주",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "기관추천 특별공급", "quota": "", "requirements": [
                "국가유공자·장애인 등 관련 기관 추천 대상",
                "무주택세대구성원",
                "해당 기관 추천서 필수",
            ]},
        ],
        "eligibility_rank1": [
            "청약통장 가입 6개월 이상 + 면적별 예치금 충족",
            "울산광역시 거주 1년 이상 우선 (당해지역 우선배정)",
            "세대주·세대원·유주택자 모두 가능 (비규제지역)",
        ],
        "eligibility_rank2": [
            "청약통장 가입기간 6개월 미만 또는 예치금 미충족자",
            "기타 지역 거주 1순위 미해당자",
        ],
    },
    "엘리프 창원": {
        "eligibility_special": [
            {"type_name": "신혼부부 특별공급", "quota": "", "requirements": [
                "혼인 7년 이내 무주택 신혼부부·예비신혼·한부모가족",
                "청약통장 가입 6개월 이상",
                "소득: 도시근로자 월평균소득 120% 이하 (맞벌이 130%)",
            ]},
            {"type_name": "생애최초 특별공급", "quota": "", "requirements": [
                "세대원 전원 과거 주택 소유 이력 없음",
                "혼인 중이거나 미혼 자녀 있는 자",
                "근로자·사업자로서 5년 이상 소득세 납부",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "다자녀가구 특별공급", "quota": "", "requirements": [
                "미성년 자녀 2명 이상",
                "무주택세대구성원 세대주",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "노부모부양 특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양",
                "무주택세대구성원 세대주",
                "청약통장 가입 6개월 이상",
            ]},
            {"type_name": "기관추천 특별공급", "quota": "", "requirements": [
                "국가유공자·장애인 등 관련 기관 추천",
                "무주택세대구성원",
                "해당 기관 추천서 필수",
            ]},
        ],
        "eligibility_rank1": [
            "청약통장 가입 6개월 이상 + 면적별 예치금 충족",
            "창원시 거주자 우선 (경남 거주자 포함)",
            "세대주·세대원·유주택자 모두 가능 (비규제지역)",
            "당첨 시 재당첨제한 10년 적용 (공공택지 분양가상한제)",
        ],
        "eligibility_rank2": [
            "청약통장 가입기간 6개월 미만 또는 예치금 미충족자",
            "1순위 미당첨자 대상",
        ],
    },
    "용인 고림 동문 디 이스트": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "81세대", "requirements": [
                "혼인 중이거나 6개월 이내 결혼 예정인 무주택 세대구성원",
                "청약통장 가입 6개월 이상, 납입 6회 이상",
                "소득기준: 도시근로자 월평균소득 120% 이하 (맞벌이 130%)",
                "신생아 우선공급: 2세 미만 자녀 있는 경우 25% 우선",
            ]},
            {"type_name": "생애최초특별공급", "quota": "32세대", "requirements": [
                "세대구성원 전원 과거 주택 소유 이력 없는 무주택자",
                "청약통장 가입 12개월 이상, 납입 12회 이상",
                "근로자·자영업자로 소득세 납부 이력 있는 자",
                "1인 가구(미혼)는 전용 59㎡에 한해 신청 가능",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "37세대", "requirements": [
                "미성년 자녀 3명 이상인 무주택 세대구성원",
                "청약통장 가입 6개월 이상, 납입 6회 이상",
                "배점제 운영 (자녀 수·무주택 기간·청약통장 기간 합산)",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "13세대", "requirements": [
                "만 65세 이상 직계존속(배우자 직계존속 포함) 3년 이상 부양 중인 무주택 세대주",
                "청약통장 가입 12개월 이상, 예치금 충족",
                "1순위 일반공급 자격과 동일한 통장 요건 적용",
            ]},
            {"type_name": "기관추천특별공급(장애인)", "quota": "", "requirements": [
                "장애인복지법상 등록 장애인인 무주택 세대구성원",
                "관할 시·군·구청 또는 복지관 추천 필수",
                "청약통장 보유 필요 (가입기간 제한 없음)",
            ]},
        ],
        "eligibility_rank1": [
            "모집공고일 기준 용인시 또는 수도권 거주 만 19세 이상",
            "청약통장 가입 12개월 이상 + 지역별 예치금 충족",
            "세대주·세대원·유주택자 모두 1순위 신청 가능 (비규제지역)",
            "가점제 40% + 추첨제 60% 적용 (60㎡ 초과 85㎡ 이하)",
            "동일 순위 내 경쟁 시 용인시 거주자 우선",
        ],
        "eligibility_rank2": [
            "1순위 자격 미충족자 (통장 가입 12개월 미만 또는 예치금 미달)",
            "1순위 미달 세대에서 2순위 접수",
        ],
    },
    "인천가정2지구 B2블록 공공분양주택(후속사업)": {
        "eligibility_special": [
            {"type_name": "신혼부부특별공급", "quota": "", "requirements": [
                "혼인 7년 이내 또는 6세 이하 자녀 있는 무주택 세대구성원",
                "청약통장 가입 6개월 이상, 납입 6회 이상",
                "소득: 도시근로자 월평균소득 100% 이하 → 70% 우선공급 (맞벌이 120%)",
                "자산: 부동산 2억 1,550만원 이하, 자동차 3,708만원 이하",
            ]},
            {"type_name": "생애최초특별공급", "quota": "", "requirements": [
                "세대구성원 전원 과거 주택 소유 이력 없는 무주택자",
                "청약통장 가입 12개월 이상, 납입 12회 이상",
                "근로자·자영업자로 소득세 납부 이력 보유",
                "소득: 도시근로자 월평균소득 100% 이하 (맞벌이 120%)",
            ]},
            {"type_name": "다자녀가구특별공급", "quota": "", "requirements": [
                "미성년 자녀 3명 이상인 무주택 세대구성원",
                "소득: 도시근로자 월평균소득 120% 이하 (맞벌이 130%)",
                "청약통장 가입 6개월 이상, 납입 6회 이상",
            ]},
            {"type_name": "노부모부양특별공급", "quota": "", "requirements": [
                "만 65세 이상 직계존속 3년 이상 부양 중인 무주택 세대주",
                "청약통장 가입 24개월 이상, 납입 24회 이상 (공공분양 기준)",
            ]},
            {"type_name": "기관추천특별공급(장애인)", "quota": "", "requirements": [
                "등록 장애인으로 관할 기관 추천 필수",
                "무주택 세대구성원",
                "청약통장 보유 (가입 기간 제한 없음)",
            ]},
        ],
        "eligibility_rank1": [
            "수도권(인천·서울·경기) 거주 성년자인 무주택 세대구성원",
            "청약통장 가입 24개월 이상 + 납입 24회 이상",
            "소득기준 충족 (도시근로자 월평균소득 100% 이하)",
            "인천광역시 거주자 100% 우선 공급",
            "일반공급 80% 순차제(저축총액순) + 20% 추첨제",
        ],
        "eligibility_rank2": [
            "무주택 세대구성원으로 청약통장 24개월 미만자",
            "수도권 거주 성년자로 청약통장 보유",
        ],
    },
}

# 기본값 (딕셔너리에 없는 경우 fallback)
DEFAULT_RANK1 = [
    "청약통장(주택청약종합저축) 가입 후 24회 이상 납입",
    "무주택세대구성원",
    "입주자 모집공고일 기준 해당 지역 거주자 우선",
]
DEFAULT_RANK2 = [
    "청약통장(주택청약종합저축) 가입 후 1회 이상 납입",
    "무주택세대구성원 또는 1주택 소유자",
]


def get_eligibility(apt_name: str) -> dict:
    """딕셔너리에서 반환, 없으면 기본값"""
    if apt_name in ELIGIBILITY_DATA:
        return ELIGIBILITY_DATA[apt_name]
    return {
        "eligibility_special": [],
        "eligibility_rank1": DEFAULT_RANK1,
        "eligibility_rank2": DEFAULT_RANK2,
    }


def main():
    patched = 0
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        apt_name = meta.get("apt_name", "")
        post_path = meta_path.parent / "post.html"
        if not post_path.exists():
            continue

        original = post_path.read_text(encoding="utf-8")
        elig_data = get_eligibility(apt_name)
        updated = patch(original, elig_data)

        if updated != original:
            post_path.write_text(updated, encoding="utf-8")
            print(f"  삽입 완료: {apt_name}")
            patched += 1
        else:
            print(f"  변경 없음: {apt_name}")

    print(f"\n총 {patched}개 파일 패치됨.")


if __name__ == "__main__":
    main()

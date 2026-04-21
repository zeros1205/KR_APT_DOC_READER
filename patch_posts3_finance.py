"""
patch_posts3_finance.py — 자금 계획 섹션 수정
  1. 계약금 금액 라인 삭제 (약 X만원 내외)
  2. 중도금 대출 설명 → 일반적 사실 정보로 교체
  3. 잔금 대출 설명 → 일반적 사실 정보로 교체
  4. financial_intro 에서 금액 언급 제거
"""
import re
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "output" / "posts"

MIDTERM_GENERIC = (
    "공사 기간 중 분납합니다. "
    "각 회차별 납부 일정과 금액은 공고문 및 계약서를 기준으로 합니다."
)
BALANCE_GENERIC = (
    "입주 지정기간 내 납부합니다. "
    "납부 방법 및 세부 조건은 입주안내문 및 계약서를 기준으로 합니다."
)
CONTRACT_GENERIC = (
    "계약 체결 시 자기자본으로 납부합니다. "
    "정확한 납부 시기와 방법은 공고문 및 계약서를 기준으로 합니다."
)


def patch(html: str) -> str:
    # 1. 계약금 금액 라인 제거 (font-size: 17px bold 라인 = 금액 표시 줄)
    html = re.sub(
        r'\s*<p style="font-size: 17px; font-weight: 800; color: [^"]+; margin: 0;">.*?</p>',
        '',
        html,
        flags=re.DOTALL,
    )

    # 2. 계약금 설명 p 태그 → 일반 정보로 교체 (금액 언급 없는 버전)
    #    패턴: 계약금 box 안의 "분양가의 X%를 계약 즉시..." 문장
    html = re.sub(
        r'(<p style="font-size: 16px; color: [^"]+; margin: 0 0 8px 0; line-height: 1\.6;">)'
        r'.*?'
        r'(</p>)',
        rf'\g<1>{CONTRACT_GENERIC}\2',
        html,
        flags=re.DOTALL,
        count=1,  # 계약금 첫 번째만
    )

    # 3. 중도금 p 태그 → 대출 제거, 일반 정보로 교체
    #    패턴: "중도금 — XX%" 헤더 이후의 첫 번째 p.font-size:16px
    def replace_midterm(m):
        prefix = m.group(1)
        suffix = m.group(3)
        return prefix + MIDTERM_GENERIC + suffix

    html = re.sub(
        r'(중도금 — \d+%.*?<p style="font-size: 16px; color: [^"]+; margin: 0; line-height: 1\.6;">)'
        r'(.*?)'
        r'(</p>)',
        replace_midterm,
        html,
        flags=re.DOTALL,
        count=1,
    )

    # 4. 잔금 p 태그 → 대출(주담대, DSR) 제거, 일반 정보로 교체
    def replace_balance(m):
        prefix = m.group(1)
        suffix = m.group(3)
        return prefix + BALANCE_GENERIC + suffix

    html = re.sub(
        r'(잔금 — \d+%.*?<p style="font-size: 16px; color: [^"]+; margin: 0; line-height: 1\.6;">)'
        r'(.*?)'
        r'(</p>)',
        replace_balance,
        html,
        flags=re.DOTALL,
        count=1,
    )

    # 5. financial_intro 에서 금액 구체적 언급 제거
    #    "5억 중반대", "5억대", "X억원" 등 금액 언급 → 일반 문장으로
    #    (orchestrator가 생성하는 인트로 문장)
    html = re.sub(
        r'(분양가가\s+)[0-9억~\s만원이]+([^\.\s])',
        r'\1분양가 기준\2',
        html,
    )

    return html


def main():
    patched = 0
    for meta_path in sorted(POSTS_DIR.glob("*/post_meta.json")):
        post_path = meta_path.parent / "post.html"
        if not post_path.exists():
            continue

        original = post_path.read_text(encoding="utf-8")
        updated = patch(original)

        if updated != original:
            post_path.write_text(updated, encoding="utf-8")
            print(f"  패치 완료: {post_path.parent.name}")
            patched += 1
        else:
            print(f"  변경 없음: {post_path.parent.name}")

    print(f"\n총 {patched}개 파일 패치됨.")


if __name__ == "__main__":
    main()

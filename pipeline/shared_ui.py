"""shared_ui.py — 공통 UI 컴포넌트
Pretendard 폰트 + 3-팔레트 CSS 변수 + 공유 네비게이션
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://cdn.jsdelivr.net">\n'
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/'
    'gh/orioncactus/pretendard@v1.3.9/dist/web/variable/'
    'pretendardvariable-dynamic-subset.min.css">'
)

FONT_FAMILY = (
    "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, "
    "system-ui, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif"
)

# ── 3-팔레트 CSS 변수 ──────────────────────────────────────────
PALETTE_CSS = """\
/* ─── 팔레트 A : Claude / Anthropic (기본값) ─── */
html {
  --c-primary:        #d97757;
  --c-primary-dark:   #b85c38;
  --c-primary-light:  #fdf0ea;
  --c-primary-stripe: rgba(217,119,87,0.05);
  --c-accent:         #6a9bcc;
  --c-bg:             #faf9f5;
  --c-surface:        #ffffff;
  --c-dark:           #2c2925;
  --c-mid:            #767370;
  --c-light-gray:     #e8e6dc;
  --c-hero-bg:        #f2efe6;
  --c-nav-bg:         #2a2721;
  --c-green:          #788c5d;
  --c-green-dark:     #57673f;
  --c-green-light:    #edf2e6;
  --c-card-grad-new:        linear-gradient(145deg,#d97757 0%,#b85c38 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#788c5d 0%,#57673f 100%);
  --c-cta-bg:               #4a4540;
  --c-cta-hover:            #38342f;
  --c-tag-new-bg:           #fdf0ea;
  --c-tag-new-text:         #b85c38;
  --c-tag-resupply-bg:      #edf2e6;
  --c-tag-resupply-text:    #57673f;
}

/* ─── 팔레트 B : Neutral Elegance ─── */
html[data-palette="B"] {
  --hunter-green:     #386641ff;
  --sage-green:       #6a994eff;
  --yellow-green:     #a7c957ff;
  --vanilla-cream:    #f2e8cfff;
  --blushed-brick:    #bc4749ff;
  --c-primary:        #386641;
  --c-primary-dark:   #2f5236;
  --c-primary-light:  #edf4e9;
  --c-primary-stripe: rgba(56,102,65,0.08);
  --c-accent:         #6a994e;
  --c-bg:             #f2e8cf;
  --c-surface:        #ffffff;
  --c-dark:           #2c2925;
  --c-mid:            #6a994e;
  --c-light-gray:     rgba(56,102,65,0.20);
  --c-hero-bg:        #f2e8cf;
  --c-nav-bg:         #2f5236;
  --c-green:          #a7c957;
  --c-green-dark:     #386641;
  --c-green-light:    #edf4e9;
  --c-card-grad-new:        linear-gradient(145deg,#6a994e 0%,#386641 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#a7c957 0%,#6a994e 100%);
  --c-cta-bg:               #386641;
  --c-cta-hover:            #2f5236;
  --c-tag-new-bg:           #edf4e9;
  --c-tag-new-text:         #386641;
  --c-tag-resupply-bg:      #edf4e9;
  --c-tag-resupply-text:    #6a994e;
}

/* ─── 팔레트 C : Pastel Dreamland ─── */
html[data-palette="C"] {
  --c-primary:        #ffafcc;
  --c-primary-dark:   #cc7fa0;
  --c-primary-light:  #fff5f8;
  --c-primary-stripe: rgba(255,175,204,0.08);
  --c-accent:         #a2d2ff;
  --c-bg:             #fdf8ff;
  --c-surface:        #ffffff;
  --c-dark:           #2d1f3d;
  --c-mid:            #8070a0;
  --c-light-gray:     #ddd0f0;
  --c-hero-bg:        #f5eefc;
  --c-nav-bg:         #3d2952;
  --c-green:          #bde0fe;
  --c-green-dark:     #6ab0e0;
  --c-green-light:    #eef6ff;
  --c-card-grad-new:        linear-gradient(145deg,#ffafcc 0%,#cdb4db 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#bde0fe 0%,#a2d2ff 100%);
  --c-cta-bg:               #7060a8;
  --c-cta-hover:            #5a4c8a;
  --c-tag-new-bg:           #fff5f8;
  --c-tag-new-text:         #cc7fa0;
  --c-tag-resupply-bg:      #eef6ff;
  --c-tag-resupply-text:    #6ab0e0;
}"""

# head에 삽입 — FOUC 방지 (DOM 파싱 전에 팔레트 클래스 설정)
PALETTE_INIT_JS = (
    '<script>'
    '(function(){var p=localStorage.getItem("apt-palette")||"A";'
    'document.documentElement.setAttribute("data-palette",p);})();'
    '</script>'
)

def shared_nav(home_href: str = "/", right_extra: str = "") -> str:
    """공유 네비게이션 바 HTML.
    home_href: 프론트페이지 링크 경로 (index: '/', detail: '../../')
    """
    return (
        f'<header id="site-nav" style="background:var(--c-nav-bg);padding:0 24px;'
        f'position:sticky;top:0;z-index:50;border-bottom:2px solid var(--c-primary);">'
        f'<div style="max-width:1160px;margin:0 auto;display:flex;align-items:center;'
        f'justify-content:space-between;height:54px;">'

        # 로고 (홈 링크)
        f'<a href="{home_href}" style="text-decoration:none;display:flex;align-items:center;gap:10px;">'
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:30px;height:30px;background:var(--c-primary);border-radius:6px;font-size:15px;flex-shrink:0;">📝</span>'
        f'<span style="color:#fff;font-size:15px;font-weight:800;letter-spacing:-0.3px;">'
        f'정과장의 청약노트</span>'
        f'</a>'

        # 우측 버튼 그룹
        f'<div style="display:flex;align-items:center;gap:10px;">'

        f'{right_extra}'

        # 청약홈 링크
        f'<a href="https://www.applyhome.co.kr/" target="_blank" rel="noopener" '
        f'style="font-size:12px;color:#fff;text-decoration:none;'
        f'border:1px solid #fff;border-radius:6px;padding:5px 12px;'
        f'white-space:nowrap;transition:all 150ms;"'
        f' onmouseover="this.style.color=\'rgba(255,255,255,0.7)\';this.style.borderColor=\'rgba(255,255,255,0.7)\'"'
        f' onmouseout="this.style.color=\'#fff\';this.style.borderColor=\'#fff\'">'
        f'청약홈 ↗</a>'

        f'</div>'
        f'</div>'
        f'</header>'
    )

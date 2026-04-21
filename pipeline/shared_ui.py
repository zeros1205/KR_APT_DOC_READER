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
  --c-primary:        #e0afa0;
  --c-primary-dark:   #c49080;
  --c-primary-light:  #f9f1ef;
  --c-primary-stripe: rgba(224,175,160,0.07);
  --c-accent:         #8a817c;
  --c-bg:             #f4f3ee;
  --c-surface:        #ffffff;
  --c-dark:           #2e2924;
  --c-mid:            #7a7370;
  --c-light-gray:     #bcb8b1;
  --c-hero-bg:        #eeebe4;
  --c-nav-bg:         #463f3a;
  --c-green:          #8a817c;
  --c-green-dark:     #635d59;
  --c-green-light:    #f0eeea;
  --c-card-grad-new:        linear-gradient(145deg,#e0afa0 0%,#c49080 100%);
  --c-card-grad-resupply:   linear-gradient(145deg,#8a817c 0%,#635d59 100%);
  --c-cta-bg:               #635d59;
  --c-cta-hover:            #52504c;
  --c-tag-new-bg:           #f9f1ef;
  --c-tag-new-text:         #c49080;
  --c-tag-resupply-bg:      #f0eeea;
  --c-tag-resupply-text:    #635d59;
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

# body 하단 <script> 안에 삽입할 팔레트 전환 JS
PALETTE_SWITCH_JS = """\
var _PALETTES = ['A','B','C'];
function cyclePalette() {
  var cur = document.documentElement.getAttribute('data-palette') || 'A';
  var next = _PALETTES[(_PALETTES.indexOf(cur) + 1) % _PALETTES.length];
  document.documentElement.setAttribute('data-palette', next);
  localStorage.setItem('apt-palette', next);
  var lbl = document.getElementById('palette-label');
  if (lbl) lbl.textContent = next;
}
document.addEventListener('DOMContentLoaded', function() {
  var lbl = document.getElementById('palette-label');
  if (lbl) lbl.textContent = document.documentElement.getAttribute('data-palette') || 'A';
});"""

_PALETTE_BTN_SVG = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;">'
    '<path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01'
    '-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c2.76 0 5-2.24 5-5 0-4.42-4.03-8-9-8z'
    'M6.5 12C5.67 12 5 11.33 5 10.5S5.67 9 6.5 9 8 9.67 8 10.5 7.33 12 6.5 12z'
    'M9.5 8C8.67 8 8 7.33 8 6.5S8.67 5 9.5 5 11 5.67 11 6.5 10.33 8 9.5 8z'
    'M14.5 8c-.83 0-1.5-.67-1.5-1.5S13.67 5 14.5 5 16 5.67 16 6.5 15.33 8 14.5 8z'
    'M17.5 12c-.83 0-1.5-.67-1.5-1.5S16.67 9 17.5 9 19 9.67 19 10.5 18.33 12 17.5 12z"/>'
    '</svg>'
)


def shared_nav(home_href: str = "/") -> str:
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

        # 팔레트 토글 버튼
        f'<button id="palette-btn" onclick="cyclePalette()" title="테마 변경 A→B→C" '
        f'style="display:inline-flex;align-items:center;gap:5px;background:transparent;'
        f'border:1px solid #fff;border-radius:6px;padding:5px 11px;'
        f'cursor:pointer;font-size:12px;color:#fff;font-family:inherit;'
        f'transition:all 150ms;"'
        f' onmouseover="this.style.borderColor=\'rgba(255,255,255,0.7)\';this.style.color=\'rgba(255,255,255,0.7)\'"'
        f' onmouseout="this.style.borderColor=\'#fff\';this.style.color=\'#fff\'">'
        f'{_PALETTE_BTN_SVG}'
        f'<span id="palette-label">A</span>'
        f'</button>'

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

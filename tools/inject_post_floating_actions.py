"""Inject share + scroll-to-top buttons into existing post.html files for preview.

One-off script. After this PR merges, future post generations get the chrome
automatically via pipeline/html_renderer.py. This handles the existing static
files so Cloudflare Pages preview shows the new buttons.

Idempotent — if marker already present, skips the file.
"""

from pathlib import Path
import sys

CSS_BLOCK = """.post-floating-actions {
  position: fixed;
  right: 24px;
  bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 60;
}
.post-floating-actions button {
  width: 48px;
  height: 48px;
  border: 1px solid rgba(255,255,255,0.92);
  border-radius: 12px;
  background: rgba(217,119,87,0.7);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 14px 28px rgba(217,119,87,0.32);
  cursor: pointer;
  padding: 0;
  transition: transform 150ms ease, background 150ms ease, opacity 150ms ease;
}
.post-floating-actions button:hover {
  background: rgba(184,92,56,0.78);
  transform: translateY(-2px);
}
.post-floating-actions button:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
#post-share-toast {
  position: fixed;
  left: 50%;
  bottom: 96px;
  transform: translateX(-50%) translateY(8px);
  background: rgba(30,30,30,0.92);
  color: #fff;
  padding: 10px 16px;
  border-radius: 999px;
  font-size: 0.875rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 180ms ease, transform 180ms ease;
  z-index: 70;
}
#post-share-toast.is-visible {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
"""

BUTTON_BLOCK = """<div class="post-floating-actions" aria-label="페이지 작업">
  <button id="post-share-btn" type="button" aria-label="공유하기">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="18" cy="5" r="3"></circle>
      <circle cx="6" cy="12" r="3"></circle>
      <circle cx="18" cy="19" r="3"></circle>
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
    </svg>
  </button>
  <button id="post-scroll-top-btn" type="button" aria-label="최상단으로 이동">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M18 15l-6-6-6 6"></path>
    </svg>
  </button>
</div>
<div id="post-share-toast" role="status" aria-live="polite"></div>
<script>
(function() {
  var topBtn = document.getElementById('post-scroll-top-btn');
  if (topBtn) {
    topBtn.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  var shareBtn = document.getElementById('post-share-btn');
  var toast = document.getElementById('post-share-toast');
  var toastTimer = null;
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('is-visible');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function() {
      toast.classList.remove('is-visible');
    }, 1800);
  }

  function getShareData() {
    var title = (document.querySelector('meta[property="og:title"]') || {}).content
      || document.title
      || '정과장의 청약노트';
    var description = (document.querySelector('meta[property="og:description"]') || {}).content
      || (document.querySelector('meta[name="description"]') || {}).content
      || '';
    return {
      title: title,
      text: description,
      url: location.href
    };
  }

  if (shareBtn) {
    shareBtn.addEventListener('click', async function() {
      var data = getShareData();
      if (navigator.share) {
        try {
          await navigator.share(data);
          return;
        } catch (err) {
          if (err && err.name === 'AbortError') return;
        }
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(data.url);
          showToast('링크가 복사되었습니다');
          return;
        } catch (_) {}
      }
      location.href = 'mailto:?subject=' + encodeURIComponent(data.title)
        + '&body=' + encodeURIComponent(data.url);
    });
  }
})();
</script>
"""

MARKER = "post-floating-actions"


def inject(post_html: Path) -> bool:
    text = post_html.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if "</style>" not in text or "</body>" not in text:
        print(f"  skip (anchors missing): {post_html}")
        return False
    text = text.replace("</style>", CSS_BLOCK + "</style>", 1)
    text = text.replace("</body>", BUTTON_BLOCK + "</body>", 1)
    post_html.write_text(text, encoding="utf-8")
    return True


def main(targets: list[str]) -> None:
    root = Path(__file__).resolve().parent.parent
    for notice_id in targets:
        post = root / "output" / "posts" / notice_id / "post.html"
        if not post.exists():
            print(f"  not found: {post}")
            continue
        ok = inject(post)
        print(f"  {'injected' if ok else 'already has marker'}: {notice_id}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: python tools/inject_post_floating_actions.py <notice_id> [...]")
        sys.exit(1)
    main(args)

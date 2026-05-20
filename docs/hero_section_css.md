# Hero 영역 CSS 정보

`https://apt-note.com/` 메인 페이지 상단 히어로 영역의 카피("복잡한 아파트 분양 공고문, 정과장이 쉽게! 정리해드립니다.")에 적용된 스타일 정보 정리.

**소스 파일**: `templates/front_index_template.html` (L756~767)

---

## DOM 구조

```html
<section class="front-hero" style="padding:32px 0; position:relative; overflow:hidden;">
  <div class="front-hero-inner" style="max-width:1160px; margin:0 auto; padding:0 24px; position:relative;">
    <div class="hero-copy">
      <h1 style="font-size:clamp(28px,4.5vw,52px);
                 font-weight:900;
                 color:var(--c-dark);
                 line-height:1.05;
                 margin-bottom:18px;
                 padding-bottom:6px;
                 word-break:keep-all;
                 letter-spacing:-1.5px;">
        <span style="color:#8f8a84;">복잡한</span><br>
        아파트 분양 공고문,<br>
        <span style="color:var(--c-primary);">정과장이 쉽게!</span><br>
        정리해드립니다.
      </h1>
    </div>
```

---

## 클래스 스타일 (template L438~448)

```css
.front-hero {
  background:
    repeating-linear-gradient(135deg, rgba(217,119,87,0.05) 0 1px, transparent 1px 34px),
    #fffaf3;
}

.hero-copy {
  position: relative;
  z-index: 2;
  width: min(560px, 100%);
}
```

---

## 인라인 스타일 분해 (h1)

| 속성 | 값 | 비고 |
|---|---|---|
| `font-size` | `clamp(28px, 4.5vw, 52px)` | 최소 28px / 뷰포트 4.5% / 최대 52px |
| `font-weight` | `900` | extra black |
| `color` | `var(--c-dark)` = `#2c2925` | 본문 줄 ("아파트 분양 공고문," / "정리해드립니다.") |
| `line-height` | `1.05` | 줄 간격 매우 좁음 |
| `margin-bottom` | `18px` |  |
| `padding-bottom` | `6px` |  |
| `word-break` | `keep-all` | 한국어 단어 단위 줄바꿈 |
| `letter-spacing` | `-1.5px` | 자간 좁힘 |

---

## 줄별 색상

| 줄 | 색상 | 값 | 적용 방식 |
|---|---|---|---|
| 복잡한 | `#8f8a84` | 회색 | `<span style="color:#8f8a84;">` |
| 아파트 분양 공고문, | `#2c2925` | `var(--c-dark)` | h1 기본 color |
| 정과장이 쉽게! | `#d97757` | `var(--c-primary)` | `<span style="color:var(--c-primary);">` |
| 정리해드립니다. | `#2c2925` | `var(--c-dark)` | h1 기본 color |

---

## 배경

- 좌상→우하 135° 사선 줄무늬 패턴 — `repeating-linear-gradient(135deg, rgba(217,119,87,0.05) 0 1px, transparent 1px 34px)` (오렌지 5% 투명도)
- 베이스 색상 — `#fffaf3` 크림 배경
- 우측에 SVG 스카이라인 (`.hero-skyline`, `opacity: 0.13`) 이 `position: absolute` 로 깔림

### 스카이라인 SVG 스타일 (template L458~480)

```css
.hero-skyline {
  position: absolute;
  left: -24px;
  right: -24px;
  bottom: 0;
  width: calc(100% + 48px);
  height: auto;
  color: #2b261f;
  opacity: 0.13;
}

.hero-skyline path,
.hero-skyline line,
.hero-skyline polyline {
  fill: none;
  stroke: currentColor;
  stroke-width: 2.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.hero-skyline .detail {
  stroke-width: 1.8;
  opacity: 0.82;
}
```

---

## CSS 변수 매핑

| 변수 | 값 | 용도 |
|---|---|---|
| `--c-primary` | `#d97757` | 강조 오렌지 ("정과장이 쉽게!") |
| `--c-dark` | `#2c2925` | h1 기본 본문 색상 |
| `--c-bg` | `#fffaf3` | 페이지 배경 크림색 |

`:root` 정의 위치: `pipeline/shared_ui.py` / `templates/front_index_template.html` 상단 `<style>` 블록.

"""카드뉴스 HTML 템플릿 → 1080x1350 JPEG 슬라이드."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .config import TEMPLATES_DIR, load_config

CATEGORY_STYLE = {
    "정치": ("POLITICS", "#D7263D"),
    "시사": ("WORLD", "#2F5BEA"),
    "사회": ("SOCIETY", "#E08A00"),
    "경제": ("ECONOMY", "#14845E"),
    "연예": ("ENTERTAINMENT", "#D9438F"),
}


def _mark(body: str, highlight: str) -> Markup:
    safe = str(escape(body)).replace("\n", "<br>")
    hl = str(escape(highlight or "")).strip()
    if hl and hl in safe:
        safe = safe.replace(hl, f"<mark>{hl}</mark>", 1)
    return Markup(safe)


def _emph(text: str) -> Markup:
    """'[[강조]]' 표시를 강조색으로. 표시가 없으면 원문 그대로."""
    safe = str(escape(text or "")).replace("\n", "<br>")
    safe = re.sub(r"\[\[(.+?)\]\]", r"<em>\1</em>", safe)
    return Markup(safe.replace("[[", "").replace("]]", ""))


def build_context(copy: dict, cand: dict, brand: dict, image_url: str, tz: str, ai_image: bool) -> dict:
    category = cand.get("category") or "시사"
    cat_en, cat_color = CATEGORY_STYLE.get(category, ("WORLD", "#2F5BEA"))
    accent = brand.get("accent") or cat_color
    logo = TEMPLATES_DIR / "logo.png"
    slides = [{"title": s.get("title", ""), "title_html": _emph(s.get("title", "")),
               "body_html": _mark(s.get("body", ""), s.get("highlight", ""))}
              for s in copy.get("slides", [])]
    my_take = (copy.get("my_take") or "").strip()
    show_take = bool(my_take) and bool(brand.get("editor_slide", False))
    show_outro = bool(brand.get("outro_slide", False))
    outro = brand.get("outro") or load_config().get("outro") or {}
    total = 1 + len(slides) + (1 if show_take else 0) + (1 if show_outro else 0)
    src = cand.get("source_account")
    source_label = f"@{src}" if src else f"Instagram {cand.get('source_type', '')}".strip()
    return {
        "brand": brand, "category": category, "category_en": cat_en, "accent": accent,
        "brand_navy": brand.get("navy", "#1B2A72"),
        "logo_url": logo.as_uri() if logo.exists() else None,
        "headline": copy.get("headline", ""), "headline_html": _emph(copy.get("headline", "")),
        "subheadline": copy.get("subheadline", ""),
        "slides": slides, "my_take": my_take, "total": total,
        "show_take": show_take, "show_outro": show_outro,
        "outro": outro, "outro_tag1": _emph(outro.get("tagline1", "")),
        "image_url": image_url, "permalink": cand.get("permalink", ""),
        "source_label": source_label, "ai_image": ai_image,
        "date": datetime.now(ZoneInfo(tz)).strftime("%Y.%m.%d"),
    }


def render_slides(ctx: dict, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template("card.html.j2").render(font_dir=(TEMPLATES_DIR / "fonts").as_uri(), **ctx)
    html_path = out_dir / "cardnews.html"
    html_path.write_text(html, encoding="utf-8")

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.wait_for_function("document.body.dataset.fitted === '1'", timeout=20000)
        for i in range(1, ctx["total"] + 1):
            path = out_dir / f"slide_{i:02d}.jpg"
            page.locator(f"#s{i}").screenshot(path=str(path), type="jpeg", quality=92)
            paths.append(path)
        browser.close()
    return paths

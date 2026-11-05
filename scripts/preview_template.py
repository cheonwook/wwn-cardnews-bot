"""API 키 없이 템플릿만 미리보기: python scripts/preview_template.py [카테고리] [표지이미지경로]
결과: preview/slide_XX.jpg
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from bot.config import ROOT, load_config  # noqa: E402
from bot.render import build_context, render_slides  # noqa: E402

out = ROOT / "preview"
out.mkdir(exist_ok=True)


def placeholder_city(path: Path):
    """임시 표지: 해질녘 도시 스카이라인."""
    W, H = 1088, 1360
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(40 + 180 * t), int(60 + 70 * t), int(120 - 40 * t)))
    rnd = random.Random(7)
    for layer, (shade, base) in enumerate([((45, 50, 75), 520), ((22, 25, 40), 640)]):
        x = -20
        while x < W:
            w = rnd.randint(60, 150)
            h = rnd.randint(150, 520) + layer * 60
            top = base + 300 - h
            d.rectangle([x, top, x + w, H], fill=shade)
            for wy in range(top + 20, H, 26):
                for wx in range(x + 10, x + w - 10, 22):
                    if rnd.random() < 0.28:
                        d.rectangle([wx, wy, wx + 8, wy + 12], fill=(255, 196, 110))
            x += w + rnd.randint(0, 12)
    img.filter(ImageFilter.GaussianBlur(1.2)).save(path, quality=90)


cover = Path(sys.argv[2]) if len(sys.argv) > 2 else out / "cover.jpg"
if len(sys.argv) <= 2:
    placeholder_city(cover)

cfg = load_config()
cand = {"category": sys.argv[1] if len(sys.argv) > 1 else "경제",
        "source_account": "bloombergbusiness",
        "permalink": "https://www.instagram.com/p/EXAMPLE123/"}
copy = {
    "headline": "[[미 연준]], 기준금리 세 번째 동결… [[고용 쇼크]] 신호에 시장 술렁",
    "subheadline": "",
    "slides": [
        {"title": "무슨 [[일]]이 있었나", "body": "미국 연방준비제도가 기준금리를 다시 동결했습니다. 세 차례 연속입니다.", "highlight": "세 차례 연속"},
        {"title": "왜 [[동결]]했을까", "body": "물가 상승률은 목표치에 가까워졌지만, 최근 고용 지표가 예상보다 약하게 나왔습니다.", "highlight": "고용 지표"},
        {"title": "[[시장]] 반응", "body": "발표 직후 주요 지수는 소폭 상승했고, 국채 금리는 하락했습니다.", "highlight": ""},
        {"title": "앞으로는?", "body": "연준은 다음 회의까지 데이터를 보고 판단하겠다는 입장입니다. 인하 시점을 두고 월가 전망이 엇갈립니다.", "highlight": "인하 시점"},
    ],
    "my_take": "결국 우리 대출 이자에도 영향이 올 수밖에 없다고 생각해요. 금리 뉴스는 남의 나라 얘기가 아니라 내 통장 얘기라는 걸 다시 느낍니다.",
}
ctx = build_context(copy, cand, cfg["brand"], cover.resolve().as_uri(), cfg["publish"]["timezone"], True)
for p in render_slides(ctx, out):
    print(p)

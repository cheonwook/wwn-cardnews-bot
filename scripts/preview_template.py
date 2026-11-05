"""API 키 없이 템플릿만 미리보기: python scripts/preview_template.py
결과: preview/slide_XX.jpg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from bot.config import ROOT, load_config  # noqa: E402
from bot.render import build_context, render_slides  # noqa: E402

out = ROOT / "preview"
out.mkdir(exist_ok=True)

# 임시 표지 이미지(그라디언트)
img = Image.new("RGB", (1088, 1360), "#1d2b45")
d = ImageDraw.Draw(img)
for y in range(1360):
    d.line([(0, y), (1088, y)], fill=(29 + y // 20, 43 + y // 30, 69 + y // 40))
d.ellipse([300, 220, 820, 740], fill="#e9b44c")
d.rectangle([0, 760, 1088, 1360], fill="#0e1626")
img = img.filter(ImageFilter.GaussianBlur(6))
img.save(out / "cover.jpg", quality=90)

cfg = load_config()
cand = {"category": sys.argv[1] if len(sys.argv) > 1 else "경제",
        "source_account": "bloombergbusiness",
        "permalink": "https://www.instagram.com/p/EXAMPLE123/"}
copy = {
    "headline": "미 연준, 금리\n세 번째 동결",
    "subheadline": "물가는 잡혔지만 고용이 흔들린다는 신호",
    "slides": [
        {"title": "무슨 일이 있었나", "body": "미국 연방준비제도가 기준금리를 다시 동결했습니다. 세 차례 연속입니다.", "highlight": "세 차례 연속"},
        {"title": "왜 동결했을까", "body": "물가 상승률은 목표치에 가까워졌지만, 최근 고용 지표가 예상보다 약하게 나왔습니다.", "highlight": "고용 지표"},
        {"title": "시장 반응", "body": "발표 직후 주요 지수는 소폭 상승했고, 국채 금리는 하락했습니다.", "highlight": ""},
        {"title": "앞으로는", "body": "연준은 다음 회의까지 데이터를 보고 판단하겠다는 입장입니다. 인하 시점을 두고 전망이 엇갈립니다.", "highlight": "인하 시점"},
    ],
    "my_take": "결국 우리 대출 이자에도 영향이 올 수밖에 없다고 생각해요. 금리 뉴스는 남의 나라 얘기가 아니라 내 통장 얘기라는 걸 다시 느낍니다.",
}
ctx = build_context(copy, cand, cfg["brand"], (out / "cover.jpg").as_uri(), cfg["publish"]["timezone"], True)
for p in render_slides(ctx, out):
    print(p)
